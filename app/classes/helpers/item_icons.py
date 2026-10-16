"""Pictures of Minecraft items for the player inventory.

Minecraft's textures belong to Mojang, so they cannot ship with Crafty. When a
super user asks for them, this downloads the game's client jar from Mojang
(checked against the sha1 Mojang publishes), draws a 64x64 picture of every
item from the models and textures inside it, and keeps only the pictures, in
app/config/item_icons/. The jar is deleted afterwards.

The drawing follows the game's rules for items in an inventory slot. Flat items
are their texture layers on top of each other. Blocks and other 3D models are
turned by the model's "gui" display settings and lit like in the game. Chests,
shulker boxes, mob heads and shields, which the game draws with entity models,
are built from their entity textures. Items drawn in other special ways
(banners, decorated pots...) get no picture; the page shows their name.
"""

import datetime
import hashlib
import io
import json
import logging
import math
import re
import shutil
import tempfile
import threading
import typing as t
import zipfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
SIZE = 64
# 3D models are drawn this many times bigger, then shrunk for smooth edges
OVERSAMPLE = 4
ASSETS = "assets/minecraft/"
NAME_RE = re.compile(r"^[a-z0-9_]{1,64}$")
MAX_DEPTH = 32
# Pictures that are not items start with "_": empty armour slots, the glint,
# and the health, food and experience bars
SPRITES = {
    "_slot_helmet": "textures/gui/sprites/container/slot/helmet.png",
    "_slot_chestplate": "textures/gui/sprites/container/slot/chestplate.png",
    "_slot_leggings": "textures/gui/sprites/container/slot/leggings.png",
    "_slot_boots": "textures/gui/sprites/container/slot/boots.png",
    "_slot_shield": "textures/gui/sprites/container/slot/shield.png",
    "_glint": "textures/misc/enchanted_glint_item.png",
    "_heart_container": "textures/gui/sprites/hud/heart/container.png",
    "_heart_full": "textures/gui/sprites/hud/heart/full.png",
    "_heart_half": "textures/gui/sprites/hud/heart/half.png",
    "_food_empty": "textures/gui/sprites/hud/food_empty.png",
    "_food_full": "textures/gui/sprites/hud/food_full.png",
    "_food_half": "textures/gui/sprites/hud/food_half.png",
    "_xp_background": "textures/gui/sprites/hud/experience_bar_background.png",
    "_xp_progress": "textures/gui/sprites/hud/experience_bar_progress.png",
}
# Light directions of the game's inventory lighting for 3D items
LIGHTS = ((-0.2225, 0.1715, 0.9597), (-0.215, 0.9718, 0.0966))

Matrix = t.List[t.List[float]]
Point = t.Tuple[float, float, float]


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _strip(ref) -> str:
    """'minecraft:block/stone' -> 'block/stone'."""
    if not isinstance(ref, str):
        return ""
    return ref.split(":", 1)[1] if ":" in ref else ref


def _numbers(value, count: int, default: float) -> t.List[float]:
    if (
        isinstance(value, list)
        and len(value) == count
        and all(isinstance(v, (int, float)) for v in value)
    ):
        return [float(v) for v in value]
    return [default] * count


# --------------------------------------------------------------------------
# 4x4 matrices
# --------------------------------------------------------------------------


def _identity() -> Matrix:
    return [[float(i == j) for j in range(4)] for i in range(4)]


def _mul(a: Matrix, b: Matrix) -> Matrix:
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)
    ]


def _translate(x: float, y: float, z: float) -> Matrix:
    m = _identity()
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


def _scale(x: float, y: float, z: float) -> Matrix:
    m = _identity()
    m[0][0], m[1][1], m[2][2] = x, y, z
    return m


def _rotate(axis: str, degrees: float) -> Matrix:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    m = _identity()
    if axis == "x":
        m[1][1], m[1][2], m[2][1], m[2][2] = c, -s, s, c
    elif axis == "y":
        m[0][0], m[0][2], m[2][0], m[2][2] = c, s, -s, c
    else:
        m[0][0], m[0][1], m[1][0], m[1][1] = c, -s, s, c
    return m


