"""
Build the Ranch map (top-down, Pokémon FireRed/LeafGreen tiles).

The layout: a clearing closed by firs, the entrance on the left, a path
crossing the screen to the ranch (the Four Island Day Care) on the right,
Professor Oak's lab (Pallet Town) above the path, two ponds, tall grass and
simple props. Tiles and drawing tools come from
mapkit.py; the colours are warmed up towards HeartGold/SoulSilver.

Usage:
    uv run python scripts/build_ranch_map.py              # writes static/img/ranch-map.png
    uv run python scripts/build_ranch_map.py previews/ 3  # into any folder, scaled x3
    uv run python scripts/build_ranch_map.py previews/ 3 --frlg   # original FRLG colours
"""

from mapkit import (
    BUSH,
    CLOSED_INNER,
    CLOSED_OUTER,
    COLS,
    FEEDER,
    FENCE,
    FLOWERS,
    LIGHT_GRASS,
    PLANT,
    SIDE,
    SIGN,
    SMALL_POND,
    TALL_GRASS,
    MapCanvas,
    cli,
    key_out,
    runs_around,
    tile,
)

MAILBOX = [("pallet", 4, 6), ("pallet", 4, 7)]  # top, then bottom
# The Four Island Day Care: 4 x 4 tiles (the top row is the ridge of the roof)
DAY_CARE = ("four", 11, 10)  # its top-left tile in the source
# Professor Oak's lab of Pallet Town: 7 x 5 tiles, its door in the middle of
# the bottom row
LAB_SOURCE = ("pallet", 13, 9)  # its top-left tile in the source
LAB_SIZE = (7, 5)

# --- Layout -------------------------------------------------------------------------
ENTRANCE_ROWS = (12, 13)  # the path enters on the left edge
# The clearing spans cols 4 to 35, between the two thick borders of firs
HOUSE = (30, 3)  # top-left tile of the ranch (4 x 4 tiles)
DOOR_COL = HOUSE[0] + 1
POND_BOX = (12, 4, 17, 7)  # col0, row0, col1, row1 (inclusive)
# The lab, between the pond and the yard: its door opens onto the path, by a
# short piece of path (keep in step with the Ranch page, which makes it
# clickable)
LAB = (19, 6)  # its top-left tile
LAB_DOOR_COL = LAB[0] + 3
LAB_SIGN_AT = (LAB[0] + 5, LAB[1] + 5)
TALL_GRASS_BOXES = [(5, 3, 9, 6), (6, 16, 11, 18), (16, 16, 20, 18)]
FLOWER_SPOTS = [
    (11, 4),
    (11, 6),
    (12, 9),
    (18, 9),
    (21, 2),
    (26, 19),
    (14, 17),
    (27, 10),
    (10, 10),
    (20, 14),
]
SMALL_POND_AT = (22, 15)  # top-left tile of the second, smaller pond
# Firs: (col, row, count) = a stack of `count` firs whose top tile is at (col, row)
FIRS = [
    (25, 3, 1),  # outside the yard, on the left of the house
    (19, 3, 1),  # next to the big pond, above the lab
    (13, 14, 1),
    (24, 15, 1),  # next to the small pond
    # a grove: three stacks side by side, at staggered heights
    (27, 16, 1),
    (29, 14, 2),
    (31, 15, 2),
]
BUSH_SPOTS = [(10, 3), (10, 4), (4, 14), (4, 15), (19, 11), (34, 12), (35, 12), (35, 13), (14, 9)]
PLANT_SPOTS = [(11, 8), (26, 11), (12, 19)]
# Yard of the ranch: a fence on its left and bottom, open where the path comes in
YARD_FENCE_COL, YARD_FENCE_ROW = HOUSE[0] - 3, HOUSE[1] + 6
YARD_GATE = range(DOOR_COL - 1, DOOR_COL + 2)  # the path goes through here
MAILBOX_AT = (HOUSE[0] - 1, HOUSE[1] + 2)  # top tile, on the left of the front wall
SIGN_AT = (HOUSE[0] + 4, HOUSE[1] + 3)  # on the right of the front wall
# The feeder: on the left, between the tall grass and the path, on a patch of
# grass worn by the visitors (keep in step with the Ranch page, which makes it
# clickable)
FEEDER_AT = (7, 8)  # its top tile
FEEDER_PATCH = (6, 8, 8, 10)


