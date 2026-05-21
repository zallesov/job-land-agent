# Hermes Memory Storage Internals

How the built-in memory system works under the hood. Traced May 2026 from
`hermes-agent` source.

## File Layout

```
$HERMES_HOME/memories/
├── MEMORY.md        ← agent's durable notes (memory tool)
├── MEMORY.md.lock   ← file lock sidecar
├── USER.md          ← user profile entries
└── USER.md.lock
```

For a profile named `interviewprep`:
`~/.hermes/profiles/interviewprep/memories/`

## Entry Format

Plain Markdown, entries separated by `§` (section sign + newline):

```
Entry one text here.
§
Entry two text here.
§
```

Delimiter constant: `ENTRY_DELIMITER = "\n§\n"` in `tools/memory_tool.py:59`.

## Class Hierarchy

All in `tools/memory_tool.py`:

- **`get_memory_dir()`** (line 55): returns `get_hermes_home() / "memories"` — profile-scoped.
- **`MemoryStore`** (line 107): the built-in provider's data layer. One instance per `AIAgent`.
  - `memory_entries: List[str]` — live state, mutated by tool calls
  - `user_entries: List[str]` — live state, mutated by tool calls
  - `_system_prompt_snapshot: Dict` — frozen at `load_from_disk()`, used for system prompt injection. Never mutated mid-session. Keeps prefix cache stable.
  - `memory_char_limit` / `user_char_limit` — from config, default 2200 / 1375

- **`load_from_disk()`** (line 126): reads MEMORY.md and USER.md, deduplicates entries (keeps first occurrence), renders the system prompt snapshot.

- **`_path_for(target)`** (line 179): maps `"memory"` → `MEMORY.md`, `"user"` → `USER.md`.

- **`_file_lock(path)`** (line 144): context manager using `fcntl.flock` on a `.lock` sidecar file. Read-modify-write safety.

## Write Path

1. Agent calls `memory(action="add", target="memory", content="...")`
2. `handle_memory_tool()` in `memory_tool.py` routes to `MemoryStore.add_entry()`
3. `add_entry()` acquires file lock, appends to in-memory list, writes to disk, releases lock
4. Disk write is atomic via tempfile + `os.replace()` (line 442-454)
5. Tool response reflects live state (memory_entries), not the frozen snapshot

## Config Keys

```yaml
memory:
  memory_enabled: true          # enable memory tool
  user_profile_enabled: true    # enable user profile
  memory_char_limit: 2200       # max chars in system prompt MEMORY block
  user_char_limit: 1375         # max chars in system prompt USER block
  provider: ''                  # external provider name (empty = builtin only)
```

## How to Inspect Memory

```bash
# Read agent memory
cat ~/.hermes/profiles/interviewprep/memories/MEMORY.md

# Read user profile
cat ~/.hermes/profiles/interviewprep/memories/USER.md

# Or use hermes_home directly
cat "$(hermes config path | xargs dirname)/memories/MEMORY.md"
```

The injected blocks at conversation start are the rendered form of these files,
truncated to the char limits above.

## MemoryManager (External Providers)

In `agent/memory_manager.py` (line 190):
- Orchestrates built-in + at most one external provider
- Built-in provider always loaded first
- External provider (Honcho, Mem0, etc.) configured via `memory.provider` in config.yaml
- Tool schemas from all providers merged; tool-to-provider routing via `_tool_to_provider` dict

## Agent Init Flow

In `agent/agent_init.py` (line 932-950):
1. Reads `memory` config section
2. Creates `MemoryStore` with char limits from config
3. Calls `load_from_disk()` to populate entries and snapshot
4. Sets `agent._memory_store`, `agent._memory_enabled`, `agent._user_profile_enabled`
