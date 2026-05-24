# Jazzed Editor Package Layout

This package separates the Jazz Jackrabbit 1 DOS data layer from the Tk editor.

- `app.py` contains the command-line entrypoint and starts the GUI.
- `gui.py` contains the Tk application, editor state, canvas rendering, tools, and dialogs.
- `raw/` contains code that understands original JJ1 files and should not depend on Tk.
- `raw/constants.py` defines file-format and game constants.
- `raw/codecs.py` contains low-level binary helpers such as RLE and palette decoding.
- `raw/event_semantics.py` translates event bytes into editor-facing names, categories, and descriptions.
- `raw/models.py` defines level, tileset, sprite, event, animation, path, and bullet data classes.
- `raw/parser.py` loads levels, tilesets, sprites, and related raw game files.
- `raw/sprites.py` decodes individual JJ1 sprite frames.
- `raw_data.py` is a compatibility facade for older imports.

The top-level `jazz1_dos_level_editor.py` remains a compatibility launcher.
