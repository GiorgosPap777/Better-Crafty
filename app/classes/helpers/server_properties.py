"""Read and change the common settings in a Minecraft server.properties file.

Only the lines that change are rewritten; comments, ordering, unknown keys
and line endings are left as they were. Only settings that already appear
in the file are offered, so each Minecraft version shows what it supports.
"""

import re
import typing as t
from pathlib import Path

GAMEMODES_JAVA = ["survival", "creative", "adventure", "spectator"]
GAMEMODES_BEDROCK = ["survival", "creative", "adventure"]
DIFFICULTIES = ["peaceful", "easy", "normal", "hard"]

# key: (type, options)  type is "bool", "int", "enum" or "text".
# For "int", options is (min, max); for "enum", the allowed values.
JAVA_FIELDS: t.Dict[str, t.Tuple[str, t.Any]] = {
    "motd": ("text", None),
    "gamemode": ("enum", GAMEMODES_JAVA),
    "force-gamemode": ("bool", None),
    "difficulty": ("enum", DIFFICULTIES),
    "hardcore": ("bool", None),
    "pvp": ("bool", None),
    "max-players": ("int", (1, 100000)),
    "white-list": ("bool", None),
    "enforce-whitelist": ("bool", None),
    "online-mode": ("bool", None),
    "allow-flight": ("bool", None),
    "allow-nether": ("bool", None),
    "spawn-monsters": ("bool", None),
    "spawn-animals": ("bool", None),
    "spawn-npcs": ("bool", None),
    "spawn-protection": ("int", (0, 10000)),
    "view-distance": ("int", (3, 32)),
    "simulation-distance": ("int", (3, 32)),
    "enable-command-block": ("bool", None),
    "level-seed": ("text", None),
}

BEDROCK_FIELDS: t.Dict[str, t.Tuple[str, t.Any]] = {
    "server-name": ("text", None),
    "gamemode": ("enum", GAMEMODES_BEDROCK),
    "force-gamemode": ("bool", None),
    "difficulty": ("enum", DIFFICULTIES),
    "allow-cheats": ("bool", None),
    "max-players": ("int", (1, 100000)),
    "allow-list": ("bool", None),
    "online-mode": ("bool", None),
    "view-distance": ("int", (5, 96)),
    "tick-distance": ("int", (4, 12)),
    "level-seed": ("text", None),
}

MAX_TEXT_LENGTH = 1000
_UNICODE_ESCAPE = re.compile(r"(\\\\)|\\u([0-9a-fA-F]{4})")


def fields_for(server_type: str) -> t.Optional[t.Dict[str, t.Tuple[str, t.Any]]]:
    if server_type == "minecraft-java":
        return JAVA_FIELDS
    if server_type == "minecraft-bedrock":
        return BEDROCK_FIELDS
    return None


def _decode_java(value: str) -> str:
    """Turn \\uXXXX escapes into characters (e.g. \\u00A7 into the colour sign)."""
    return _UNICODE_ESCAPE.sub(
        lambda m: m.group(1) if m.group(1) else chr(int(m.group(2), 16)), value
    )


def _encode_java(value: str) -> str:
    """Write characters outside ASCII as \\uXXXX, which every Java version reads."""
    out = []
    for char in value:
        code = ord(char)
        if code < 128:
            out.append(char)
        elif code > 0xFFFF:
            # Characters outside the BMP are written as a UTF-16 surrogate pair
            code -= 0x10000
            out.append(f"\\u{0xD800 + (code >> 10):04x}")
            out.append(f"\\u{0xDC00 + (code & 0x3FF):04x}")
        else:
            out.append(f"\\u{code:04x}")
    return "".join(out)


def _split_line(line: str) -> t.Optional[t.Tuple[str, str]]:
    """Return (key, raw value) for a key=value line, or None."""
    stripped = line.strip()
    if not stripped or stripped[0] in "#!":
        return None
    match = re.match(r"\s*([^=:\s]+)\s*[=:][ \t\f]*(.*)$", line.rstrip("\r\n"))
    if not match:
        return None
    return match.group(1), match.group(2)


def _read_lines(path: Path) -> t.List[str]:
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read().splitlines(keepends=True)


def read_settings(path: Path, server_type: str) -> t.List[t.Dict[str, t.Any]]:
    """List the known settings found in the file, in the order of the field list."""
    fields = fields_for(server_type)
    if fields is None:
        return []
    values: t.Dict[str, str] = {}
    for line in _read_lines(path):
        parsed = _split_line(line)
        if parsed and parsed[0] in fields:
            values[parsed[0]] = parsed[1]

    settings = []
    for key, (kind, options) in fields.items():
        if key not in values:
            continue
        raw = values[key].strip() if kind != "text" else values[key]
        if server_type == "minecraft-java" and kind == "text":
            raw = _decode_java(raw)
        setting: t.Dict[str, t.Any] = {"key": key, "type": kind}
        if kind == "bool":
            setting["value"] = raw.lower() == "true"
        elif kind == "int":
            try:
                setting["value"] = int(raw)
            except ValueError:
                setting["value"] = None
            setting["min"], setting["max"] = options
        elif kind == "enum":
            setting["value"] = raw.lower()
            setting["options"] = list(options)
            # Old servers may store a number (0 = survival); keep it selectable
            if setting["value"] not in options:
                setting["options"].append(setting["value"])
        else:
            setting["value"] = raw
        settings.append(setting)
    return settings


def validate_changes(changes: t.Dict[str, t.Any], server_type: str) -> t.Dict[str, str]:
    """Check each change and return the text to write for it.

    Raises ValueError naming the first bad key.
    """
    fields = fields_for(server_type)
    if fields is None:
        raise ValueError("server type has no server.properties settings")
    out = {}
    for key, value in changes.items():
        if key not in fields:
            raise ValueError(f"{key} is not an editable setting")
        kind, options = fields[key]
        if kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
            out[key] = "true" if value else "false"
        elif kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{key} must be a whole number")
            low, high = options
            if not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
            out[key] = str(value)
        elif kind == "enum":
            if value not in options:
                raise ValueError(f"{key} must be one of {', '.join(options)}")
            out[key] = value
        else:
            if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
                raise ValueError(f"{key} must be text up to {MAX_TEXT_LENGTH} long")
            text = value.replace("\r\n", "\n").replace("\r", "\n")
            text = text.replace("\n", "\\n")
            if server_type == "minecraft-java":
                text = _encode_java(text)
            out[key] = text
    return out


def write_changes(path: Path, changes: t.Dict[str, str]) -> None:
    """Replace the values of the given keys, keeping every other line as is."""
    lines = _read_lines(path)
    for index, line in enumerate(lines):
        parsed = _split_line(line)
        if not parsed or parsed[0] not in changes:
            continue
        ending = line[len(line.rstrip("\r\n")) :]
        lines[index] = f"{parsed[0]}={changes[parsed[0]]}{ending}"
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write("".join(lines))
