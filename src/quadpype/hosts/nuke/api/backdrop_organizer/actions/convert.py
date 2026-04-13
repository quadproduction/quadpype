from typing import Union
import nuke
from . import check
from ..entities import Node, Backdrop

"""
convert.py
----------
Provides conversion utilities between raw Nuke types and internal entities.

Handles color format conversion (RGB to Nuke's packed integer format) and
wrapping of nuke.Node instances into the appropriate Node or Backdrop entity.
"""

def rgb_to_nuke_color(r: int, g: int, b: int) -> int:
    return (r << 24) + (g << 16) + (b << 8)

def node(nuke_node: nuke.Node) -> Union[Node, Backdrop]:
    if check.is_nuke_backdrop(nuke_node):
        return Backdrop(nuke_entity=nuke_node)
    return Node(nuke_entity=nuke_node)
