Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Level-local Bullet Editor release:

- Added `LEVEL LOCAL -> Bullets`.
- The parser now reads the real JJ1 level-local bullet table:
  - 32 bullet definitions
  - 20 bytes each
  - plus 32 attack names of 21 bytes each
- Bullet editor exposes:
  - left/right/lower-left/lower-right sprite/event refs
  - x speed
  - y speed
  - gravity
  - finish animation
  - finish sound
  - behaviour
  - start sound
  - attack name
- Bullet sprite fields have a visual sprite atlas picker.
- Finish animation has an animation atlas picker.
- `EVENT DEFS` bullet picker now lists real level-local bullet definitions instead of only generic bullet IDs.
- Save writes bullet definitions and attack names back to the level file.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Reliable Animation Picker release:

- Rebuilt the animation picker hit-testing.
- Each animation is now a filled clickable tile instead of a mostly-border/transparent canvas item.
- Hovering an animation highlights the whole tile.
- The mouse cursor changes over selectable animations.
- Clicking anywhere inside the animation tile selects it.
- Double-click also selects it.
- This should fix the intermittent issue where animation cells only clicked after moving/resizing the window.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Animation/Bullet picker cleanup:

- `animation speed` no longer gets an animation atlas button.
- Animation atlas buttons are only shown for fields that actually reference animations:
  - left/right animation
  - finish left/right animation
  - shoot left/right animation
- `bullet type` now has a `Pick…` button.
- Bullet picker shows human-readable bullet slot labels where known and generic labels otherwise.
- Interpretation panel now shows bullet type labels instead of just a raw number.

Note: the full JJ1 level-local bullet table decoder is still a future research step; v24 adds the semantic UI layer and picker first.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Event Definitions Workspace release:

- `EVENT DEFS` is now a main workspace next to `BUILD` and `LEVEL LOCAL`.
- Inside `EVENT DEFS`:
  - `Concept editor`
  - `Raw / interpretation`
- `Object Types` is no longer a visible tab; object type editing happens in `EVENT DEFS`.
- Event selector now marks unused event definitions as `Unused`.
- `Unused / empty` is a first-class concept; selecting an unused event lets you choose a concept and turn it into an object type.
- Added `Duplicate as new` to copy the currently selected event definition into a free normal event slot.
- Added animation picker buttons (`Atlas…`) next to animation fields in the concept editor.
- `New type` now creates a truly empty/unused event definition, then lets you choose the concept.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Concept Object Type Editor release:

- `Object Types` tab is no longer shown separately; object type editing is unified into `Event defs`.
- `Event defs` now has its own event selector, so you choose the event/object type directly inside the editor.
- Event editing is concept-driven instead of raw-field-first:
  - Enemy / hazard
  - Touch pickup / item
  - Shootable pickup / container
  - Destructible block
  - Spring / bounce
  - Warp trigger
  - Conveyor belt
  - Path-moving object
  - Foreground / engine marker
  - Raw / advanced
- The visible controls change by concept:
  - pickup identity is a dropdown,
  - shootable/touch behavior is a checkbox,
  - weapon/ammo reward type is chosen semantically,
  - enemy fields show health/score/bullet/movement,
  - path objects show path index,
  - warp shows target X/Y,
  - destructible blocks show hits and replacement tile.
- Raw byte fields still exist behind `Show advanced raw field editors`.
- Added `New type` to allocate a free normal event ID in range `1..121`.
- `LEVEL0.000` sanity check:
  - Event 4 is interpreted as touch pickup/item.
  - Event 14 is interpreted as shootable pickup/container.
  - Reserved events 122/126 remain engine marker events.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Semantic Event Definition Editor release:

- `Event defs` now exposes every known event-definition field and hides `unused_*` bytes from editing.
- The editor keeps raw bytes visible for diagnostics.
- Field labels now adapt to the event's movement/modifier where known, for example:
  - `modifier / pickup identity`
  - `strength: 0 touch, >0 shootable`
  - `path index (multiA)`
  - `warp target X/Y`
- Added an `Interpretation` panel explaining what the current event likely does.
- Pickup identity is now interpreted primarily from `modifier`, based on the Jazz 1/OpenJazz-reference `takeEvent()` logic.
- Strength is interpreted contextually: for pickup-like modifiers, `strength == 0` means touch pickup/trigger, while `strength > 0` means shootable/destructible container/object before the effect is awarded.
- Weapon/ammo modifier meanings are shown explicitly, e.g. weapon 0/1/2/3 ammo amounts and TNT.
- Save writes the modified level-local event definitions directly; there is no separate “save modified event defs” checkbox.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

