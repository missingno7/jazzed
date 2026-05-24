# User Guide

Jazzed edits original DOS Jazz Jackrabbit 1 level data. Most tables are level-local, meaning a change affects the currently loaded `LEVEL*.*` file, not every level in the game.

## Main Workspaces

### Level Editor

The main map canvas shows the loaded level as a tile grid. The toolbar controls common visible layers such as grid, events, collision, player start, object sprites, paths, names, and water.

Editing modes:

- `Tiles`: paint visual tile IDs and optionally the BG flag.
- `Events`: paint raw event IDs into map cells.
- `Objects`: select, move, duplicate, replace, or delete event placements.
- `Start`: place the player start position.
- `Inspect`: inspect cells without editing.

### BUILD

The BUILD workspace focuses on placing things in the level:

- tile atlas and selected tile ID
- object prefab palette
- placed object list
- layer visibility and locks
- player start and metadata controls

Use layer locks when editing risky data. For example, lock events while painting tiles if you do not want to accidentally change object placements.

### EVENT DEFS

Event definitions are level-local object type definitions. Editing event definition `17` in one level does not necessarily mean event `17` behaves the same in another level.

The event definition editor has concept-based controls for common object types and an advanced raw-byte view for diagnostics.

Reserved engine marker event IDs `122..126` should be treated carefully. Their behavior is tied to the numeric event ID in the engine.

### LEVEL LOCAL

Level-local tables include:

- animations
- bullets
- paths
- collision masks
- validation

These tables are stored inside the current level file and can affect many map placements at once.

### Assets Browser

The assets browser previews game-wide files in the selected game data directory, such as tilesets, sprites, audio/resource files, and other original DOS assets.

## Save Behavior

`Save` writes changes back to the current level path.

`Save as...` writes the current level to a chosen path.

Because Jazzed edits original binary data, keep backups of important levels while experimenting.

## Collision Overlay

The collision overlay visualizes each tile's 8x8 collision mask. It is cached as bitmap overlays for performance and is available both on the map and in the tile atlas.

## Background Rendering

Jazzed approximates the in-game background from JJ1 palette/background metadata. Sky levels use the tileset background palette when the level metadata indicates a sky effect.
