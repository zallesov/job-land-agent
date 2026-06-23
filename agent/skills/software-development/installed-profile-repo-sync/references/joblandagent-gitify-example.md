# JobLandAgent gitify example

Concrete pattern used in this session:

## Context

- Active Hermes profile root: `/opt/data/profiles/joblandagent`
- Persistent profile HOME: `/opt/data/profiles/joblandagent/home`
- Goal: make the installed profile pushable to GitHub without discarding local changes.

## Steps that worked

1. Install `gh` under persistent HOME:
   - `/opt/data/profiles/joblandagent/home/bin/gh`
2. Authenticate with `gh auth login` using the device flow.
3. Clone the repo separately to a temp path under HOME:
   - `/opt/data/profiles/joblandagent/home/src/job-land-agent-tmp`
4. Back up local key files to a timestamped backup dir:
   - `config.yaml`
   - `distribution.yaml`
   - `.gitignore`
5. Copy the temp clone's `.git` dir into the installed profile root.
6. Extend `.gitignore` for profile-runtime noise:
   - `.clean_shutdown`
   - `.skills_prompt_snapshot.json`
   - `skills/.hub/`
7. Create a branch before the first commit:
   - `chore/gitify-profile-state`
8. Commit the current local state to make the work tree clean.
9. Push the branch.

## What mattered

- `/opt/data` was persistent; overlay-root was not the right place for `gh`.
- The installed profile already had repo-like source structure, so attaching `.git` was viable.
- The user explicitly wanted local changes preserved as canonical source state, including the Codex/OpenAI default model.
- Even with that preference, provider hooks such as DeepSeek support still needed to remain in the config/distribution story because other workflows depend on them.

## Files that showed up as intentional tracked changes

- `config.yaml`
- `distribution.yaml`
- `SOUL.md`
- `pnpm-lock.yaml`
- several `skills/` docs
- some `scripts/` files

This is a reminder to inspect tracked diffs before the first commit, but not to assume they should be reverted.
