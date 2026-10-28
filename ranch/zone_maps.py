"""
Where the Pokémon stand on the zone maps (static/img/zone-*.png).

The maps are drawn by scripts/build_zone_maps.py on a grid of 40 x 23 tiles
of 16 px. Each map keeps room for its Pokémon (an open middle in the
Meadow, the alleys between the fruit trees in the Orchard): the spots
below sit there (keep the two in step). A page places things in percentages of the map, so
they stay on their tile whatever the size of the map on screen.
"""

MAP_COLS, MAP_ROWS, TILE = 40, 23, 16
MAP_WIDTH, MAP_HEIGHT = MAP_COLS * TILE, MAP_ROWS * TILE  # 640 x 368

# Spots of each zone, in the order they fill up: (column, row) of the tile a
# Pokémon stands on. More than the 3 places of the start: the skill tree
# will add places.
ZONE_SPOTS = {
    # Around the worn grass of the middle: a triangle first
    "meadow": [(21, 8), (16, 13), (26, 13), (15, 8), (27, 8), (21, 15)],
    # In the two alleys of the orchard (the bottom one is the trail)
    "orchard": [(19, 10), (15, 17), (23, 17), (11, 10), (27, 10), (31, 17)],
}

# Sun/Moon menu icons are 40 x 30 px, the Pokémon's feet on their 28th row
ICON_WIDTH, ICON_HEIGHT, ICON_FEET = 40, 30, 28


def spot_style(zone: str, index: int) -> str:
    """
    Inline CSS placing an icon on spot `index` of `zone`: centred on its tile,
    feet on the bottom of the tile, at the map's scale (one icon pixel = one
    map pixel).
    """
    col, row = ZONE_SPOTS[zone][index]
    left = col * TILE + TILE / 2 - ICON_WIDTH / 2
    top = (row + 1) * TILE - ICON_FEET
    width, height = ICON_WIDTH / MAP_WIDTH, ICON_HEIGHT / MAP_HEIGHT
    return (
        f"left: {100 * left / MAP_WIDTH:.3f}%; top: {100 * top / MAP_HEIGHT:.3f}%; "
        f"width: {100 * width:.3f}%; height: {100 * height:.3f}%;"
    )
