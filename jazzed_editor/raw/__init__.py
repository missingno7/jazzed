"""Raw Jazz Jackrabbit 1 DOS data parsing and model layer.

The lightweight helpers and data classes are imported eagerly. Pillow-backed
parser and sprite helpers are loaded lazily so basic checks can run before
runtime GUI dependencies are installed.
"""

from .constants import *
from .event_semantics import *
from .codecs import *
from .models import *
from .sounds import *

__all__ = [
    "JJ1Parser",
]


def __getattr__(name: str):
    if name == "JJ1Parser":
        from .parser import JJ1Parser

        return JJ1Parser
    raise AttributeError(name)

