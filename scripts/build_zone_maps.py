"""
Build the maps of the harvest zones (top-down, FireRed/LeafGreen tiles).

Each zone has its own landscape, with a path coming from the left (where
the Ranch is):
- the Meadow, open countryside: sand paths winding between fields of tall
  grass, white fences, flower beds and worn grass, closed by firs;
- the Orchard, in a wood of broadleaf trees (Viridian Forest): fruit trees
  in straight rows, the Pokémon working in the alleys between them.

The Pokémon stand on the spots listed in ranch/zone_maps.py. Around them,
each map keeps areas free of anything tall (trees, fences, tall grass):
only ground (paths, worn grass) may lie there. The build fails if a tall
prop is placed in one.

Usage:
    uv run python scripts/build_zone_maps.py               # writes static/img/zone-*.png
    uv run python scripts/build_zone_maps.py previews/ 2   # into any folder, scaled x2
"""

from mapkit import (
    BROADLEAF_COL,
    BROADLEAF_DOME,
    BROADLEAF_LEAVES,
    BROADLEAF_TOP,
    BUSH,
    CLOSED_INNER,
    CLOSED_OUTER,
    FLOWERS,
    LIGHT_GRASS,
    PLANT,
    SIGN,
    SMALL_POND,
    TALL_GRASS,
    WHITE_FENCE,
    WHITE_FLOWERS,
    MapCanvas,
    cli,
    runs_around,
    tile,
)

ENTRANCE_ROWS = (12, 13)  # the path comes in on the left, as on the Ranch


def check_clear(work_area, cells):
    """Fail the build if a tall prop covers the work area (where the Pokémon stand)."""
    c0, r0, c1, r1 = work_area
    for col, row in cells:
        assert not (c0 <= col <= c1 and r0 <= row <= r1), f"({col}, {row}) is in the work area"


