"""
Build the Ranch map (top-down, Pokémon FireRed/LeafGreen tiles).

Tiles are cut from official FRLG map renders (Bulbapedia archives) kept in
assets/map/sources/frlg/. FRLG maps sit on an exact 16x16 grid, so every
tile can be reused pixel for pixel. The map follows the validated layout:
a clearing closed by firs, the entrance on the left, a path crossing the
screen to the ranch on the right, a pond, tall grass and simple props.
The colours are then warmed up towards HeartGold/SoulSilver (see hgss_palette).

Usage:
    uv run python scripts/build_ranch_map.py            # writes static/img/ranch-map.png
    uv run python scripts/build_ranch_map.py preview.png 3   # any path, scaled x3
    uv run python scripts/build_ranch_map.py preview.png 3 --frlg   # original FRLG colours
"""

import argparse
import random
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "assets" / "map" / "sources" / "frlg"
OUTPUT = ROOT / "static" / "img" / "ranch-map.png"

T = 16  # tile size in pixels
COLS, ROWS = 40, 23  # 640 x 368: a landscape map
rng = random.Random(4)  # fixed seed: the same map at every build

# The three sources share the same grass colour, so their tiles blend seamlessly
_maps = {
    "r1": Image.open(SOURCES / "Kanto_Route_1_FRLG.png").convert("RGBA"),
    "r25": Image.open(SOURCES / "Kanto_Route_25_FRLG.png").convert("RGBA"),
    "four": Image.open(SOURCES / "Four_Island_FRLG.png").convert("RGBA"),
    "pallet": Image.open(SOURCES / "Pallet_Town_FRLG.png").convert("RGBA"),
}


def tile(source, col, row):
    """The 16x16 tile at (col, row) of a source map."""
    return _maps[source].crop((col * T, row * T, (col + 1) * T, (row + 1) * T))


canvas = Image.new("RGBA", (COLS * T, ROWS * T))


def put(img, col, row):
    canvas.alpha_composite(img, (col * T, row * T))


# --- Tiles used (source, column, row) ------------------------------------------
GRASS = [("r1", 6, 13), ("r1", 7, 12), ("r1", 6, 12), ("r1", 5, 13)]
TALL_GRASS = ("r1", 17, 15)
FLOWERS = ("r1", 3, 11)
SIGN = ("r1", 9, 31)
BUSH = ("r25", 15, 2)  # round bush
PLANT = ("four", 16, 6)  # leafy plant
SMALL_POND = [[("four", 34 + dx, 28 + dy) for dx in range(2)] for dy in range(2)]  # round, 2x2
MAILBOX = [("pallet", 4, 6), ("pallet", 4, 7)]  # top, then bottom
# Log fence of the Four Island Day Care: vertical line, bottom-left corner, horizontal line
FENCE = {"v": ("four", 9, 9), "corner": ("four", 9, 13), "h": ("four", 10, 13)}
# The Four Island Day Care: 4 x 4 tiles (the top row is the ridge of the roof)
DAY_CARE = ("four", 11, 10)  # its top-left tile in the source
# Firs are stacked in columns of 2 tiles: a top row, then two middle rows that
# repeat (the top of the next fir covers the bottom of the previous one),
# then the trunk. One fir alone is top + middle + trunk (3 tiles tall).
FIR_TOP, FIR_MIDDLE, FIR_TRUNK = 3, (4, 5), 11  # rows of the stack in Route 1 (cols 8-9)
# The left and right borders of Route 1 use the same two middle rows, with
# their own columns (0-1 and 22-23): trees behind trees, off the map.
BORDER_COLS = {"left": 0, "right": 22}

# Sand path: one tile per neighbourhood (autotiling, see path_tile)
PATH = {
    "C": ("r1", 11, 1),
    "T": ("r1", 17, 11),
    "B": ("r1", 17, 12),
    "L": ("r1", 13, 12),
    "R": ("r1", 15, 18),
    "TL": ("r1", 13, 11),
    "TR": ("r1", 21, 11),
    "BL": ("r1", 5, 19),
    "BR": ("r1", 21, 12),
    # inner corners: path all around, grass only on one diagonal
    "ITL": ("r1", 13, 18),
    "ITR": ("r1", 13, 3),
    "IBL": ("r1", 18, 4),
    "IBR": ("r1", 14, 12),
}

# Pond, cut in 9 parts so it can take any size. Its bottom rim is a thin
# line drawn at the top of the grass row below it: the "U" (under) tiles.
POND = {
    "TL": ("r25", 43, 9),
    "T": ("r25", 44, 9),
    "TR": ("r25", 48, 9),
    "L": ("r25", 43, 10),
    "C": ("r25", 44, 10),
    "R": ("r25", 48, 10),
    "BL": ("r25", 43, 11),
    "B": ("r25", 44, 11),
    "BR": ("r25", 48, 11),
    "UL": ("r25", 43, 12),
    "U": ("r25", 44, 12),
    "UR": ("r25", 48, 12),
}

