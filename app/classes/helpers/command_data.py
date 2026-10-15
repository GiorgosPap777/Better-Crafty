"""Which Minecraft versions the Terminal can suggest commands for.

The data files are made by dev/command-data/generate.py from the game's own
command tree; the browser picks the one that fits the server's version.
"""

import functools
import os
import re
import typing as t
from pathlib import Path

DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "static"
    / "assets"
    / "data"
    / "commands"
)
_JAVA_FILE = re.compile(r"^java-(\d+(?:\.\d+){1,2})\.json$")


def _version_key(version: str) -> t.Tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@functools.lru_cache(maxsize=1)
def java_versions() -> t.Tuple[str, ...]:
    """Versions that have a command data file, oldest first."""
    try:
        names = os.listdir(DATA_DIR)
    except OSError:
        return ()
    found = [m.group(1) for m in map(_JAVA_FILE.match, names) if m]
    return tuple(sorted(found, key=_version_key))
