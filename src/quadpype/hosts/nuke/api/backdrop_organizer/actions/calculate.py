from typing import Union

from . import check, constants
from ..entities import Node, Backdrop

"""
calculate.py
------------
Provides spatial and visual calculation utilities for Nuke nodes and backdrops.

Handles bounding box computation for single or grouped nodes, color darkening
across backdrop hierarchy levels, and final size estimation when aligning
multiple backdrops side by side.
"""

def color_hierarchy(color: list[int], hierarchy: list[str]) -> list[list[int]]:
    """Blacken the based color based on the number of backdrop that will be created"""
    num_levels = len(hierarchy)
    colors = [color]
    for i in range(num_levels - 1):
        colors.append([int(x * 0.75) for x in colors[-1]])
    colors.reverse()
    return colors

def bounds(nodes: Union[list[Union[Node, Backdrop]], Union[Node, Backdrop]]) -> tuple[int, int, int, int]:
    if not check.is_list(nodes):
        return nodes.x , nodes.y, nodes.width, nodes.height

    x_positions = [n.x for n in nodes]
    y_positions = [n.y for n in nodes]
    # A condition is necessary, because when a node is newly created, screenWidth return 0 and not the correct width
    widths = [n.width if (n.width > 0) else constants.NODE_DEFAULT_WIDTH for n in nodes]
    heights = [n.height for n in nodes]

    min_x = min(x_positions)
    min_y = min(y_positions)
    max_x = max(x + w for x, w in zip(x_positions, widths))
    max_y = max(y + h for y, h in zip(y_positions, heights))

    width = max_x - min_x
    height = max_y - min_y

    return min_x, min_y, width, height

def final_size_after_align(
        backdrops: list[Backdrop],
        backdrop: Backdrop,
        lower_level_backdrop: Backdrop
) -> tuple[int, int]:
    """Will return the final size of backdrops and backdrop
     combined after alignment based on their size BEFORE doing it"""
    ref_x, _, ref_w, ref_h = bounds(backdrops)
    bd_w, bd_h = backdrop.size

    width = ref_w + bd_w + constants.BACKDROP_INSIDE_W_PADDING
    height = max([ref_h, bd_h])

    lower_x, lower_y = lower_level_backdrop.position
    offset_w = ref_x - lower_x - constants.BACKDROP_W_PADDING
    width = width + offset_w

    return width, height