def _quaternion(value) -> Matrix:
    """A rotation given as [x, y, z, w] or as {"angle": radians, "axis": [...]}."""
    if isinstance(value, dict):
        angle = value.get("angle", 0)
        angle = angle if isinstance(angle, (int, float)) else 0
        axis = _numbers(value.get("axis"), 3, 0.0)
        length = math.sqrt(sum(a * a for a in axis)) or 1.0
        half = math.sin(angle / 2) / length
        value = [axis[0] * half, axis[1] * half, axis[2] * half, math.cos(angle / 2)]
    x, y, z, w = _numbers(value, 4, 0.0) if isinstance(value, list) else (0, 0, 0, 1)
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length == 0:
        return _identity()
    x, y, z, w = x / length, y / length, z / length, w / length
    m = _identity()
    m[0][:3] = [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)]
    m[1][:3] = [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)]
    m[2][:3] = [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]
    return m


def _transformation(value) -> Matrix:
    """The optional "transformation" of an item model, as a matrix."""
    if isinstance(value, list) and len(value) == 16:
        if all(isinstance(v, (int, float)) for v in value):
            return [
                [float(v) for v in value[row * 4 : row * 4 + 4]] for row in range(4)
            ]
        return _identity()
    value = _dict(value)
    matrix = _translate(*_numbers(value.get("translation"), 3, 0.0))
    matrix = _mul(matrix, _quaternion(value.get("left_rotation")))
    matrix = _mul(matrix, _scale(*_numbers(value.get("scale"), 3, 1.0)))
    return _mul(matrix, _quaternion(value.get("right_rotation")))


def _display(gui: dict) -> Matrix:
    """A model's "gui" display settings, as the game applies them."""
    rotation = _numbers(gui.get("rotation"), 3, 0.0)
    translation = [
        max(-80.0, min(80.0, v)) / 16 for v in _numbers(gui.get("translation"), 3, 0.0)
    ]
    scale = [max(-4.0, min(4.0, v)) for v in _numbers(gui.get("scale"), 3, 1.0)]
    matrix = _translate(*translation)
    for axis, degrees in zip("xyz", rotation):
        matrix = _mul(matrix, _rotate(axis, degrees))
    return _mul(matrix, _scale(*scale))


def _apply(m: Matrix, p: Point) -> Point:
    return tuple(  # type: ignore[return-value]
        m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3)
    )


def _determinant(m: Matrix) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


# --------------------------------------------------------------------------
# Reading the jar
# --------------------------------------------------------------------------


class Assets:
    """Models and textures from a Minecraft client jar (or a test zip)."""

    def __init__(self, archive: zipfile.ZipFile):
        self.archive = archive
        self._json: t.Dict[str, t.Any] = {}
        self._images: t.Dict[str, t.Optional[Image.Image]] = {}
        self._models: t.Dict[str, t.Optional[dict]] = {}

    def json(self, path: str):
        if path not in self._json:
            try:
                self._json[path] = json.loads(self.archive.read(ASSETS + path))
            except (KeyError, ValueError):
                self._json[path] = None
        return self._json[path]

    def image(self, path: str) -> t.Optional[Image.Image]:
        """A PNG as RGBA; for an animated texture, its first frame."""
        if path not in self._images:
            try:
                with Image.open(io.BytesIO(self.archive.read(ASSETS + path))) as img:
                    img = img.convert("RGBA")
            except (KeyError, OSError, ValueError, Image.DecompressionBombError):
                img = None
            if img is not None and img.height > img.width:
                if ASSETS + path + ".mcmeta" in self.archive.namelist():
                    img = img.crop((0, 0, img.width, img.width))
            self._images[path] = img
        return self._images[path]

    def texture(self, ref: str) -> t.Optional[Image.Image]:
        name = _strip(ref)
        if not name or ".." in name:
            return None
        return self.image(f"textures/{name}.png")

    def model(self, ref) -> t.Optional[dict]:
        """A block or item model with what it takes from its parents."""
        name = _strip(ref)
        if name not in self._models:
            self._models[name] = self._load_model(name)
        return self._models[name]

    def _load_model(self, name: str) -> t.Optional[dict]:
        textures: t.Dict[str, t.Any] = {}
        elements = None
        gui = None
        light = None
        generated = False
        seen: t.Set[str] = set()
        current: t.Optional[str] = name
        while current and current not in seen and len(seen) < MAX_DEPTH:
            if current == "builtin/generated":
                generated = True
                break
            data = self.json(f"models/{current}.json")
            if not isinstance(data, dict):
                break
            seen.add(current)
            for key, value in _dict(data.get("textures")).items():
                textures.setdefault(key, value)
            if elements is None and isinstance(data.get("elements"), list):
                elements = data["elements"]
            if gui is None and isinstance(_dict(data.get("display")).get("gui"), dict):
                gui = data["display"]["gui"]
            if light is None and data.get("gui_light") in ("front", "side"):
                light = data["gui_light"]
            current = _strip(data.get("parent")) or None
        if not seen:
            return None
        return {
            "textures": textures,
            "elements": elements or [],
            "gui": gui or {},
            "light": light or "side",
            "generated": generated and elements is None,
        }