def in_path(col, row):
    """
    Path cells: the band from the entrance to the ranch, then up to its door,
    and the short way up to the lab's door.
    """
    horizontal = row in ENTRANCE_ROWS and col <= DOOR_COL + 1
    vertical = DOOR_COL - 1 <= col <= DOOR_COL + 1 and HOUSE[1] + 5 <= row <= ENTRANCE_ROWS[1]
    lab_way = LAB_DOOR_COL - 1 <= col <= LAB_DOOR_COL + 1 and row == LAB[1] + LAB_SIZE[1]
    off_map = col < 0 and row in ENTRANCE_ROWS  # the path runs off the map
    return horizontal or vertical or lab_way or off_map


def build() -> MapCanvas:
    canvas = MapCanvas(seed=4)

    # Ground: grass, tall grass, flowers, ponds, path, small plants
    canvas.grass()
    for box in TALL_GRASS_BOXES:
        canvas.fill(TALL_GRASS, box)
    canvas.scatter(FLOWERS, FLOWER_SPOTS)
    canvas.pond(POND_BOX)
    canvas.path(in_path)
    canvas.block(SMALL_POND, *SMALL_POND_AT)
    canvas.scatter(BUSH, BUSH_SPOTS)
    canvas.scatter(PLANT, PLANT_SPOTS)
    canvas.patch(LIGHT_GRASS, FEEDER_PATCH)
    for dy, piece in enumerate(FEEDER):
        canvas.put(piece, FEEDER_AT[0], FEEDER_AT[1] + dy)

    # The ranch: the Day Care of Four Island, with a brick doorstep (Route 25)
    canvas.block(
        [[("four", DAY_CARE[1] + dx, DAY_CARE[2] + dy) for dx in range(4)] for dy in range(4)],
        *HOUSE,
    )
    for dx in range(3):
        canvas.put_tile(("r25", 50 + dx, 5), DOOR_COL - 1 + dx, HOUSE[1] + 4)

    # Mailbox and notice board on each side of the front wall. Pallet Town's grass
    # is a shade lighter than ours: its colours become transparent around the mailbox.
    pallet_grass = set(tile("pallet", 4, 5).getdata())

    # Professor Oak's lab, its Pallet Town grass made transparent too (above the
    # roof: the grass just above the lab in the source, a dotted shade), and its
    # sign on the right of the way to its door
    source, col0, row0 = LAB_SOURCE
    lab_grass = pallet_grass | set(tile(source, col0 + 3, row0 - 1).getdata())
    for dy in range(LAB_SIZE[1]):
        for dx in range(LAB_SIZE[0]):
            piece = key_out(tile(source, col0 + dx, row0 + dy), lab_grass)
            canvas.put(piece, LAB[0] + dx, LAB[1] + dy)
    canvas.put_tile(SIGN, *LAB_SIGN_AT)
    for dy, spec in enumerate(MAILBOX):
        canvas.put(key_out(tile(*spec), pallet_grass), MAILBOX_AT[0], MAILBOX_AT[1] + dy)
    canvas.put_tile(SIGN, *SIGN_AT)

    # Log fence of the yard: down from the trees, then right to the border of firs,
    # with a gate where the path comes in
    for row in range(2, YARD_FENCE_ROW):
        canvas.put_tile(FENCE["v"], YARD_FENCE_COL, row)
    canvas.put_tile(FENCE["corner"], YARD_FENCE_COL, YARD_FENCE_ROW)
    for col in range(YARD_FENCE_COL + 1, COLS - SIDE):
        if col not in YARD_GATE:
            canvas.put_tile(FENCE["h"], col, YARD_FENCE_ROW)

    for fir in FIRS:
        canvas.fir_stack(*fir)

    # Border of firs, open on the left where the path comes in
    entrance = runs_around(ENTRANCE_ROWS)
    canvas.forest_border(entrance, entrance, CLOSED_INNER, CLOSED_OUTER)
    return canvas


if __name__ == "__main__":
    cli(__doc__, {"ranch-map": build})