# --- Layout -------------------------------------------------------------------------
ENTRANCE_ROWS = (12, 13)  # the path enters on the left edge
HOUSE = (32, 3)  # top-left tile of the ranch (4 x 4 tiles)
DOOR_COL = HOUSE[0] + 1
POND_BOX = (15, 4, 21, 7)  # col0, row0, col1, row1 (inclusive)
TALL_GRASS_BOXES = [(3, 3, 8, 6), (4, 16, 10, 18), (16, 16, 21, 18)]
FLOWER_SPOTS = [
    (11, 4),
    (12, 5),
    (10, 9),
    (23, 9),
    (24, 4),
    (28, 19),
    (13, 17),
    (29, 10),
    (8, 10),
    (22, 15),
]
SMALL_POND_AT = (24, 15)  # top-left tile of the second, smaller pond
# Firs: (col, row, count) = a stack of `count` firs whose top tile is at (col, row)
FIRS = [
    (27, 3, 1),  # outside the yard, on the left of the house
    (23, 5, 1),  # next to the big pond
    (12, 14, 1),
    (26, 15, 1),  # next to the small pond
    # a grove: three stacks side by side, at staggered heights
    (30, 16, 1),
    (32, 14, 2),
    (34, 15, 2),
]
BUSH_SPOTS = [(9, 3), (9, 4), (2, 14), (2, 15), (25, 11), (36, 12), (37, 12), (37, 13), (14, 9)]
PLANT_SPOTS = [(14, 5), (22, 6), (27, 9), (11, 19)]
# Yard of the ranch: a fence on its left and bottom, open where the path comes in
YARD_FENCE_COL, YARD_FENCE_ROW = 29, HOUSE[1] + 6
YARD_GATE = range(DOOR_COL - 1, DOOR_COL + 2)  # the path goes through here
MAILBOX_AT = (HOUSE[0] - 1, HOUSE[1] + 2)  # top tile, on the left of the front wall
SIGN_AT = (HOUSE[0] + 4, HOUSE[1] + 3)  # on the right of the front wall
# Border columns: (first row, last row) of each run of stacked firs. A run that
# starts below the top corner begins with a fir top; one that ends above the
# bottom corner ends with a trunk. The rows in between alternate between the two
# middle rows, and the row next to a corner must be the first one (FIR_MIDDLE[0]):
# that is why the right column is cut in two runs, like the left one.
BORDER_RUNS = {
    "left": [(2, ENTRANCE_ROWS[0] - 1), (ENTRANCE_ROWS[1] + 1, ROWS - 4)],  # around the entrance
    "right": [(2, 11), (12, ROWS - 4)],
}


def in_path(col, row):
    """Path cells: the band from the entrance to the ranch, then up to the door."""
    horizontal = row in ENTRANCE_ROWS and col <= DOOR_COL + 1
    vertical = DOOR_COL - 1 <= col <= DOOR_COL + 1 and HOUSE[1] + 5 <= row <= ENTRANCE_ROWS[1]
    return horizontal or vertical or (col < 0 and row in ENTRANCE_ROWS)  # runs off the map


def path_tile(col, row):
    """Pick the edge tile of a path cell from its neighbours (autotiling)."""
    n, s = in_path(col, row - 1), in_path(col, row + 1)
    w, e = in_path(col - 1, row), in_path(col + 1, row)
    if not n and not w:
        return "TL"
    if not n and not e:
        return "TR"
    if not s and not w:
        return "BL"
    if not s and not e:
        return "BR"
    if not n:
        return "T"
    if not s:
        return "B"
    if not w:
        return "L"
    if not e:
        return "R"
    if not in_path(col - 1, row - 1):
        return "ITL"
    if not in_path(col + 1, row - 1):
        return "ITR"
    if not in_path(col - 1, row + 1):
        return "IBL"
    if not in_path(col + 1, row + 1):
        return "IBR"
    return "C"


# --- Ground: grass, tall grass, flowers, pond, path --------------------------------
for row in range(ROWS):
    for col in range(COLS):
        put(tile(*rng.choice(GRASS)), col, row)

for c0, r0, c1, r1 in TALL_GRASS_BOXES:
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            put(tile(*TALL_GRASS), col, row)

for col, row in FLOWER_SPOTS:
    put(tile(*FLOWERS), col, row)

c0, r0, c1, r1 = POND_BOX
for row in range(r0, r1 + 2):  # one more row: the bottom rim on the grass
    for col in range(c0, c1 + 1):
        v = "T" if row == r0 else "B" if row == r1 else "U" if row == r1 + 1 else ""
        h = "L" if col == c0 else "R" if col == c1 else ""
        key = (v + h) or "C"
        put(tile(*POND["U" + h if v == "U" else key]), col, row)

for row in range(ROWS):
    for col in range(COLS):
        if in_path(col, row):
            put(tile(*PATH[path_tile(col, row)]), col, row)

for dy, line in enumerate(SMALL_POND):
    for dx, spec in enumerate(line):
        put(tile(*spec), SMALL_POND_AT[0] + dx, SMALL_POND_AT[1] + dy)

