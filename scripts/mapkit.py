"""
Toolkit for the game's maps: FireRed/LeafGreen tiles, laid out by code.

Tiles are cut from official FRLG map renders (Bulbapedia archives) kept in
assets/map/sources/frlg/. FRLG maps sit on an exact 16x16 grid, so every
tile can be reused pixel for pixel. The sources share the same grass
colour, so their tiles blend seamlessly.

Most renders turn the GBA's 5-bit colours (0-31) into 8-bit ones by
multiplying by 8 (14 -> 112). A few use 255/31 instead (14 -> 115): those
are converted back on loading (gba_colours), so every tile blends.

A map script creates a MapCanvas, lays its scenery with the methods below,
then calls run(), which saves it with the HeartGold/SoulSilver-like palette.
Used by build_ranch_map.py and build_zone_maps.py.
"""

import argparse
import random
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "assets" / "map" / "sources" / "frlg"
IMG_DIR = ROOT / "static" / "img"

T = 16  # tile size in pixels
COLS, ROWS = 40, 23  # 640 x 368: a landscape map
# The border of firs is 2 firs thick on the left and right (4 tiles): the page
# crops the sides of the map on screens narrower than it, and this crops trees
# instead of the scenery.
SIDE = 4


def gba_colours(img):
    """Colours made with x * 255 / 31 brought back to x * 8, like the other renders."""
    table = [round(v * 31 / 255) * 8 for v in range(256)]
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r.point(table), g.point(table), b.point(table), a))


def _open(name):
    return Image.open(SOURCES / name).convert("RGBA")


_maps = {
    "r1": _open("Kanto_Route_1_FRLG.png"),
    "r25": _open("Kanto_Route_25_FRLG.png"),
    "four": _open("Four_Island_FRLG.png"),
    "pallet": _open("Pallet_Town_FRLG.png"),
    "vf": _open("Viridian_Forest_FRLG.png"),
    "r13": gba_colours(_open("Kanto_Route_13_FRLG.png")),
}


def tile(source, col, row):
    """The 16x16 tile at (col, row) of a source map."""
    return _maps[source].crop((col * T, row * T, (col + 1) * T, (row + 1) * T))


def key_out(piece, colours):
    """A tile whose pixels of the given colours become transparent."""
    piece = piece.copy()
    piece.putdata([(0, 0, 0, 0) if p in colours else p for p in piece.getdata()])
    return piece


# --- Tiles (source, column, row) -------------------------------------------------
GRASS = [("r1", 6, 13), ("r1", 7, 12), ("r1", 6, 12), ("r1", 5, 13)]
# Every colour of the grass: keyed out, they let a tile stand against the sky
GRASS_COLOURS = {colour for spec in GRASS for colour in tile(*spec).getdata()}
BROADLEAF_DOME = key_out(tile("vf", 22, 35), GRASS_COLOURS)  # see BROADLEAF_COL
TALL_GRASS = ("r1", 17, 15)
FLOWERS = ("r1", 3, 11)
# Wooden sign of Viridian Forest, standing on grass (the Route 1 one stands on sand)
SIGN = ("vf", 28, 44)
BUSH = ("r25", 15, 2)  # round bush
PLANT = ("four", 16, 6)  # leafy plant
SMALL_POND = [[("four", 34 + dx, 28 + dy) for dx in range(2)] for dy in range(2)]  # round, 2x2
# A small round tree of Four Island, 1 tile wide and 2 tall: top, then trunk
ROUND_TREE = [("four", 10, 6), ("four", 10, 7)]
WHITE_FLOWERS = ("vf", 19, 34)  # small white and orange flowers (Viridian Forest)
# Log fence of the Four Island Day Care: vertical line, bottom-left corner, horizontal line
FENCE = {"v": ("four", 9, 9), "corner": ("four", 9, 13), "h": ("four", 10, 13)}
# White fence of Route 13, a horizontal run
WHITE_FENCE = ("r13", 1, 6)
# Worn, lighter grass of Route 13, cut in 9 parts so it can take any size
LIGHT_GRASS = {
    key: ("r13", 13 + dx, 7 + dy)
    for dy, row in enumerate((("TL", "T", "TR"), ("L", "C", "R"), ("BL", "B", "BR")))
    for dx, key in enumerate(row)
}
# Broadleaf trees of Viridian Forest, 3 tiles wide, stacked like the firs: a
# row of tops, two rows of leaves that repeat, then trunks and shadows. Inside
# a wood each tree fills exactly its 3 columns, so woods of any size can be
# laid with these source rows (columns 18-20 of the forest).
BROADLEAF_COL = 21
BROADLEAF_TOP, BROADLEAF_LEAVES, BROADLEAF_TRUNK, BROADLEAF_SHADOW = 36, (37, 38), 41, 42
# The very top of a crown pokes into the tile above, in the middle column of
# the tree: this dome, its grass keyed out, is laid on whatever lies there
# (grass, tall grass, a path). Without it, the trees look cut flat.
# Firs are stacked in columns of 2 tiles: a top row, then two middle rows that
# repeat (the top of the next fir covers the bottom of the previous one),
# then the trunk. One fir alone is top + middle + trunk (3 tiles tall).
FIR_TOP, FIR_MIDDLE, FIR_TRUNK = 3, (4, 5), 11  # rows of the stack in Route 1 (cols 8-9)
# The left and right borders of Route 1 use the same two middle rows, with
# their own columns (0-1 and 22-23): trees behind trees, off the map.
BORDER_COLS = {"left": 0, "right": 22}