def _texture_ref(textures: dict, ref) -> t.Optional[str]:
    """Follow "#name" references in a model's textures to a texture path."""
    for _ in range(MAX_DEPTH):
        if isinstance(ref, dict):
            ref = ref.get("sprite")
        if not isinstance(ref, str):
            return None
        if not ref.startswith("#"):
            return ref
        ref = textures.get(ref[1:])
    return None


def _tint_color(assets: Assets, tint) -> t.Optional[t.Tuple[int, int, int]]:
    tint = _dict(tint)
    if _strip(tint.get("type")) == "grass":
        colormap = assets.image("textures/colormap/grass.png")
        if colormap is None:
            return None
        temperature = tint.get("temperature", 0.5)
        downfall = tint.get("downfall", 1.0)
        temperature = min(1.0, max(0.0, float(temperature)))
        downfall = min(1.0, max(0.0, float(downfall))) * temperature
        x = int((1 - temperature) * (colormap.width - 1))
        y = int((1 - downfall) * (colormap.height - 1))
        return colormap.getpixel((x, y))[:3]
    value = tint.get("value", tint.get("default"))
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        value &= 0xFFFFFF
        return (value >> 16 & 255, value >> 8 & 255, value & 255)
    if isinstance(value, list) and len(value) == 3:
        return tuple(int(255 * min(1.0, max(0.0, float(v)))) for v in value)  # type: ignore[return-value]
    return None


def _colored(img: Image.Image, color=None, light: float = 1.0) -> Image.Image:
    """Multiply a texture's colours by a tint and a light level."""
    red, green, blue = color or (255, 255, 255)
    if (red, green, blue) == (255, 255, 255) and light >= 1.0:
        return img
    table = []
    for factor in (red / 255 * light, green / 255 * light, blue / 255 * light):
        table += [min(255, int(v * factor + 0.5)) for v in range(256)]
    return img.point(table + list(range(256)))


# --------------------------------------------------------------------------
# Item definitions
# --------------------------------------------------------------------------


def _layers(node, matrix: Matrix, found: list, depth: int = 0) -> None:
    """What an item definition draws in an inventory slot, in drawing order."""
    if not isinstance(node, dict) or depth > MAX_DEPTH:
        return
    if "transformation" in node:
        matrix = _mul(matrix, _transformation(node["transformation"]))
    kind = _strip(node.get("type"))
    if kind == "model":
        found.append(("model", node.get("model"), _list(node.get("tints")), matrix))
    elif kind == "special":
        found.append(("special", node.get("base"), _dict(node.get("model")), matrix))
    elif kind == "composite":
        for child in _list(node.get("models")):
            _layers(child, matrix, found, depth + 1)
    elif kind == "condition":
        _layers(node.get("on_false"), matrix, found, depth + 1)
    elif kind == "select":
        cases = [_dict(case) for case in _list(node.get("cases"))]
        chosen = None
        if _strip(node.get("property")) == "display_context":
            for case in cases:
                when = case.get("when")
                if "gui" in (when if isinstance(when, list) else [when]):
                    chosen = case.get("model")
                    break
        if chosen is None:
            chosen = node.get("fallback") or (cases[0].get("model") if cases else None)
        _layers(chosen, matrix, found, depth + 1)
    elif kind == "range_dispatch":
        entries = [_dict(entry) for entry in _list(node.get("entries"))]
        chosen = node.get("fallback") or (entries[0].get("model") if entries else None)
        _layers(chosen, matrix, found, depth + 1)


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------


class Face(t.NamedTuple):
    corners: t.Tuple[Point, Point, Point]  # top left, top right, bottom left
    texture: Image.Image
    uv: t.Tuple[t.Tuple[float, float], ...]  # texture pixels at the same corners
    shade: bool


