import nuke
from typing import Union

from . import convert, check
from ..entities import Node, Backdrop

"""
set.py
------
Provides setter utilities for applying values to Nuke nodes and backdrops.

Handles knob value assignment, backdrop coloring, node input connections,
and pipeline identifier knob creation for pipe-tagging nodes.
"""

def identifier_knob(node: Node, identifier: str, identifier_value: str = None):
    if check.has_knob(node, identifier):
        return
    knob = nuke.String_Knob(identifier, identifier)
    node.nuke_entity.addKnob(knob)
    if identifier_value:
        knob_value(node, identifier, identifier_value)

def color_backdrop(backdrop: Backdrop, bd_color: Union[list, tuple]):
    if isinstance(bd_color, list):
        bd_color = tuple(bd_color)
    r, g, b, a = bd_color
    backdrop.nuke_entity["tile_color"].setValue(convert.rgb_to_nuke_color(r, g, b))

def node_input(node: Node, input_node: Node, index: int):
    node.nuke_entity.setInput(index, input_node.nuke_entity)

def knob_value(node: Node, knob: str, value: Union[str, int, bool]):
    node.nuke_entity[knob].setValue(value)