# Sand path: one tile per neighbourhood (autotiling, see MapCanvas.path)
PATH = {
    "C": ("r1", 11, 1),
    "T": ("r1", 17, 11),
    "B": ("r1", 17, 12),
    "L": ("r1", 13, 12),
    "R": ("r1", 15, 18),
    "TL": ("r1", 13, 11),
    "TR": ("r1", 21, 11),
    "BR": ("r1", 21, 12),
    # inner corners: path all around, grass only on one diagonal
    "ITL": ("r1", 13, 18),
    "ITR": ("r1", 13, 3),
    "IBL": ("r1", 18, 4),
}
# The tiles of the path, ready to draw. Route 1 has no clean bottom-left
# corner nor inner bottom-right one: they are the mirror images of their
# twins (the path's edges are symmetric; only the specks of sand differ).
PATH_TILES = {key: tile(*spec) for key, spec in PATH.items()}
PATH_TILES["BL"] = PATH_TILES["BR"].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
PATH_TILES["IBR"] = PATH_TILES["IBL"].transpose(Image.Transpose.FLIP_LEFT_RIGHT)

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


def runs_around(gap_rows):
    """
    Runs of a border column with an opening at `gap_rows` (see forest_border).

    A run is (first row, last row) of stacked firs. The rows next to the
    corners (2 and ROWS - 4) and the trunk/top rows around the gap must fit
    the two-row pattern of the stacks: openings of two rows at an even first
    row work, like the Ranch's entrance (rows 12 and 13).
    """
    return [(2, gap_rows[0] - 1), (gap_rows[-1] + 1, ROWS - 4)]


# Border columns with no opening. The cuts (trunk then top) let the pattern
# fit between the corners, at different rows on the two columns of a side.
CLOSED_OUTER = [(2, 7), (8, ROWS - 4)]
CLOSED_INNER = [(2, 11), (12, ROWS - 4)]


