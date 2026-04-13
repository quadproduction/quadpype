from typing import Union

from . import check, convert, calculate, constants
from ..entities import Node, Backdrop

"""
transform.py
------------
Provides spatial transformation utilities for moving and resizing Nuke nodes
and backdrops.

Handles absolute positioning, offset-based moves (single or grouped nodes),
backdrop resizing (fixed or node-based), and coordinated movement of a backdrop
together with all its inner nodes.
"""

def move(node: Union[Node, Backdrop], x: int, y: int):
    node.nuke_entity["xpos"].setValue(x)
    node.nuke_entity["ypos"].setValue(y)

def move_nodes(nodes: list[Union[Node, Backdrop]], x: int, y: int):
    """Move a group of Nodes to a given position by conserving their relatives position"""
    ref_x, ref_y= nodes[0].position
    offset_x = x - ref_x
    offset_y = y - ref_y
    for node in nodes:
        offset_nodes(node, offset_x, offset_y)

def offset_nodes(nodes: Union[list[Node], Node], offset_x: int, offset_y: int):
    """Move a group of Nodes by applying a given offset"""
    if not check.is_list(nodes):
        nodes = [nodes]

    for node in nodes:
        x, y  = node.position
        move(
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

def move_backdrop_with_nodes_within(backdrop: Backdrop, x: int, y: int):
    ref_x, ref_y = backdrop.position
    inside_nodes = [convert.node(n) for n in backdrop.get_nodes()]
    move(backdrop, x, y)
    offset_x = x - ref_x
    offset_y = y - ref_y
    offset_nodes(inside_nodes, offset_x, offset_y)

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
