"""A small Java world for the test server (the World page's browser checks):
level.dat with a seed and a killed dragon, and an overworld, Nether and End
in the 1.21 layout. Run it again to undo a reset."""
import os, sys, time
from pathlib import Path
sys.path.insert(0, os.environ.get("REPO", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from tests.classes.helpers.nbt_writer import byte, long, nbt_file

server = Path(sys.argv[1])
world = server / "world"
level = {"Data": {
    "LevelName": "world", "Version": {"Name": "1.21.4", "Id": 4189},
    "WorldGenSettings": {"seed": long(-4172144997902289642)},
    "LastPlayed": long(int(time.time() * 1000) - 3600 * 1000),
    "DragonFight": {"DragonKilled": byte(1), "PreviouslyKilled": byte(1)},
}}
written = [world / "level.dat"]
world.mkdir(parents=True, exist_ok=True)
(world / "level.dat").write_bytes(nbt_file(level))
for folder, size in (("region", 300_000), ("DIM-1/region", 120_000), ("DIM1/region", 80_000)):
    path = world / folder
    path.mkdir(parents=True, exist_ok=True)
    (path / "r.0.0.mca").write_bytes(os.urandom(size))
    written += [path.parent, path, path / "r.0.0.mca"]

# Owned like the server folder, so Crafty can delete them again
if hasattr(os, "chown"):
    owner = server.stat()
    for path in written:
        os.chown(path, owner.st_uid, owner.st_gid)