class MapCanvas:
    """A map being drawn, COLS x ROWS tiles (or any size, e.g. a zone's banner)."""

    def __init__(self, seed: int, cols: int = COLS, rows: int = ROWS):
        self.cols, self.rows = cols, rows
        self.image = Image.new("RGBA", (cols * T, rows * T))
        self.rng = random.Random(seed)  # fixed seed: the same map at every build

    def put(self, img, col, row):
        self.image.alpha_composite(img, (col * T, row * T))

    def put_tile(self, spec, col, row):
        self.put(tile(*spec), col, row)

    def grass(self):
        """Fill the whole map with grass, mixing its four variants at random."""
        for row in range(self.rows):
            for col in range(self.cols):
                self.put_tile(self.rng.choice(GRASS), col, row)

    def fill(self, spec, box):
        """One tile repeated over a box (col0, row0, col1, row1), e.g. tall grass."""
        c0, r0, c1, r1 = box
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                self.put_tile(spec, col, row)

    def scatter(self, spec, spots):
        for col, row in spots:
            self.put_tile(spec, col, row)

    def block(self, specs, col, row):
        """A block of tiles given as rows of specs (a pond, a tree...), top-left at (col, row)."""
        for dy, line in enumerate(specs):
            for dx, spec in enumerate(line):
                self.put_tile(spec, col + dx, row + dy)

    def patch(self, parts, box):
        """A 9-part patch (worn grass...) over a box: corners, edges and middle."""
        c0, r0, c1, r1 = box
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                v = "T" if row == r0 else "B" if row == r1 else ""
                h = "L" if col == c0 else "R" if col == c1 else ""
                self.put_tile(parts[(v + h) or "C"], col, row)

    def pond(self, box):
        """A rectangular pond over a box, with its bottom rim on the row below."""
        c0, r0, c1, r1 = box
        for row in range(r0, r1 + 2):  # one more row: the bottom rim on the grass
            for col in range(c0, c1 + 1):
                v = "T" if row == r0 else "B" if row == r1 else "U" if row == r1 + 1 else ""
                h = "L" if col == c0 else "R" if col == c1 else ""
                key = (v + h) or "C"
                self.put_tile(POND["U" + h if v == "U" else key], col, row)

    def path(self, in_path: Callable[[int, int], bool]):
        """A sand path over the cells where in_path(col, row) is true (autotiling)."""

        def edge(col, row):
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

        for row in range(self.rows):
            for col in range(self.cols):
                if in_path(col, row):
                    self.put(PATH_TILES[edge(col, row)], col, row)

    def fir_stack(self, col, row, count):
        """A column of `count` firs, 2 tiles wide, its top tile at (col, row)."""
        rows = [FIR_TOP] + list(FIR_MIDDLE) * (count - 1) + [FIR_MIDDLE[0], FIR_TRUNK]
        for dy, source_row in enumerate(rows):
            for dx in range(2):
                self.put_tile(("r1", 8 + dx, source_row), col + dx, row + dy)

    def crown_dome(self, col, row):
        """The top of a broadleaf crown, at (col, row): the middle column of a tree."""
        self.put(BROADLEAF_DOME, col, row)

    def wood(self, col, row, wide, tall):
        """
        A wood of `wide` x `tall` broadleaf trees, its row of tops at (col, row).
        Height: the tops (with their domes on the row above), two rows per tree,
        then trunks and shadows. A wood touching the broadleaf border must start
        on a multiple of 3, so its trees line up with the border's (col % 3).
        """
        rows = [BROADLEAF_TOP, *BROADLEAF_LEAVES * tall, BROADLEAF_TRUNK, BROADLEAF_SHADOW]
        for dy, source_row in enumerate(rows):
            for dx in range(3 * wide):
                self.put_tile(("vf", BROADLEAF_COL + dx % 3, source_row), col + dx, row + dy)
        for dx in range(1, 3 * wide, 3):
            self.crown_dome(col + dx, row - 1)

    def broadleaf_border(self, gap_rows, left=6, right=7):
        """
        Close the map with broadleaf trees instead of firs: `left` and `right`
        columns on the sides, three rows at the top and bottom, and an opening
        on the left at `gap_rows` (two rows, an even first row).

        Every tile follows col % 3, so the inner edges of the walls must fall
        between two trees: the left wall ends after a multiple of 3 (6) and the
        right one starts on a multiple of 3 (40 - 7 = 33), leaving 27 columns,
        9 whole trees, for the bands.

        The sides are walls of leaves (the two repeating rows); above the
        opening they end with trunks and shadows, below it they start again
        with a row of tops. The top band shows the bottom of trees (leaves,
        trunks, shadows), the bottom band their tops.
        """
        top, (even, odd), trunk, shadow = (
            BROADLEAF_TOP,
            BROADLEAF_LEAVES,
            BROADLEAF_TRUNK,
            BROADLEAF_SHADOW,
        )

        def put(col, row, source_row):
            self.put_tile(("vf", BROADLEAF_COL + col % 3, source_row), col, row)

        for col in range(left, COLS - right):
            for row, source_row in enumerate((odd, trunk, shadow)):
                put(col, row, source_row)
            for row, source_row in zip(range(ROWS - 3, ROWS), (top, even, odd), strict=True):
                put(col, row, source_row)
            if col % 3 == 1:
                self.crown_dome(col, ROWS - 4)  # the bottom band's trees: their domes
        first, last = gap_rows[0], gap_rows[-1]
        for col in [*range(left), *range(COLS - right, COLS)]:
            is_left = col < left
            for row in range(ROWS):
                if is_left and first <= row <= last:
                    continue  # the opening
                if is_left and row == first - 2:
                    source_row = trunk
                elif is_left and row == first - 1:
                    source_row = shadow
                elif is_left and row == last + 1:
                    source_row = top
                elif is_left and row > last:
                    source_row = even if (row - last) % 2 == 0 else odd  # 37 just below the tops
                else:
                    source_row = even if row % 2 == 0 else odd
                put(col, row, source_row)
        # Below the opening, the left wall starts again with tops: their domes
        for col in range(1, left, 3):
            self.crown_dome(col, last)

    def round_tree(self, col, row):
        """A small round tree (1 x 2 tiles), its top at (col, row)."""
        self.block([[ROUND_TREE[0]], [ROUND_TREE[1]]], col, row)

    def forest_border(self, left_outer, left_inner, right_inner, right_outer):
        """
        Close the map with firs: a band at the top and bottom, and two columns
        of stacked firs on each side, each described by its runs (see
        runs_around). A run that starts below the top corner begins with a fir
        top; one that ends above the bottom corner ends with a trunk. The rows
        in between alternate between the two middle rows, and the row next to
        a corner must be the first one (FIR_MIDDLE[0]).
        """
        for col in range(SIDE, COLS - SIDE):
            for dy in range(2):
                self.put_tile(("r1", 2 + col % 2, dy), col, dy)  # top: bottoms of the trees
            for dy in range(3):
                self.put_tile(("r1", 2 + col % 2, 37 + dy), col, ROWS - 3 + dy)  # bottom: tops
        columns = [
            (0, "left", left_outer),
            (2, "left", left_inner),
            (COLS - 4, "right", right_inner),
            (COLS - 2, "right", right_outer),
        ]
        for map_col, side, runs in columns:
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
                        self.put_tile((spec[0], spec[1] + dx, spec[2]), map_col + dx, row)
            # Corners: the column of firs goes on behind the top and bottom bands
            for dx in range(2):
                for dy in range(2):
                    self.put_tile(("r1", BORDER_COLS[side] + dx, dy), map_col + dx, dy)
                for dy in range(3):
                    self.put_tile(
                        ("r1", BORDER_COLS[side] + dx, 37 + dy), map_col + dx, ROWS - 3 + dy
                    )


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


def save(canvas: MapCanvas, output: Path, scale: int = 1, frlg: bool = False) -> None:
    """Save a map (HGSS palette unless `frlg`), optionally enlarged without smoothing."""
    image = canvas.image if frlg else hgss_palette(canvas.image)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.resize((image.width * scale, image.height * scale), Image.NEAREST).save(output)
    print("saved", output, image.size, "x", scale)


def cli(doc: str, maps: dict[str, Callable[[], MapCanvas]]) -> None:
    """
    Command line of a map script: build each map into static/img/<name>.png,
    or with an output folder and a zoom, previews of them.
    """
    parser = argparse.ArgumentParser(
        description=doc, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("output", nargs="?", type=Path, default=IMG_DIR, help="output folder")
    parser.add_argument("scale", nargs="?", type=int, default=1, help="integer zoom")
    parser.add_argument("--frlg", action="store_true", help="keep the original FRLG colours")
    args = parser.parse_args()
    for name, build in maps.items():
        save(build(), args.output / f"{name}.png", args.scale, args.frlg)
