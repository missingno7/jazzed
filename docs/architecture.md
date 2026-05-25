# Architecture

Jazzed is split into a GUI layer and a raw data layer.

## Top-Level Entrypoints

- `jazz1_dos_level_editor.py` is a compatibility launcher for older workflows.
- `jazzed_editor/app.py` owns command-line argument parsing and starts the GUI.
- `jazzed_editor/__init__.py` exposes a lazy `main()` wrapper without importing the GUI immediately.

## GUI Layer

`jazzed_editor/gui.py` contains the Tk application shell:

- window construction
- editor state initialization
- main layout wiring
- mixin composition

Feature-specific GUI behavior lives in `jazzed_editor/gui_parts/`:

- `overview.py`: overview/jump helper tabs
- `assets.py`: assets browser tabs and previews
- `build_tabs.py`: BUILD workspace tabs and LEVEL LOCAL summary/masks tab construction
- `event_defs.py`: level-local event definition editor
- `level_local.py`: animations, bullets, paths, masks editor logic
- `level_io.py`: load/save, dirty state, undo/redo, validation, metadata
- `objects.py`: object/event palettes, object lists, replacements
- `rendering.py`: map rendering, atlas rendering, overlays, background/collision caches
- `editing.py`: canvas input, painting, picking, erasing, selection

Each module defines a mixin class. `LevelEditorApp` inherits from those mixins plus `tk.Tk`. This keeps one application object while letting related behavior live in smaller files.

Future GUI refactors should keep moving toward smaller modules. If a mixin grows too large, split it again by user workflow.

## Raw Data Layer

`jazzed_editor/raw/` contains the original DOS data model and binary parsing code. It should not import Tkinter.

Modules:

- `constants.py`: dimensions, table sizes, IDs, and format constants
- `codecs.py`: RLE, palettes, little-endian helpers, signed byte conversion
- `event_semantics.py`: human-readable event meanings and categories
- `models.py`: dataclasses for level, tileset, sprites, events, animations, paths, bullets, and save serialization
- `parser.py`: level, tileset, and sprite loading
- `sounds.py`: `SOUNDS.000` parsing and WAV conversion
- `sprites.py`: sprite frame decoding helpers

`jazzed_editor/raw_data.py` is a compatibility facade for old imports.

## Import Boundary Rules

The raw layer may depend on Pillow for image-bearing models and parsers, but it must not depend on Tk.

The GUI layer may import raw data modules, Tkinter, Pillow, and desktop-specific helpers.

Tests include an import-boundary check to catch accidental `tkinter` imports in `jazzed_editor/raw/`.

## Data Flow

```text
game_data/ files
  -> JJ1Parser
  -> LevelData / TilesetData / SpriteSetData
  -> LevelEditorApp state
  -> Tk canvas/widgets
  -> LevelData.save_as()
  -> modified LEVEL file
```

## Compatibility Choices

The repository keeps `jazz1_dos_level_editor.py` as a thin launcher so existing commands still work:

```bash
python jazz1_dos_level_editor.py
```

New code should prefer package imports from `jazzed_editor`.
