---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing
- Web scraping / browser automation (Codex has built-in Chrome control)
- Running Codex skills (auto-discovered from `~/.codex/skills/`)

Requires the codex CLI and a git repository.

## Prerequisites

- Codex installed: `npm install -g @openai/codex` (see Troubleshooting below if macOS blocks it)
- OpenAI auth configured: either `OPENAI_API_KEY` or Codex OAuth credentials
  from the Codex CLI login flow
- **Must run inside a git repository** — Codex refuses to run outside one
- Use `pty=true` in terminal calls — Codex is an interactive terminal app

## Troubleshooting: macOS Gatekeeper / XProtect Flags Binary as Malware

**Symptom:** `ENOENT` on the native binary at `vendor/aarch64-apple-darwin/codex/codex`,
or macOS popup: "codex-aarch64-apple-darwin" was not opened because it contains malware.

**Root cause:** Apple XProtect / notarization rejection. The binary gets deleted or
quarantined by macOS immediately after install. Multiple open GitHub issues (#22135,
#21199, #18985). OpenAI needs to re-sign/re-notarize the release.

**Workaround — Manual GitHub Release download (preferred):**

```sh
# Download latest release tarball
curl -L https://github.com/openai/codex/releases/latest/download/codex-aarch64-apple-darwin.tar.gz | tar xz

# Rename (archive has platform in name) and copy to PATH
# Option A: system-wide (needs sudo)
sudo mv codex-aarch64-apple-darwin /usr/local/bin/codex
# Option B: user-local (no sudo, prefer if ~/.local/bin is in PATH)
mv codex-aarch64-apple-darwin ~/.local/bin/codex

# Strip Gatekeeper quarantine so macOS trusts it
xattr -d com.apple.quarantine ~/.local/bin/codex 2>/dev/null || true

# Ad-hoc sign — macOS may still refuse unsigned binaries even after quarantine removed
codesign --force --deep --sign - ~/.local/bin/codex
```

**Workaround — xattr on npm-installed binary (if binary not yet deleted):**

```sh
# Find and strip quarantine from the native binary
find /opt/homebrew/lib/node_modules/@openai/codex -name "codex" -type f -exec xattr -d com.apple.quarantine {} \; 2>/dev/null
# Or if the install is via pnpm:
find ~/Library/pnpm -path "*/@openai+codex*/vendor/*/codex" -type f -exec xattr -d com.apple.quarantine {} \; 2>/dev/null
```

**Workaround — Ad-hoc sign (if binary exists but won't execute):**

```sh
codesign --force --deep --sign - /path/to/codex/binary
```

**MacOS reinstall tip:** After the binary is removed by XProtect, re-running
`npm install -g @openai/codex` will NOT re-download it — npm uses its cache.
Force a clean reinstall:
```sh
npm uninstall -g @openai/codex
npm cache clean --force
npm install -g @openai/codex
# Then immediately strip quarantine (above) before XProtect scans it
```

See `references/macos-gatekeeper.md` for detailed error transcripts and
reproduction steps.

## Troubleshooting: 401 Unauthorized Inside Hermes Sessions

**Symptom:** `codex exec` fails with `HTTP error: 401 Unauthorized` and repeated
`failed to connect to websocket` errors, even though `codex login` succeeds when
run directly in your terminal.

**Root cause:** Hermes profiles redirect `HOME` to a profile-specific directory
(e.g., `~/.hermes/profiles/<name>/home/`). Codex looks for `auth.json` and
`config.toml` under `$HOME/.codex/`, but that directory doesn't exist (or lacks
auth files) in the profile home.

**Fix — Symlink auth into the profile home:**

```sh
mkdir -p $HOME/.codex
ln -sf /Users/<you>/.codex/auth.json $HOME/.codex/auth.json
ln -sf /Users/<you>/.codex/config.toml $HOME/.codex/config.toml
```

Symlinks are better than copying because they stay in sync when you re-auth
or update config in the real `~/.codex/`.

**Quick workaround (if you can't symlink):** prefix with the real HOME:
`HOME=/Users/<you> codex exec ...`
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session may live under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

## One-Shot Tasks

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## Background Mode (Long Tasks)

```
# Start in background with PTY
terminal(command="codex exec --sandbox workspace-write 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Browser Capabilities

Codex can control Chrome directly — no Playwright needed. Three browser modes, all
stable and enabled by default in 0.130.0+:

| Feature | What it does |
|---------|-------------|
| `browser_use` | Built-in browser for web tasks |
| `browser_use_external` | Controls real Chrome via the Codex Chrome extension — same profile, cookies, logged-in sessions, multiple tabs in parallel |
| `in_app_browser` | Browser inside the Codex desktop app |
| `computer_use` | Full desktop control (screenshot, mouse, keyboard) |

The Chrome extension creates its own tab group, works in the background, and can
script repetitive actions across parallel tabs. Combine with plugins for email,
spreadsheets, etc.

Check what's enabled: `codex features list | grep browser`

For persisting browser auth/cookies across Codex sessions (Playwright MCP `userDataDir`),
see `references/playwright-mcp-persistence.md`.

## Running Codex Skills from Hermes

Codex auto-discovers skills in `~/.codex/skills/`. Each skill has a
`SKILL.md` + optional `agents/`, `scripts/`, `references/` directories.

To run a Codex skill from Hermes:

```bash
# Long-running skill (browser scraping, multi-step automation)
codex exec --cd <workspace> "Run the <skill-name> skill: <context>"  # with pty=true, background=true

# Example: a job-scraping skill that browses JobLeads and exports a spreadsheet
codex exec --cd /Users/zall/interviews "Update my JobLeads jobs workbook from the configured searches. Use the jobleads-daily-export skill."
```

Codex skills that do browser scraping need the user to be logged into the target
site in Codex's in-app browser beforehand (authenticated session).

Monitor progress: `codex resume --last` or `process(action="poll", session_id="...")`

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--sandbox workspace-write` | Auto-approves file changes in workspace (replaces deprecated `--full-auto`) |
| `--skip-git-repo-check` | Allow running outside a git repository |
| `--yolo` | No sandbox, no approvals (fastest, most dangerous) |

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --yolo exec 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="codex --yolo exec 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Rules

1. **Always use `pty=true`** — Codex is an interactive terminal app and hangs without a PTY
2. **Git repo required by default** — Codex won't run outside a git directory. Use `--skip-git-repo-check` for non-git dirs, or `mktemp -d && git init` for scratch work.
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--sandbox workspace-write` for building** — auto-approves changes within the sandbox (`--full-auto` deprecated)
5. **Background for long tasks** — use `background=true` and monitor with `process` tool
6. **Don't interfere** — monitor with `poll`/`log`, be patient with long-running tasks
7. **Parallel is fine** — run multiple Codex processes at once for batch work
