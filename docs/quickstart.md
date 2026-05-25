# Quickstart

## 1. Install Python

Use Python 3.10 or newer. On Windows, the standard desktop Python installer is recommended because it includes Tkinter, which Jazzed uses for the GUI.

Check your version:

```bash
python --version
```

## 2. Install Dependencies

From the repository root:

```bash
python -m pip install -r requirements.txt
```

For development checks:

```bash
python -m pip install -r requirements-dev.txt
```

## 3. Add Local Game Data

Create or use the existing `game_data/` folder and copy files from a legally owned DOS Jazz Jackrabbit 1 installation into it.

Expected examples:

```text
game_data/
  LEVEL0.000
  LEVEL1.000
  BLOCKS.000
  SPRITES.000
  MAINCHAR.000
  SOUNDS.000
```

The exact file set depends on your Jazz release and episode data.

## 4. Run The Editor

Default local workflow:

```bash
python jazz1_dos_level_editor.py
```

This opens `game_data/`.

To use another directory:

```bash
python jazz1_dos_level_editor.py D:\Games\DOS\JAZZ
```

## 5. Run Checks

Before committing changes:

```bash
python tools/check_project.py
```

This compiles project Python files, runs unit tests, and checks a few import assumptions.
