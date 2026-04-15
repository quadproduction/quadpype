import nuke
from typing import Union

from . import convert, check, constants, calculate
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

def position(node: Union[Node, Backdrop], x: int, y: int):
    node.nuke_entity["xpos"].setValue(x)
    node.nuke_entity["ypos"].setValue(y)

def nodes_position(nodes: list[Union[Node, Backdrop]], x: int, y: int):
    """Move a group of Nodes to a given position by conserving their relatives position"""
    ref_x, ref_y= nodes[0].position
    offset_x = x - ref_x
    offset_y = y - ref_y
    for node in nodes:
        nodes_position_with_offset(node, offset_x, offset_y)

def nodes_position_with_offset(nodes: Union[list[Node], Node], offset_x: int, offset_y: int):
    """Move a group of Nodes by applying a given offset"""
    if not check.is_list(nodes):
        nodes = [nodes]

    for node in nodes:
        x, y  = node.position
        position(
            node,
            x + offset_x,
            y + offset_y
        )

def backdrop_size(
        backdrop: Backdrop,
        width: int = None,
        height: int = None,
        padding_w: int = 0,
        padding_h: int = 0):
    if width:
        backdrop.nuke_entity["bdwidth"].setValue(width + padding_w)
    if height:
        backdrop.nuke_entity["bdheight"].setValue(height + padding_h)

def backdrop_size_based_on_nodes(
        backdrop: Backdrop,
        nodes: Union[list[Node], Node],
        padding_w: int = None,
        padding_h: int = None
):
    if not padding_w:
        padding_w = constants.BACKDROP_W_PADDING
    if not padding_h:
        padding_h = constants.BACKDROP_H_PADDING

    if not check.is_list(nodes):
        nodes = [nodes]
    x, y, nodes_width, nodes_height = calculate.bounds(nodes)

    bd_width = nodes_width + padding_w
    bd_height = nodes_height + padding_h
    backdrop_size(backdrop, bd_width, bd_height)

def backdrop_position_with_nodes_within(backdrop: Backdrop, x: int, y: int):
    ref_x, ref_y = backdrop.position
    inside_nodes = [convert.node(n) for n in backdrop.get_nodes()]
    position(backdrop, x, y)
    offset_x = x - ref_x
    offset_y = y - ref_y
    nodes_position_with_offset(inside_nodes, offset_x, offset_y)
