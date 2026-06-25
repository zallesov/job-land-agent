---
name: installed-profile-repo-sync
description: "Convert an installed Hermes profile into a git-backed working tree while preserving local profile state and runtime data."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
---

# Installed Profile Repo Sync

Use this when a Hermes profile was installed/copied without `.git`, but the user now wants that same profile root to behave like a normal git checkout so changes can be committed and pushed.

## When to use

- The active profile root already contains source-like files (`scripts/`, `skills/`, `dashboard/`, `tests/`, `package.json`) but is not a git repo.
- The user wants to keep local profile changes as the source of truth.
- The profile also contains runtime state that must not be accidentally committed (session stores, auth files, caches, `home/`, etc.).

## Core idea

Do **not** replace the installed profile with a fresh clone blindly.
Instead:
1. authenticate GitHub first
2. clone the repo separately
3. back up the local key files
4. attach the clone's `.git` metadata to the installed profile root
5. extend `.gitignore` for profile-runtime noise
6. commit the local source state on a new branch

This preserves the live profile while making it pushable.

## Prerequisites

- Git works
- GitHub auth works (`gh auth status` or equivalent)
- The repo URL is known
- The user explicitly wants the installed profile state preserved

## Recommended flow

### 1. Verify the profile is source-shaped

Look for a repo-like structure in the installed profile root:
- `scripts/`
- `skills/`
- `dashboard/`
- `tests/`
- `package.json` / `pyproject.toml`

If the profile is only runtime state and not source-shaped, stop and use a normal clone instead.

### 2. Install persistent GitHub CLI auth if needed

In persistent-profile environments, install `gh` under profile HOME, not system overlay:
- binary path: `$HOME/bin/gh`
- auth files: `$HOME/.config/gh/hosts.yml`

This matters in Dockerized profiles where `/opt/data` persists and overlay-root may not.

### 3. Clone the repo separately first

Clone to a scratch path under persistent HOME, for example:
- `$HOME/src/<repo>-tmp`

Use this clone only as the source of `.git` metadata and remote config.

### 4. Back up local key files before attaching `.git`

At minimum, copy these to a timestamped backup dir:
- `config.yaml`
- `distribution.yaml`
- `.gitignore`

If the profile has other highly customized tracked files, back them up too.

### 5. Attach the clone's `.git` dir to the installed profile root

If the target profile root has no `.git` yet, copy the clone's `.git` into it.

After that, verify:
- current branch
- remote URL
- `git status`

### 6. Extend `.gitignore` for runtime-only profile noise

Common ignores worth adding in installed Hermes profiles:
- `.clean_shutdown`
- `.skills_prompt_snapshot.json`
- `skills/.hub/`

Keep existing runtime ignores for:
- DB files
- caches
- `home/`
- auth files
- session/log dirs

### 7. Inspect dirty tracked files before committing

Typical tracked local changes may include:
- `config.yaml`
- `distribution.yaml`
- skill docs
- scripts
- lockfiles

Do not assume these are accidental. The user may want the local installed state preserved and committed.

### 8. Create a branch before the first commit

Use a branch like:
- `chore/gitify-profile-state`

Then commit the current local source state so the working tree becomes clean.

## Important judgment rules

### Treat local config as intentional if the user says so

If the user says the installed/local version is newer or should become canonical:
- keep the local `config.yaml`
- keep the local `distribution.yaml`
- do not automatically restore repo versions

### Preserve model/provider intent when requested

If the user explicitly wants a local model/provider change (for example Codex/OpenAI as default) to become the new default, treat that as intentional source state.

### Keep required provider hooks intact

Even if the default model changes, do not casually remove required provider support from the config or distribution metadata if the repo still uses it elsewhere (for example a `DEEPSEEK_API_KEY` requirement for screening/assessment workflows).

## Verification checklist

After gitifying and committing:
- `git status` is clean
- branch is not `main` unless the user asked for that
- remote points to the expected GitHub repo
- `gh auth status` succeeds
- the auth/config paths live under persistent profile HOME

## Push workflow

1. commit local state
2. push branch
3. optionally open PR
4. continue feature work on top of the now-clean branch

## Pitfalls

- Do not overwrite the installed profile with a fresh clone unless the user explicitly wants to discard local state.
- Do not commit runtime/profile data just because the tree became git-backed.
- Do not store `gh` in overlay-root when the profile has a persistent HOME.
- Do not assume `config.yaml` drift is accidental; inspect and ask if needed.

## References

See `references/joblandagent-gitify-example.md` for a concrete in-session example using a Dockerized persistent profile with `gh` installed under profile HOME and `.git` attached from a separate clone.