UI cleanup release:

- Removed redundant overview/click-through tabs:
  - BUILD overview
  - LEVEL LOCAL Summary
  - GAME GLOBALS overview
- Event definition/path/mask/animation Apply now simply modifies the level-local data.
- Save always writes the current level-local edited structures; no separate “save modified level-local table” checkboxes.
- Object Prefabs is cleaner:
  - removed `Reserved markers` help button
  - removed redundant `Use selected palette event` button
  - selecting a palette item is enough; `Use selected as brush` remains for selected map objects.
- Reduced explanatory text/noise in the UI.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

WYSIWYG brush preview + normal save release:

- Brush preview now shows the actual tile image when placing tiles.
- Brush preview shows the object sprite/icon when the selected event has a usable sprite preview.
- Events without an icon still show the outlined cell + label.
- Added normal **Save** button / Ctrl+S that writes to the current level path.
- **Save as...** still lets you choose another path.
- The window title shows `*` when the level has unsaved changes.
- Loading another level, reloading, opening another game dir, or closing the window now asks whether to save unsaved changes.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Reserved engine marker event release:

- Events `122..126` are now treated as reserved engine marker events, not normal editable object types.
- Friendly names:
  - `122` — One-way platform marker
  - `123` — Animated foreground tile marker
  - `124` — Foreground pass-through solid tile marker
  - `125` — Foreground decoration marker
  - `126` — Spike / hurt marker
- Normal duplicate/create-new event definition workflow now uses event IDs `1..121`.
- Reserved marker tooltips explain that behavior is tied to the numeric event ID, not to a cloneable 32-byte event definition.
- Reserved markers still remain visible/selectable as event placements, because they are real event IDs stored in the original DOS level grid.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===========================================

Rendering / overlay cleanup release:

- Collision mask orientation fixed: bit 0 is now drawn on the left side of the 8×8 tile mask.
- Collision overlay is now transparent/hatched instead of covering the artwork.
- Grid, collision, event labels, object names, water, start marker and paths are drawn as independent canvas overlay items, not burned into the scaled pixel-art map image.
- Background color is taken from the loaded tileset palette and used as the canvas/base map background.
- LEVEL LOCAL child tabs are now named simply `Event defs`, `Animations`, `Paths`, `Masks`, etc.; the parent workspace already says LEVEL LOCAL.

Jazz Jackrabbit 1 DOS Data Level Editor v24
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

Jazz Jackrabbit 1 DOS Data Level Editor v24
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

Jazz Jackrabbit 1 DOS Data Level Editor v24
===============================

Scope separation release:

- **BUILD**: WYSIWYG placement/editing.
- **LEVEL LOCAL**: definitions stored inside the currently opened level file.
- **GAME GLOBALS**: external/shared game assets such as `BLOCKS.xxx`, `SPRITES.xxx`, `MAINCHAR.000`, music/resource files.

This version renames the previous ambiguous “global” tabs to **Level Local** and adds a separate **Game Globals** workspace.

Jazz Jackrabbit 1 DOS Data Level Editor v24
===============================

Performance/UX release:

- chunked 16×16-tile rendering cache,
- fast tile/event painting updates only the affected chunk,
- one undo snapshot per paint stroke instead of one per cell,
- brush ghost/preview on hover,
- clearer stroke status showing what is being placed and how many cells changed.

Jazz Jackrabbit 1 DOS Data Level Editor v24
==============================

This version reorganizes the editor into two main workspaces:

- **BUILD - place things**: WYSIWYG level construction, object prefabs, tiles, start marker and layers.
- **DEFINE - object types**: level-local event/object type authoring, event definitions, animations, paths, masks and validation.

# Jazz Jackrabbit 1 DOS Data Level Editor v24

Standalone WYSIWYG-oriented GUI prototype for editing Jazz Jackrabbit 1 DOS/OpenJazz/reference levels.

## Run

```bash
python -m pip install pillow
python jazz1_dos_level_editor.py /path/to/JAZZ
```

## What v24 focuses on

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

Event definitions, animations, paths and masks are not global game-wide object definitions. They are shared tables inside each level. So v24 uses terms like **Object Types** and **Level Definitions** rather than treating event 17 as a universal object across the whole game.

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