for spots, spec in ((BUSH_SPOTS, BUSH), (PLANT_SPOTS, PLANT)):
    for col, row in spots:
        put(tile(*spec), col, row)

# --- The ranch: the Day Care of Four Island (FRLG) ---------------------------------
for dy in range(4):
    for dx in range(4):
        put(tile("four", DAY_CARE[1] + dx, DAY_CARE[2] + dy), HOUSE[0] + dx, HOUSE[1] + dy)
# Brick doorstep in front of the door (from Route 25)
for dx in range(3):
    put(tile("r25", 50 + dx, 5), DOOR_COL - 1 + dx, HOUSE[1] + 4)

# Mailbox and notice board on each side of the front wall. Pallet Town's grass
# is a shade lighter than ours: its colours become transparent around the mailbox.
pallet_grass = set(tile("pallet", 4, 5).getdata())
for dy, spec in enumerate(MAILBOX):
    piece = tile(*spec)
    piece.putdata([(0, 0, 0, 0) if p in pallet_grass else p for p in piece.getdata()])
    put(piece, MAILBOX_AT[0], MAILBOX_AT[1] + dy)
put(tile(*SIGN), *SIGN_AT)

# Log fence of the yard: down from the trees, then right to the border of firs,
# with a gate where the path comes in
for row in range(2, YARD_FENCE_ROW):
    put(tile(*FENCE["v"]), YARD_FENCE_COL, row)
put(tile(*FENCE["corner"]), YARD_FENCE_COL, YARD_FENCE_ROW)
for col in range(YARD_FENCE_COL + 1, COLS - 2):
    if col not in YARD_GATE:
        put(tile(*FENCE["h"]), col, YARD_FENCE_ROW)


def fir_stack(col, row, count):
    """A column of `count` firs, 2 tiles wide, its top tile at (col, row)."""
    rows = [FIR_TOP] + list(FIR_MIDDLE) * (count - 1) + [FIR_MIDDLE[0], FIR_TRUNK]
    for dy, source_row in enumerate(rows):
        for dx in range(2):
            put(tile("r1", 8 + dx, source_row), col + dx, row + dy)


for fir in FIRS:
    fir_stack(*fir)

# --- Border of firs, with the entrance on the left ---------------------------------
for col in range(2, COLS - 2):
    for dy in range(2):
        put(tile("r1", 2 + col % 2, dy), col, dy)  # top: bottoms of the trees
    for dy in range(3):
        put(tile("r1", 2 + col % 2, 37 + dy), col, ROWS - 3 + dy)  # bottom: tree tops
for side, runs in BORDER_RUNS.items():
    map_col = 0 if side == "left" else COLS - 2
    for first, last in runs:
        for row in range(first, last + 1):
            if row == first and first != 2:  # a new run: fir top, free-standing
                spec = ("r1", 8, FIR_TOP)
            elif row == last and last != ROWS - 4:  # end of a run: trunk
                spec = ("r1", 8, FIR_TRUNK)
            else:  # behind the corners, the run starts on the first middle row
                start = first if first == 2 else first + 1
                spec = ("r1", BORDER_COLS[side], FIR_MIDDLE[(row - start) % 2])
            for dx in range(2):
                put(tile(spec[0], spec[1] + dx, spec[2]), map_col + dx, row)
for dx in range(2):
    for dy in range(2):
        put(tile("r1", dx, dy), dx, dy)  # top-left corner
        put(tile("r1", 22 + dx, dy), COLS - 2 + dx, dy)  # top-right corner
    for dy in range(3):
        put(tile("r1", dx, 37 + dy), dx, ROWS - 3 + dy)  # bottom-left corner
        put(tile("r1", 22 + dx, 37 + dy), COLS - 2 + dx, ROWS - 3 + dy)  # bottom-right


# --- HeartGold/SoulSilver-like palette (the default look) --------------------------
def hgss_palette(img):
    """
    Warm up the FRLG colours towards HGSS: greens pulled towards yellow, then
    more saturation and contrast. Pixel art keeps its look because each colour
    of the palette is only moved, never blended with its neighbours.
    """
    alpha = img.getchannel("A")
    h, s, v = img.convert("RGB").convert("HSV").split()
    # Pillow's hue runs from 0 to 255: greens and teals sit between ~60 and ~130
    h = h.point(lambda x: x - 10 if 60 <= x <= 130 else x)
    img = Image.merge("HSV", (h, s, v)).convert("RGB")
    img = ImageEnhance.Color(img).enhance(1.3)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img.putalpha(alpha)
    return img


# --- Save --------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("output", nargs="?", type=Path, default=OUTPUT)
parser.add_argument(
    "scale", nargs="?", type=int, default=1, help="integer zoom (nearest neighbour)"
)
parser.add_argument("--frlg", action="store_true", help="keep the original FRLG colours")
args = parser.parse_args()

image = canvas if args.frlg else hgss_palette(canvas)
args.output.parent.mkdir(parents=True, exist_ok=True)
image.resize((image.width * args.scale, image.height * args.scale), Image.NEAREST).save(args.output)
print("saved", args.output, image.size, "x", args.scale)
