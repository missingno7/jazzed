# Development

## Setup

Install runtime and development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

For GUI work, use a Python installation with Tkinter. On Windows, the official desktop Python installer is usually the safest option.

## Checks

Run the main project check:

```bash
python tools/check_project.py
```

This does three things:

- compile-checks project Python files
- runs unit tests
- checks a lightweight import path

Run only tests:

```bash
python -m unittest discover -s tests
```

Run compile checks manually:

```bash
python -m compileall jazz1_dos_level_editor.py jazzed_editor tests tools
```

## Test Philosophy

Tests should be small and independent of real game data.

Good candidates:

- binary codec round trips
- signed byte behavior
- dataclass property behavior
- import boundary checks
- parser behavior against synthetic minimal data, if practical

Avoid tests that require original Jazz files unless they are explicitly local-only and skipped by default.

## Refactoring Guidance

When moving code:

- keep raw parsing separate from GUI concerns
- preserve `jazz1_dos_level_editor.py` as a launcher
- add tests for helpers before moving them
- run `python tools/check_project.py`
- avoid committing `__pycache__` or local data

## Common Failure Modes

### Wildcard Imports And Private Helpers

Python wildcard imports do not import names starting with `_`. If GUI code needs a private helper after a module split, import it explicitly or promote it to a public helper.

Example:

```python
from jazzed_editor.raw.codecs import signed_byte
```

### Importing GUI Too Early

Importing `jazzed_editor.raw.*` should not require Tkinter. Keep package `__init__` files lazy where needed so raw tests can run in clean environments.

### Local Data Leakage

Always check `git status --short` before committing. `game_data/` and `openjazz/` should remain local-only.