def _flat(assets: Assets, model: dict, tints: list) -> t.Optional[Image.Image]:
    """A flat item: its texture layers on top of each other."""
    layers = []
    for index in range(16):
        ref = _texture_ref(model["textures"], f"#layer{index}")
        if ref is None:
            break
        texture = assets.texture(ref)
        if texture is not None:
            color = _tint_color(assets, tints[index]) if index < len(tints) else None
            layers.append(_colored(texture, color))
    if not layers:
        return None
    side = max(layer.width for layer in layers)
    canvas = Image.new("RGBA", (side, side))
    for layer in layers:
        if layer.size != (side, side):
            layer = layer.resize((side, side), Image.Resampling.NEAREST)
        canvas.alpha_composite(layer)

    gui = model["gui"]
    scale = abs(max(-4.0, min(4.0, _numbers(gui.get("scale"), 3, 1.0)[0])))
    move_x, move_y, _ = _numbers(gui.get("translation"), 3, 0.0)
    width = round(SIZE * scale)
    if width <= 0:
        return None
    picture = Image.new("RGBA", (SIZE, SIZE))
    canvas = canvas.resize((width, width), Image.Resampling.NEAREST)
    left = round((SIZE - width) / 2 + move_x * SIZE / 16)
    top = round((SIZE - width) / 2 - move_y * SIZE / 16)
    picture.paste(canvas, (left, top), canvas)
    return picture


def _block_corners(direction: str, low: Point, high: Point):
    x1, y1, z1 = low
    x2, y2, z2 = high
    return {
        "north": ((x2, y2, z1), (x1, y2, z1), (x2, y1, z1)),
        "south": ((x1, y2, z2), (x2, y2, z2), (x1, y1, z2)),
        "east": ((x2, y2, z2), (x2, y2, z1), (x2, y1, z2)),
        "west": ((x1, y2, z1), (x1, y2, z2), (x1, y1, z1)),
        "up": ((x1, y2, z1), (x2, y2, z1), (x1, y2, z2)),
        "down": ((x1, y1, z2), (x2, y1, z2), (x1, y1, z1)),
    }[direction]


def _default_uv(direction: str, low: Point, high: Point) -> t.List[float]:
    x1, y1, z1 = low
    x2, y2, z2 = high
    return {
        "north": [16 - x2, 16 - y2, 16 - x1, 16 - y1],
        "south": [x1, 16 - y2, x2, 16 - y1],
        "east": [16 - z2, 16 - y2, 16 - z1, 16 - y1],
        "west": [z1, 16 - y2, z2, 16 - y1],
        "up": [x1, z1, x2, z2],
        "down": [x1, 16 - z2, x2, 16 - z1],
    }[direction]


def _element_matrix(rotation) -> Matrix:
    """An element's own rotation around its origin, in model pixels."""
    rotation = _dict(rotation)
    origin = _numbers(rotation.get("origin"), 3, 8.0)
    turn = _identity()
    if rotation.get("axis") in ("x", "y", "z"):
        axis = rotation["axis"]
        angle = rotation.get("angle", 0)
        angle = float(angle) if isinstance(angle, (int, float)) else 0.0
        turn = _rotate(axis, angle)
        if rotation.get("rescale") and abs(math.cos(math.radians(angle))) > 1e-6:
            grow = 1 / abs(math.cos(math.radians(angle)))
            turn = _mul(turn, _scale(*(1.0 if a == axis else grow for a in "xyz")))
    else:
        for axis in "xyz":
            angle = rotation.get(axis, 0)
            if isinstance(angle, (int, float)) and angle:
                turn = _mul(turn, _rotate(axis, float(angle)))
    matrix = _mul(_translate(*origin), turn)
    return _mul(matrix, _translate(-origin[0], -origin[1], -origin[2]))


