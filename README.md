Jazz Jackrabbit 1 DOS Data Level Editor v14
===========================================

Rendering / overlay cleanup release:

- Collision mask orientation fixed: bit 0 is now drawn on the left side of the 8×8 tile mask.
- Collision overlay is now transparent/hatched instead of covering the artwork.
- Grid, collision, event labels, object names, water, start marker and paths are drawn as independent canvas overlay items, not burned into the scaled pixel-art map image.
- Background color is taken from the loaded tileset palette and used as the canvas/base map background.
- LEVEL LOCAL child tabs are now named simply `Event defs`, `Animations`, `Paths`, `Masks`, etc.; the parent workspace already says LEVEL LOCAL.

Jazz Jackrabbit 1 DOS Data Level Editor v14
===========================================

UX cleanup release:

- Unknown events no longer get a misleading fallback Jazz/rabbit icon. If an event has no explicit usable animation, no icon is shown.
- Removed the redundant Level Local overview tab.
- Cell/object inspector is now a compact bottom information bar instead of a large right-side panel.
- Right-click erases in the active layer:
  - Tiles mode clears tile/BG.
  - Events/Objects mode clears event placement.
  - Shift+right-click or middle-click still picks values.
- Tile atlas wraps dynamically according to the Build panel width.

Jazz Jackrabbit 1 DOS Data Level Editor v14
===========================================

This editor targets the **original Jazz Jackrabbit 1 DOS data files**, not an OpenJazz-specific project format.

OpenJazz is useful here only as a reference implementation for understanding how the original DOS assets are parsed and interpreted.

Target files include:

- `LEVEL*.*` — original DOS level files
- `BLOCKS.*` — external tilesets/palettes
- `SPRITES.*` — external world sprite assets
- `MAINCHAR.000` — shared/main character sprites
- music/resource files referenced by the original data

Workspace split:

- **BUILD**: WYSIWYG level placement/editing.
- **LEVEL LOCAL**: definitions stored inside the currently opened `LEVEL` file.
- **GAME GLOBALS**: external/shared DOS game assets such as `BLOCKS.xxx`, `SPRITES.xxx`, `MAINCHAR.000`, music/resource files.
- **ENGINE GLOBAL**: behavior hardcoded in the original game engine / mirrored by OpenJazz-reference code.

Run:

```bash
python jazz1_dos_level_editor.py /path/to/JAZZ_DOS_DIRECTORY
```

Jazz Jackrabbit 1 DOS Data Level Editor v14
===============================

Scope separation release:

- **BUILD**: WYSIWYG placement/editing.
- **LEVEL LOCAL**: definitions stored inside the currently opened level file.
- **GAME GLOBALS**: external/shared game assets such as `BLOCKS.xxx`, `SPRITES.xxx`, `MAINCHAR.000`, music/resource files.

This version renames the previous ambiguous “global” tabs to **Level Local** and adds a separate **Game Globals** workspace.

Jazz Jackrabbit 1 DOS Data Level Editor v14
===============================

Performance/UX release:

- chunked 16×16-tile rendering cache,
- fast tile/event painting updates only the affected chunk,
- one undo snapshot per paint stroke instead of one per cell,
- brush ghost/preview on hover,
- clearer stroke status showing what is being placed and how many cells changed.

Jazz Jackrabbit 1 DOS Data Level Editor v14
==============================

This version reorganizes the editor into two main workspaces:

- **BUILD - place things**: WYSIWYG level construction, object prefabs, tiles, start marker and layers.
- **DEFINE - object types**: level-local event/object type authoring, event definitions, animations, paths, masks and validation.

# Jazz Jackrabbit 1 DOS Data Level Editor v14

Standalone WYSIWYG-oriented GUI prototype for editing Jazz Jackrabbit 1 DOS/OpenJazz/reference levels.

## Run

```bash
python -m pip install pillow
python jazz1_dos_level_editor.py /path/to/JAZZ
```

## What v14 focuses on

This version makes the editor less raw-byte-centric and more WYSIWYG:

- object sprites are shown directly on the map when the level animation/sprite data resolves them,
- optional readable object-name labels can be drawn over the map,
- water level, player start, paths, collision masks, event labels and object sprites are separate visible layers,
- the new **Layers** tab lets you toggle visibility and lock dangerous layers against accidental edits,
- the new **Object Types** tab treats event IDs as level-local object definitions instead of pretending they are hardcoded global game objects,
- selected object types can be highlighted across the map,
- selected placements can be duplicated into a fresh level-local event definition slot,
- selected placements or all placements of a highlighted type can be replaced with the current object brush.

## Main editing model

The editor separates four concepts:

- **Tiles**: visual tile ID and optional BG flag.
- **Events**: raw numeric event ID stored in a map cell.
- **Objects**: concrete event placements on the map, with sprite preview where possible.
- **Object Types / Level Definitions**: shared definitions inside the current level file. Editing these affects all placements using that event ID in the current level only.

## Important JJ1 detail

Event definitions, animations, paths and masks are not global game-wide object definitions. They are shared tables inside each level. So v14 uses terms like **Object Types** and **Level Definitions** rather than treating event 17 as a universal object across the whole game.

## Save strategy

`Save as...` always writes the safe placement layer:

- tile IDs
- BG flags
- map event placements
- basic metadata / player start

Level-wide/shared tables are written only when their checkbox is enabled in **Level Definitions** or the relevant definition tab:

- event definitions
- paths
- collision masks
- animations

This is intentional because shared definitions can affect many placed objects at once.
