# Git from a Non-TTY Agent Environment

Hermes terminal sessions lack a proper TTY/PTY. Several git operations that open an editor will hang silently. Use these workarounds.

## `cd` Resolution Issues

In some Hermes profile environments, `cd <path>` resolves against a wrong working directory. Use `git -C <absolute_path> <command>` instead.

```bash
# DON'T: cd then git
cd ~/.hermes/profiles/joblandagent-dev && git pull

# DO: git -C
git -C /Users/zall/.hermes/profiles/joblandagent-dev pull
```

## Locating the Repo Root

Use `git rev-parse --show-toplevel` to confirm you're in a repo, or `find <path> -name ".git" -type d` to search for repos.

```bash
find ~/.hermes -name ".git" -type d 2>/dev/null
git -C /path/to/suspect-dir rev-parse --show-toplevel 2>/dev/null || echo "NOT_A_REPO"
```

## Rebasing Without a TTY

`git rebase --continue` opens the default editor (usually vim) to let you edit the commit message. Without a TTY, the command hangs forever.

**Fix:** use `GIT_EDITOR=true` or `-c core.editor=true` on the continue command:

```bash
# Instead of:
git rebase --continue   # HANGS — opens vim, no TTY

# Use:
git -c core.editor=true rebase --continue
# or:
GIT_EDITOR=true git rebase --continue
```

## Pulling with Divergent Branches

When `git pull` says "divergent branches" and you're in an agent:

```bash
# 1. Check for unstaged changes first
git -C <path> status --short

# 2. Stash if needed
git -C <path> stash

# 3. Rebase pull (keeps history linear)
git -C <path> pull --rebase
# If that fails with "you have divergent branches":
git -C <path> branch --set-upstream-to=origin/main main
git -C <path> pull --rebase

# 4. Resolve conflicts if they occur (see "Rebasing Without a TTY" above)

# 5. Pop stash
git -C <path> stash pop
```

## Setting Upstream Tracking

If `git pull` says "no tracking information":

```bash
git -C <path> branch --set-upstream-to=origin/main main
```