def box_cells(box):
    c0, r0, c1, r1 = box
    return [(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


# --- The Meadow -------------------------------------------------------------------

MEADOW_WORK_AREA = (13, 6, 30, 16)


def meadow_path(col, row):
    """A network of paths: the main one across, two lanes up and down, a loop at the top."""
    main = row in ENTRANCE_ROWS and col <= 33
    west_lane = col in (11, 12) and 4 <= row <= 18
    east_lane = col in (31, 32) and 4 <= row <= 13
    top_loop = row in (4, 5) and 11 <= col <= 32
    return main or west_lane or east_lane or top_loop or (col < 0 and row in ENTRANCE_ROWS)


def meadow() -> MapCanvas:
    canvas = MapCanvas(seed=11)
    canvas.grass()

    # Worn grass where the Pokémon gather, around the middle
    canvas.patch(LIGHT_GRASS, (17, 7, 26, 10))
    canvas.patch(LIGHT_GRASS, (15, 15, 19, 16))

    # Fields of tall grass between the paths
    fields = [(5, 3, 9, 10), (5, 15, 9, 18), (14, 18, 29, 19), (34, 15, 35, 19), (14, 2, 30, 2)]
    # White fences along the fields, with gaps to walk through
    fences = [(c, 17) for c in range(13, 31) if c not in (21, 22)] + [
        (c, 3) for c in range(13, 31) if c not in (17, 18, 26)
    ]
    flowers = [(33, 7), (34, 8), (35, 6), (34, 10), (6, 11), (8, 11), (10, 15), (33, 16)]
    white_flowers = [(33, 9), (35, 8), (7, 11), (9, 14), (10, 7), (10, 16), (34, 13), (35, 10)]
    bushes = [(34, 3), (35, 3), (35, 12), (10, 2)]
    check_clear(MEADOW_WORK_AREA, [c for f in fields for c in box_cells(f)] + fences)
    check_clear(MEADOW_WORK_AREA, flowers + white_flowers + bushes)

    for box in fields:
        canvas.fill(TALL_GRASS, box)
    canvas.path(meadow_path)
    canvas.scatter(WHITE_FENCE, fences)
    canvas.scatter(FLOWERS, flowers)
    canvas.scatter(WHITE_FLOWERS, white_flowers)
    canvas.scatter(BUSH, bushes)
    canvas.block(SMALL_POND, 33, 18)
    canvas.put_tile(SIGN, 9, 11)  # by the path: "Meadow"

    entrance = runs_around(ENTRANCE_ROWS)
    canvas.forest_border(entrance, entrance, CLOSED_INNER, CLOSED_OUTER)
    return canvas


# --- The Orchard ------------------------------------------------------------------

# Like a real orchard: fruit trees in straight rows, with grass alleys in
# between where the Pokémon work. Two rows of six broadleaf trees, one
# column apart, centred in the clearing (columns 6 to 32).
ORCHARD_TREE_COLS = range(8, 29, 4)  # 8-10, 12-14, ..., 28-30
ORCHARD_TREE_ROWS = (4, 11)  # each tree: top, two rows of leaves, trunk, shadow
# The alleys: between the two rows (rows 9-10), and the trail at the bottom
ORCHARD_TRAIL_ROWS = (16, 17)
ORCHARD_ALLEYS = [(6, 9, 32, 10), (6, 16, 32, 17)]


def orchard_path(col, row):
    """The trail: in from the left, along the bottom alley of the orchard."""
    return row in ORCHARD_TRAIL_ROWS and col <= 32


def orchard() -> MapCanvas:
    canvas = MapCanvas(seed=12)
    canvas.grass()

    trees = [(col, row) for row in ORCHARD_TREE_ROWS for col in ORCHARD_TREE_COLS]
    tall_grass = [(7, 18, 18, 19), (22, 18, 31, 19)]
    white_flowers = [(6, 4), (7, 6), (31, 4), (32, 7), (6, 13), (32, 13), (20, 19), (21, 18)]
    plants = [(6, 11), (32, 11), (19, 3), (23, 3)]

    tall = [c for col, row in trees for c in box_cells((col, row, col + 2, row + 4))]
    for box in tall_grass:
        tall += box_cells(box)
    for alley in ORCHARD_ALLEYS:  # the alleys stay clear for the Pokémon
        check_clear(alley, tall + white_flowers + plants)

    for box in tall_grass:
        canvas.fill(TALL_GRASS, box)
    canvas.path(orchard_path)
    canvas.scatter(WHITE_FLOWERS, white_flowers)
    canvas.scatter(PLANT, plants)
    for col, row in trees:
        canvas.wood(col, row, 1, 1)
    canvas.put_tile(SIGN, 7, 15)  # by the trail, past the edge of the wood: "Orchard"

    canvas.broadleaf_border(ORCHARD_TRAIL_ROWS)
    return canvas


# --- Banners -------------------------------------------------------------------------
# A small picture of each zone for the list of zones, in the spirit of the
# area icons of Pokémon Platinum: a strip of the zone's landscape, two tiles
# high (shown at x2 in a 64 px band), wide enough not to repeat on a card.
BANNER_COLS, BANNER_ROWS = 16, 2  # 256 x 32 px


def meadow_banner() -> MapCanvas:
    """Fields: tall grass, stretches of white fence, bushes and flowers."""
    canvas = MapCanvas(seed=21, cols=BANNER_COLS, rows=BANNER_ROWS)
    canvas.grass()
    canvas.fill(TALL_GRASS, (0, 0, 2, 1))
    canvas.fill(TALL_GRASS, (10, 1, 15, 1))
    canvas.fill(TALL_GRASS, (14, 0, 15, 0))
    canvas.scatter(WHITE_FENCE, [(c, 0) for c in (*range(3, 8), *range(10, 14))])
    canvas.scatter(BUSH, [(8, 0), (9, 0)])
    canvas.scatter(FLOWERS, [(4, 1), (7, 1), (9, 1)])
    canvas.scatter(WHITE_FLOWERS, [(3, 1), (5, 1), (8, 1)])
    return canvas


def orchard_banner() -> MapCanvas:
    """
    A row of fruit trees with flowers and plants between them. A whole tree
    doesn't fit in two tiles: the trees are drawn 8 px lower, so their
    rounded tops show and the bottom of their leaves leaves the picture.
    """
    canvas = MapCanvas(seed=22, cols=BANNER_COLS, rows=BANNER_ROWS)
    canvas.grass()
    canvas.scatter(PLANT, [(3, 0), (11, 0)])
    canvas.scatter(WHITE_FLOWERS, [(3, 1), (7, 0), (7, 1), (11, 1), (15, 0)])
    for col in range(0, BANNER_COLS, 4):  # trees 3 wide, a column apart
        for dx in range(3):
            x = (col + dx) * 16
            parts = [(BROADLEAF_TOP, 8), (BROADLEAF_LEAVES[0], 24)]
            for source_row, y in parts:
                piece = tile("vf", BROADLEAF_COL + dx, source_row)
                canvas.image.paste(piece, (x, y), piece)
            if dx == 1:  # the dome of the crown, half in the picture
                canvas.image.paste(BROADLEAF_DOME, (x, -8), BROADLEAF_DOME)
    return canvas


if __name__ == "__main__":
    cli(
        __doc__,
        {
            "zone-meadow": meadow,
            "zone-orchard": orchard,
            "zone-meadow-banner": meadow_banner,
            "zone-orchard-banner": orchard_banner,
        },
    )
