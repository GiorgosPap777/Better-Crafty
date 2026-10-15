"""Read and change the -Xms / -Xmx memory flags in a Java start command.

Only the numbers in those two flags are touched, so users who may not edit
the start command itself can still change how much memory the server gets.
"""

import re
import typing as t

_FLAG = re.compile(r"(?<!\S)-Xm([sx])(\d+)([kKmMgG]?)(?!\S)")
_UNIT_TO_MIB = {"k": 1 / 1024, "m": 1, "g": 1024, "": 1 / (1024 * 1024)}

MIN_MIB = 128
MAX_MIB = 1024 * 1024  # 1 TiB


def read_memory(command: str) -> t.Dict[str, t.Optional[int]]:
    """Return {"mem_min": MiB, "mem_max": MiB}; None where the flag is missing."""
    found: t.Dict[str, t.Optional[int]] = {"mem_min": None, "mem_max": None}
    for match in _FLAG.finditer(command or ""):
        mib = int(round(int(match.group(2)) * _UNIT_TO_MIB[match.group(3).lower()]))
        found["mem_min" if match.group(1) == "s" else "mem_max"] = mib
    return found


def set_memory(
    command: str, mem_min: t.Optional[int] = None, mem_max: t.Optional[int] = None
) -> str:
    """Write new -Xms / -Xmx values (in MiB) into the command.

    Raises ValueError if a value is out of range, if minimum is above
    maximum, or if the command has no such flag to change.
    """
    current = read_memory(command)
    new_min = current["mem_min"] if mem_min is None else mem_min
    new_max = current["mem_max"] if mem_max is None else mem_max
    for name, value in (("mem_min", mem_min), ("mem_max", mem_max)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be a whole number of MiB")
        if not MIN_MIB <= value <= MAX_MIB:
            raise ValueError(f"{name} must be between {MIN_MIB} and {MAX_MIB} MiB")
        if current[name] is None:
            flag = "-Xms" if name == "mem_min" else "-Xmx"
            raise ValueError(f"the start command has no {flag} flag to change")
    if new_min is not None and new_max is not None and new_min > new_max:
        raise ValueError("minimum memory cannot be more than maximum memory")

    def replace(match: re.Match) -> str:
        value = new_min if match.group(1) == "s" else new_max
        return f"-Xm{match.group(1)}{value}M"

    return _FLAG.sub(replace, command)
