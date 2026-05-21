# SRS Tetromino Shape Tables

All 7 standard pieces, each with 4 rotation states (0-3). Coordinates are relative to anchor point.

## I Piece (Cyan)
```
State 0: [(1,0), (1,1), (1,2), (1,3)]
State 1: [(0,1), (1,1), (2,1), (3,1)]
State 2: [(2,0), (2,1), (2,2), (2,3)]
State 3: [(0,1), (1,1), (2,1), (3,1)]
```

## O Piece (Yellow)
```
State 0: [(0,4), (0,5), (1,4), (1,5)]
State 1: [(0,4), (0,5), (1,4), (1,5)]
State 2: [(0,4), (0,5), (1,4), (1,5)]
State 3: [(0,4), (0,5), (1,4), (1,5)]
```

## T Piece (Purple)
```
State 0: [(0,3), (1,3), (1,4), (1,5)]
State 1: [(0,4), (1,3), (1,4), (2,4)]
State 2: [(1,3), (1,4), (1,5), (2,4)]
State 3: [(0,4), (1,3), (1,4), (2,4)]
```

## S Piece (Green)
```
State 0: [(0,4), (0,5), (1,3), (1,4)]
State 1: [(0,3), (1,3), (1,4), (2,4)]
State 2: [(1,3), (1,4), (2,4), (2,5)]
State 3: [(0,3), (1,3), (1,4), (2,4)]
```

## Z Piece (Red)
```
State 0: [(0,3), (0,4), (1,4), (1,5)]
State 1: [(0,3), (1,3), (1,4), (2,3)]
State 2: [(1,3), (1,4), (2,4), (2,5)]
State 3: [(0,3), (1,3), (1,4), (2,3)]
```

## J Piece (Blue)
```
State 0: [(0,3), (1,3), (1,4), (1,5)]
State 1: [(0,3), (0,4), (1,3), (2,3)]
State 2: [(1,3), (1,4), (1,5), (2,5)]
State 3: [(0,3), (1,3), (2,3), (2,4)]
```

## L Piece (Orange)
```
State 0: [(0,5), (1,3), (1,4), (1,5)]
State 1: [(0,3), (1,3), (2,3), (2,4)]
State 2: [(1,3), (1,4), (1,5), (2,3)]
State 3: [(0,3), (0,4), (1,3), (2,3)]
```

## SRS Wall Kick Offsets (Non-I Pieces)

Clockwise rotation kicks to try in order:
```
(0, 0), (0, -1), (0, +2), (-1, -1), (+2, -1)
```

Counter-clockwise rotation kicks to try in order:
```
(0, 0), (0, +1), (0, -2), (+1, +1), (-2, +1)
```

Full SRS tables: https://tetris.wiki/SRS
