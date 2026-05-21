---
name: terminal-games
description: "Build playable terminal/CLI games using stdlib (curses, etc.) with testable game logic."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [terminal, cli, game, curses, stdlib, testing]
---

# Terminal Games

Use this skill when building **playable terminal/CLI games** using Python stdlib (primarily `curses`) with unit-testable game logic.

Load this when the user wants to build a terminal game, CLI puzzle, or any interactive text-based game.

## Core Architecture Pattern

The key challenge: **curses blocks testing**. Always separate logic from rendering.

```
tetris.py
├── Tetromino   — piece shapes, rotation states (no curses)
├── Board       — grid storage, collision detection (no curses)
├── Game        — rules: gravity, scoring, lock delay, line clearing (no curses)
└── Renderer    — curses drawing only (imported by main, not by tests)
```

**Rule:** `Tetromino`, `Board`, and `Game` must never import or depend on `curses`. Tests import only these three.

## Key Design Decisions

### Hidden Spawn Rows
Add hidden rows above the visible board so pieces can spawn partially off-screen. For a 10x20 Tetris board, use `TOTAL_ROWS = 22` (20 visible + 2 hidden). The renderer only draws rows 2–21.

### Anchor-Based Positioning
Store piece cells as **relative offsets** from an anchor point `(anchor_r, anchor_c)`. Absolute position = `cell + (anchor_r, anchor_c)`. This makes:
- Rotation simple (rotate relative cells around center)
- Collision checks clean (convert to absolute, check bounds/board)

### Lock Delay Mechanics
When a piece can't move down:
1. Set `is_locking = True`, start 500ms timer
2. Player moves/rotates → reset timer (max 15 resets)
3. Timer expires or 15 resets reached → lock piece to board
4. If locked entirely in hidden rows → game over

### Hard Drop Must Lock Immediately
`hard_drop()` moves piece to bottom, then **must call `lock_active()`** immediately. Don't just update position — write to grid, clear lines, spawn next.

### SRS Tetromino Shapes
Store all 7 pieces with 4 rotation states each. Use relative coordinates that place the piece's center near `(0, 0)` for clean rotation. See `references/srs-tetrominoes.md` for the full shape tables.

## Testing Strategy

- **No `curses` in tests.** Tests import only `Board`, `Tetromino`, `Game`.
- Test collision by placing anchor at boundary positions (e.g., `anchor_c = -4` for T piece to hit left wall).
- Test scoring by directly calling `lock_active()` or `clear_lines()`.
- Test bag randomizer independently from game loop.

## Pitfalls

1. **Wall collision tests fail silently** if piece's leftmost relative column > 0. T piece starts at col 3, so `anchor_c = -1` still leaves it at column 2. Use `anchor_c <= -3` to actually hit the wall.
2. **Lock delay flag** must be set in `tick()` when downward move fails, not just on player input.
3. **Hard drop** must trigger full lock sequence (write to grid, clear lines, update score), not just reposition.
4. **Color fallback**: check `curses.has_colors()` before using color pairs. Fall back to monochrome (`#`, `|`, `-`) if False.
5. **Terminal size check**: verify `stdscr.getmaxyx()` >= (24, 40) before starting.

## Related Skills

- `spike` — use for feasibility experiments before building
- `writing-plans` — use to plan the game architecture first
