"""
Build the images of Professor Oak's lab (its pages, under /lab/).

From the FRLG map of the inside of the lab (assets/map/sources/frlg/), with
the HGSS colours of the other maps (mapkit.hgss_palette):

- lab-inside.png: the lab itself, shown on the lab's first page with
  Professor Oak (the black row under its door mat is left out);
- lab-floor.png: a piece of its floor, repeated as the background of every
  lab page (2 x 2 tiles: the stripes of the floor repeat every 2 tiles).

Usage:
    uv run python scripts/build_lab_images.py
"""

from mapkit import IMG_DIR, SOURCES, hgss_palette
from PIL import Image

TILE = 16
INSIDE = SOURCES / "Professor_Oak_Lab_inside_FRLG.png"
ROWS = 13  # the 14th row is black, under the door mat
FLOOR = (5, 6)  # top-left tile of a plain piece of floor (between the table and the shelves)


def main() -> None:
    lab = hgss_palette(Image.open(INSIDE).convert("RGBA"))
    inside = lab.crop((0, 0, lab.width, ROWS * TILE))
    inside.save(IMG_DIR / "lab-inside.png")
    col, row = FLOOR
    floor = lab.crop((col * TILE, row * TILE, (col + 2) * TILE, (row + 2) * TILE))
    floor.save(IMG_DIR / "lab-floor.png")
    print("saved lab-inside.png", inside.size, "and lab-floor.png", floor.size)


if __name__ == "__main__":
    main()
