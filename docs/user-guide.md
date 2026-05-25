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
- object prefab palette, with both atlas and list views
- placed object list
- layer visibility and locks
- player start and metadata controls

Use layer locks when editing risky data. For example, lock events while painting tiles if you do not want to accidentally change object placements.

### LEVEL LOCAL

Level-local tables include:

- event definitions
- animations
- bullets
- paths
- collision masks
- validation

These tables are stored inside the current level file and can affect many map placements at once.

The `Events` tab edits level-local object type definitions. Editing event definition `17` in one level does not necessarily mean event `17` behaves the same in another level. The editor has a concept-based view for common object types and a raw/interpretation view for diagnostics.

Reserved engine marker event IDs `122..126` should be treated carefully. Their behavior is tied to the numeric event ID in the engine. Jazzed visualizes several reserved and mechanical event types in the map overlay, including one-way platform markers, pass-through foreground markers, difficulty badges, conveyor/belt arrows, float/blower arrows, and repel/sucker tube arrows.

The `Animations` tab edits the level-local animation table. It has a sprite atlas picker, frame ordering controls, per-frame sprite IDs, signed X/Y offsets, and a live preview.

The `Bullets` tab edits level-local bullet definitions. Sprite and sound fields use picker controls, and bullet type pickers in event concepts use an atlas view.

The `Masks` tab edits the level-local 8x8 collision mask for each tile. Pick a tile from the atlas, then paint the enlarged tile/mask grid directly: left-click or drag to set solid cells, right-click or drag to erase cells.

### Assets Browser

The assets browser previews game-wide files in the selected game data directory, such as tilesets, sprites, audio/resource files, and other original DOS assets.

The Audio tab can browse and play individual clips from `SOUNDS.000`. Music module formats such as `.PSM` are listed with contextual controls; direct in-editor module playback depends on available local players/libraries, so external opening remains the fallback.

## Save Behavior

`Save` writes changes back to the current level path, including edited level-local tables such as event definitions, paths, masks, animations, and bullets.

`Save as...` writes the current level to a chosen path.

Because Jazzed edits original binary data, keep backups of important levels while experimenting.

## Collision Overlay

The collision overlay visualizes each tile's 8x8 collision mask. It is cached as bitmap overlays for performance and is available both on the map and in tile/mask atlases.

## Background Rendering

Jazzed approximates the in-game background from JJ1 palette/background metadata. Sky levels use the tileset background palette when the level metadata indicates a sky effect. The editor uses a deterministic full-level gradient so zoom changes do not alter the background representation.
