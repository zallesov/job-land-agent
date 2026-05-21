# Version-Controlling a Hermes Profile

Move a Hermes agent profile from `~/.hermes/profiles/<name>/` into a git repo so config, skills, and scripts are tracked alongside project files.

## When to use this

- You want your Hermes config, skills, and templates under version control
- The profile lives in a repo alongside other materials (resume, scraping pipeline, dashboard code)
- You want clean git history for config changes without runtime state bloat

## Step-by-step

### 1. Identify the source profile

```bash
hermes profile list
hermes profile show <name>
```

Note the profile's absolute path (typically `~/.hermes/profiles/<name>/`).

### 2. Copy the profile to the repo

```bash
cp -a ~/.hermes/profiles/<name>/ /path/to/repo/hermes-profile
```

Use `cp -a` (archive mode) to preserve permissions, symlinks, and file metadata.

### 3. Create `.gitignore` for runtime state

Write a `.gitignore` at the root of the copied profile dir:

```gitignore
# Runtime state — never commit
home/
sessions/
cache/
logs/
*.db
*.db-*
.env
```

- `home/` — the profile's `$HOME` runtime directory (often GBs of cached data)
- `sessions/` — SQLite session transcripts
- `cache/` — model downloads, skill caches
- `logs/` — gateway and agent logs
- `*.db` — state databases (kanban board, session store, etc.)
- `.env` — API keys and secrets

### 4. Symlink the original location to the new one

```bash
rm -rf ~/.hermes/profiles/<name>
ln -s /path/to/repo/hermes-profile ~/.hermes/profiles/<name>
```

This makes Hermes continue to find the profile at its expected path while the actual files live in the repo symlink resolves to.

### 5. Stage and commit

```bash
cd /path/to/repo
git add hermes-profile/.gitignore hermes-profile/
git commit -m "chore: add Hermes agent profile (<name>/)"
```

### 6. Verify

```bash
# Symlink resolves correctly
readlink ~/.hermes/profiles/<name>
# -> /path/to/repo/hermes-profile

# No runtime files leaked into git
git ls-files hermes-profile/ | grep -E 'home/|sessions/|cache/|logs/|\.db'

# Profile still recognized
hermes profile show <name>
```

## Verification checklist

- [ ] Symlink: `readlink ~/.hermes/profiles/<name>` points to the repo path
- [ ] No runtime files in git: `git ls-files hermes-profile/` shows only config, skills, templates
- [ ] Profile recognized: `hermes profile show <name>` succeeds
- [ ] Gateway needs a restart after the move if it was running

## Pitfalls

- **Do NOT replace `.env` with a tracked file.** API keys belong in `.env`, which should be gitignored. Use `.env.example` or similar for doc purposes.
- **Check for hardcoded absolute paths** in config.yaml before moving. The config referencing `~/.hermes/profiles/<name>/home/...` patterns will break if the profile moves. Grep: `grep -r "~/.hermes/profiles" hermes-profile/ | grep -v sessions/ | grep -v cache/ | grep -v logs/`
- **The profile name comes from the directory name**, not from any internal config. The directory under `~/.hermes/profiles/` must match the profile name `hermes profile list` expects.