def _uv_corners(uv: t.List[float], rotation: int, width: int, height: int):
    """Texture pixels at a face's top left, top right and bottom left corners."""
    u1, v1, u2, v2 = (
        uv[0] * width / 16,
        uv[1] * height / 16,
        uv[2] * width / 16,
        uv[3] * height / 16,
    )
    ring = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
    turns = (rotation // 90) % 4
    # Top left, top right, bottom left are corners 0, 1 and 3 of the ring
    return tuple(ring[(corner - turns) % 4] for corner in (0, 1, 3))


def _model_faces(assets: Assets, model: dict, tints: list, matrix: Matrix) -> list:
    """The faces of a block-style model, placed by the given matrix (pixels in)."""
    faces = []
    for element in model["elements"]:
        element = _dict(element)
        low = tuple(_numbers(element.get("from"), 3, 0.0))
        high = tuple(_numbers(element.get("to"), 3, 16.0))
        place = _mul(matrix, _element_matrix(element.get("rotation")))
        shade = element.get("shade", True) is not False
        for direction, face in _dict(element.get("faces")).items():
            face = _dict(face)
            if direction not in ("north", "south", "east", "west", "up", "down"):
                continue
            # A face names one of the model's textures, with or without "#"
            ref = face.get("texture")
            if isinstance(ref, str) and not ref.startswith("#"):
                ref = "#" + ref
            ref = _texture_ref(model["textures"], ref)
            texture = assets.texture(ref) if ref else None
            if texture is None:
                continue
            tint = face.get("tintindex")
            if isinstance(tint, int) and not isinstance(tint, bool):
                if 0 <= tint < len(tints):
                    texture = _colored(texture, _tint_color(assets, tints[tint]))
            uv = face.get("uv")
            if not (isinstance(uv, list) and len(uv) == 4):
                uv = _default_uv(direction, low, high)
            uv = _numbers(uv, 4, 0.0)
            turn = face.get("rotation", 0)
            turn = turn if isinstance(turn, int) and not isinstance(turn, bool) else 0
            corners = tuple(
                _apply(place, p) for p in _block_corners(direction, low, high)
            )
            faces.append(
                Face(
                    corners,  # type: ignore[arg-type]
                    texture,
                    _uv_corners(uv, turn, texture.width, texture.height),
                    shade,
                )
            )
    return faces


def _box(origin, size, tex_offset, inflate: float = 0.0):
    """The six faces of an entity model cube, like the game's ModelPart.Cube.

    Gives (top left, top right, bottom left) corners in model pixels and the
    texture pixels at those corners, for a texture of the model's own size.
    """
    x, y, z = origin
    dx, dy, dz = size
    u, v = tex_offset
    lo = (x - inflate, y - inflate, z - inflate)
    hi = (x + dx + inflate, y + dy + inflate, z + dz + inflate)
    p = [
        (lo[0], lo[1], lo[2]),
        (hi[0], lo[1], lo[2]),
        (hi[0], hi[1], lo[2]),
        (lo[0], hi[1], lo[2]),
        (lo[0], lo[1], hi[2]),
        (hi[0], lo[1], hi[2]),
        (hi[0], hi[1], hi[2]),
        (lo[0], hi[1], hi[2]),
    ]
    us = (u, u + dz, u + dz + dx, u + dz + 2 * dx, u + 2 * dz + dx, u + 2 * dz + 2 * dx)
    vs = (v, v + dz, v + dz + dy)
    polygons = (
        ((5, 4, 0, 1), us[1], vs[0], us[2], vs[1]),
        ((2, 3, 7, 6), us[2], vs[1], us[3], vs[0]),
        ((0, 4, 7, 3), us[0], vs[1], us[1], vs[2]),
        ((1, 0, 3, 2), us[1], vs[1], us[2], vs[2]),
        ((5, 1, 2, 6), us[2], vs[1], us[4], vs[2]),
        ((4, 5, 6, 7), us[4], vs[1], us[5], vs[2]),
    )
    for corners, u1, v1, u2, v2 in polygons:
        # The game gives the second vertex the top left of the texture area
        yield (p[corners[1]], p[corners[0]], p[corners[2]]), (
            (u1, v1),
            (u2, v1),
            (u1, v2),
        )


# Entity models: (texture, texture size, [(origin, size, texture offset, inflate)])
CHEST = [
    ((1, 0, 1), (14, 10, 14), (0, 19), 0.0),
    ((1, 9, 1), (14, 5, 14), (0, 0), 0.0),
    ((7, 7, 15), (2, 4, 1), (0, 0), 0.0),
]
SHULKER = [
    ((-8, 8, -8), (16, 12, 16), (0, 0), 0.0),
    ((-8, 16, -8), (16, 8, 16), (0, 28), 0.0),
]
HEAD = [((-4, -8, -4), (8, 8, 8), (0, 0), 0.0)]
HEAD_WITH_HAT = HEAD + [((-4, -8, -4), (8, 8, 8), (32, 0), 0.25)]
SHIELD = [
    ((-6, -11, -2), (12, 22, 1), (0, 0), 0.0),
    ((-1, -3, -1), (2, 6, 6), (26, 0), 0.0),
]
CONDUIT = [((-3, -3, -3), (6, 6, 6), (0, 0), 0.0)]
HEADS = {
    "skeleton": ("entity/skeleton/skeleton", (64, 32), HEAD),
    "wither_skeleton": ("entity/skeleton/wither_skeleton", (64, 32), HEAD),
    "zombie": ("entity/zombie/zombie", (64, 64), HEAD_WITH_HAT),
    "creeper": ("entity/creeper/creeper", (64, 32), HEAD),
}


def _special_model(spec: dict):
    """Texture and boxes for the entity-drawn items this can draw."""
    kind = _strip(spec.get("type"))
    texture = _strip(spec.get("texture"))
    if texture and not NAME_RE.match(texture):
        return None
    if kind == "chest" and texture:
        return f"entity/chest/{texture}", (64, 64), CHEST
    if kind == "shulker_box" and texture:
        return f"entity/shulker/{texture}", (64, 64), SHULKER
    if kind == "head":
        return HEADS.get(_strip(spec.get("kind")))
    if kind == "player_head":
        return "entity/player/wide/steve", (64, 64), HEAD_WITH_HAT
    if kind == "shield":
        return "entity/shield/shield_base_nopattern", (64, 64), SHIELD
    if kind == "conduit":
        return "entity/conduit/base", (32, 16), CONDUIT
    return None


def _special_faces(assets: Assets, spec: dict, matrix: Matrix) -> t.Optional[list]:
    found = _special_model(spec)
    if found is None:
        return None
    name, (width, height), boxes = found
    texture = assets.texture(name)
    if texture is None:
        return None
    sx, sy = texture.width / width, texture.height / height
    faces = []
    for origin, size, offset, inflate in boxes:
        for corners, uv in _box(origin, size, offset, inflate):
            faces.append(
                Face(
                    tuple(_apply(matrix, c) for c in corners),  # type: ignore[arg-type]
                    texture,
                    tuple((u * sx, v * sy) for u, v in uv),
                    True,
                )
            )
    return faces


def _light(normal: Point) -> float:
    total = sum(max(0.0, sum(a * b for a, b in zip(light, normal))) for light in LIGHTS)
    return min(1.0, 0.4 + 0.6 * total)


def _padded_crop(texture: Image.Image, uv) -> t.Tuple[Image.Image, float, float]:
    """The texture area a face uses, with its edge pixels repeated around it.

    Faces are drawn slightly past their edges, so this keeps neighbouring parts
    of the texture (or nothing) from showing there.
    """
    us = [u for u, _ in uv] + [uv[1][0] + uv[2][0] - uv[0][0]]
    vs = [v for _, v in uv] + [uv[1][1] + uv[2][1] - uv[0][1]]
    left = max(0, min(texture.width - 1, math.floor(min(us) + 1e-6)))
    top = max(0, min(texture.height - 1, math.floor(min(vs) + 1e-6)))
    right = max(left + 1, min(texture.width, math.ceil(max(us) - 1e-6)))
    bottom = max(top + 1, min(texture.height, math.ceil(max(vs) - 1e-6)))
    area = texture.crop((left, top, right, bottom))
    width, height = area.size
    padded = Image.new("RGBA", (width + 2, height + 2))
    padded.paste(area, (1, 1))
    padded.paste(area.crop((0, 0, width, 1)), (1, 0))
    padded.paste(area.crop((0, height - 1, width, height)), (1, height + 1))
    padded.paste(padded.crop((1, 0, 2, height + 2)), (0, 0))
    padded.paste(padded.crop((width, 0, width + 1, height + 2)), (width + 1, 0))
    return padded, left - 1, top - 1


def _draw_faces(faces: t.List[Face], light: bool) -> t.Optional[Image.Image]:
    size = SIZE * OVERSAMPLE
    canvas = Image.new("RGBA", (size, size))
    drawn = []
    for face in faces:
        top_left, top_right, bottom_left = face.corners
        across = [b - a for a, b in zip(top_left, top_right)]
        down = [b - a for a, b in zip(top_left, bottom_left)]
        normal = (
            down[1] * across[2] - down[2] * across[1],
            down[2] * across[0] - down[0] * across[2],
            down[0] * across[1] - down[1] * across[0],
        )
        length = math.sqrt(sum(n * n for n in normal))
        if length < 1e-9 or normal[2] / length <= 1e-4:
            continue
        # The middle of the face is halfway between two opposite corners
        depth = top_right[2] + bottom_left[2]
        drawn.append((depth, face, tuple(n / length for n in normal)))
    drawn.sort(key=lambda item: item[0])
    for _, face, normal in drawn:
        level = _light(normal) if light and face.shade else 1.0
        _draw_face(canvas, face, level)
    if not drawn:
        return None
    small = canvas.convert("RGBa").reduce(OVERSAMPLE).convert("RGBA")
    return small if small.getbbox() else None


def _draw_face(canvas: Image.Image, face: Face, level: float) -> None:
    size = canvas.width
    screen = [((x + 0.5) * size, (0.5 - y) * size) for x, y, _ in face.corners]
    (x0, y0), (x1, y1), (x2, y2) = screen
    corners = [(x0, y0), (x1, y1), (x1 + x2 - x0, y1 + y2 - y0), (x2, y2)]
    left = max(0, math.floor(min(x for x, _ in corners)))
    top = max(0, math.floor(min(y for _, y in corners)))
    right = min(size, math.ceil(max(x for x, _ in corners)))
    bottom = min(size, math.ceil(max(y for _, y in corners)))
    if right <= left or bottom <= top:
        return
    across, down = (x1 - x0, y1 - y0), (x2 - x0, y2 - y0)
    det = across[0] * down[1] - across[1] * down[0]
    if abs(det) < 1e-9:
        return
    texture, u0, v0 = _padded_crop(face.texture, face.uv)
    texture = _colored(texture, None, level)
    (tu0, tv0), (tu1, tv1), (tu2, tv2) = [(u - u0, v - v0) for u, v in face.uv]

    # Screen point -> how far along the face's two edges (a, b) -> texture
    def along(px: float, py: float) -> t.Tuple[float, float]:
        dx, dy = px - x0, py - y0
        return (dx * down[1] - dy * down[0]) / det, (
            across[0] * dy - across[1] * dx
        ) / det

    a_o, b_o = along(left, top)
    a_x, b_x = [p - q for p, q in zip(along(left + 1, top), (a_o, b_o))]
    a_y, b_y = [p - q for p, q in zip(along(left, top + 1), (a_o, b_o))]
    du = (tu1 - tu0, tu2 - tu0)
    dv = (tv1 - tv0, tv2 - tv0)
    coefficients = (
        du[0] * a_x + du[1] * b_x,
        du[0] * a_y + du[1] * b_y,
        tu0 + du[0] * a_o + du[1] * b_o,
        dv[0] * a_x + dv[1] * b_x,
        dv[0] * a_y + dv[1] * b_y,
        tv0 + dv[0] * a_o + dv[1] * b_o,
    )
    box = (right - left, bottom - top)
    piece = texture.transform(
        box, Image.Transform.AFFINE, coefficients, resample=Image.Resampling.NEAREST
    )
    mask = Image.new("L", box)
    ImageDraw.Draw(mask).polygon([(x - left, y - top) for x, y in corners], fill=255)
    alpha = piece.getchannel("A")
    piece.putalpha(Image.composite(alpha, mask, mask))
    canvas.alpha_composite(piece, (left, top))


def render_item(assets: Assets, name: str) -> t.Optional[Image.Image]:
    """A SIZE x SIZE picture of an item as it looks in an inventory slot."""
    definition = assets.json(f"items/{name}.json")
    if not isinstance(definition, dict):
        return None
    layers: list = []
    _layers(definition.get("model"), _identity(), layers)
    flat_pictures = []
    faces: t.List[Face] = []
    light = False
    for kind, ref, extra, matrix in layers:
        model = assets.model(ref)
        if model is None:
            continue
        if kind == "model" and model["generated"]:
            picture = _flat(assets, model, extra)
            if picture is not None:
                flat_pictures.append(picture)
            continue
        # Model pixels -> blocks -> the item's own transformation -> centred
        # on the slot -> the model's inventory display settings
        place = _mul(_display(model["gui"]), _translate(-0.5, -0.5, -0.5))
        place = _mul(_mul(place, matrix), _scale(1 / 16, 1 / 16, 1 / 16))
        if kind == "model":
            found = _model_faces(assets, model, extra, place)
        else:
            found = _special_faces(assets, extra, place) or []
        if _determinant(place) < 0:
            # A mirroring transformation turns faces inside out
            found = [
                face._replace(
                    corners=(face.corners[0], face.corners[2], face.corners[1]),
                    uv=(face.uv[0], face.uv[2], face.uv[1]),
                )
                for face in found
            ]
        if not found:
            continue
        faces += found
        light = light or model["light"] == "side"
    picture = None
    if faces:
        picture = _draw_faces(faces, light)
    for flat in flat_pictures:
        if picture is None:
            picture = flat
        else:
            picture.alpha_composite(flat)
    return picture


def render_all(
    assets: Assets, folder: Path, progress: t.Callable[[int, int], None] = None
) -> int:
    """Draw every item in the jar into folder; returns how many were drawn."""
    prefix = ASSETS + "items/"
    names = sorted(
        entry[len(prefix) : -5]
        for entry in assets.archive.namelist()
        if entry.startswith(prefix) and entry.endswith(".json")
    )
    names = [name for name in names if NAME_RE.match(name)]
    drawn = 0
    for number, name in enumerate(names):
        try:
            picture = render_item(assets, name)
        except Exception as error:  # pylint: disable=broad-exception-caught
            # One odd model must not stop the rest
            logger.debug(f"Could not draw {name}: {error}")
            picture = None
        if picture is not None:
            picture.save(folder / f"{name}.png")
            drawn += 1
        if progress and number % 50 == 0:
            progress(number, len(names))
    for name, path in SPRITES.items():
        sprite = assets.image(path)
        if sprite is not None:
            sprite.save(folder / f"{name}.png")
    return drawn


# --------------------------------------------------------------------------
# Download and status
# --------------------------------------------------------------------------


class ItemIcons:
    """Makes the pictures in a background thread and reports how it is going."""

    _instances: t.Dict[str, "ItemIcons"] = {}
    _instances_lock = threading.Lock()

    def __init__(self, config_dir):
        self.folder = Path(config_dir) / "item_icons"
        self._lock = threading.Lock()
        self._job: t.Dict[str, t.Any] = {}

    @classmethod
    def get(cls, config_dir) -> "ItemIcons":
        key = str(config_dir)
        with cls._instances_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(config_dir)
            return cls._instances[key]

    def info(self) -> t.Optional[dict]:
        try:
            data = json.loads((self.folder / "info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def status(self) -> dict:
        with self._lock:
            job = dict(self._job)
        info = self.info()
        status = {"state": "ready" if info else "none"}
        if info:
            status.update({key: info.get(key) for key in ("version", "count", "made")})
        if job:
            status.update(job)
        return status

    def path(self, name: str) -> t.Optional[Path]:
        if not NAME_RE.match(name):
            return None
        path = self.folder / f"{name}.png"
        return path if path.is_file() else None

    def start(self) -> bool:
        """Start making the pictures; False if that is already happening."""
        with self._lock:
            if self._job.get("state") == "working":
                return False
            self._job = {"state": "working", "step": "download", "done": 0, "total": 0}
        threading.Thread(target=self._run, name="item_icons", daemon=True).start()
        return True

    def _set(self, **values) -> None:
        with self._lock:
            self._job.update(values)

    def _run(self) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="crafty_items_") as work:
                jar, version = self._download(Path(work))
                self._make(jar, version)
            with self._lock:
                self._job = {}
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(f"Could not make item pictures: {error}")
            self._set(state="error", error=str(error)[:300])

    def _download(self, work: Path) -> t.Tuple[Path, str]:
        session = requests.Session()
        manifest = session.get(MANIFEST, timeout=30)
        manifest.raise_for_status()
        manifest = manifest.json()
        version = manifest["latest"]["release"]
        entry = next(v for v in manifest["versions"] if v["id"] == version)
        details = session.get(entry["url"], timeout=30)
        details.raise_for_status()
        client = details.json()["downloads"]["client"]
        jar = work / "client.jar"
        self._set(version=version, total=int(client.get("size", 0)))
        for attempt in range(3):
            digest = hashlib.sha1()
            done = 0
            try:
                with session.get(client["url"], stream=True, timeout=60) as response:
                    response.raise_for_status()
                    with open(jar, "wb") as file:
                        for chunk in response.iter_content(1024 * 256):
                            file.write(chunk)
                            digest.update(chunk)
                            done += len(chunk)
                            self._set(done=done)
            except requests.RequestException:
                if attempt == 2:
                    raise
                continue
            if digest.hexdigest() == client["sha1"]:
                return jar, version
        raise ValueError("The download from Mojang did not match its checksum")

    def _make(self, jar: Path, version: str) -> None:
        self._set(step="draw", done=0, total=0)
        new = self.folder.with_name("item_icons.new")
        shutil.rmtree(new, ignore_errors=True)
        new.mkdir(parents=True)
        with zipfile.ZipFile(jar) as archive:
            count = render_all(
                Assets(archive),
                new,
                lambda done, total: self._set(done=done, total=total),
            )
        info = {
            "version": version,
            "count": count,
            "made": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        (new / "info.json").write_text(json.dumps(info), encoding="utf-8")
        old = self.folder.with_name("item_icons.old")
        shutil.rmtree(old, ignore_errors=True)
        if self.folder.exists():
            self.folder.rename(old)
        new.rename(self.folder)
        shutil.rmtree(old, ignore_errors=True)
        logger.info(f"Drew {count} item pictures from Minecraft {version}")
