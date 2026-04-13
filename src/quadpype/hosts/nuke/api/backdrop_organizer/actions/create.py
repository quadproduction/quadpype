from typing import Union
import nuke
from quadpype.lib import Logger

from quadpype.pipeline.settings import extract_width_and_height

from . import get, set, transform, check, convert, constants
from ..entities import Node, Backdrop
from quadpype.hosts.nuke.nuke_addon.stamps import stamps_autoClickedOk

"""
create.py
---------
Provides factory functions for creating and initializing Nuke nodes and backdrops.

Handles the instantiation of pipeline-specific elements (backdrops, shuffles,
removes, premults, dots, anchors, stamps), applying default knob values,
positioning, coloring, and pipe identifier setup upon creation.
"""
log = Logger.get_logger(__name__)

def backdrop(bd_name: str,
             bd_color: Union[list, tuple],
             bd_size: str = None,
             fill_backdrop: bool = True,
             font_size: int = constants.BACKDROP_FONT_SIZE,
             z_order: int = 0,
             position: tuple = None,
             identifier: str = constants.LOAD_BACKDROP) -> Backdrop:

    if check.backdrop_exists(bd_name):
        log.info(f"Backdrop already exists with name {bd_name}.")
        return get.backdrop(bd_name)

    if not bd_size:
        bd_size = constants.DEFAULT_BACKDROP_SIZE
    width, height = extract_width_and_height(bd_size)

    if not position:
        center_x = int(nuke.root().width() / 2)
        center_y = int(nuke.root().height() / 2)
        xpos = center_x
        ypos = center_y - int(height) // 2

    else:
        xpos, ypos = position

    new_backdrop = convert.node(nuke.createNode("BackdropNode"))

    transform.move(new_backdrop, xpos, ypos)
    transform.backdrop_size(new_backdrop, int(width), int(height))
    set.color_backdrop(new_backdrop, bd_color)

    set.knob_value(new_backdrop, "label", bd_name)
    set.knob_value(new_backdrop, "name", bd_name)

    set.knob_value(new_backdrop, "z_order", z_order)
    set.knob_value(new_backdrop, "note_font_size", font_size)

    if not fill_backdrop:
        set.knob_value(new_backdrop, "appearance", "Border")

    set.identifier_knob(new_backdrop, identifier)

    return get.backdrop(bd_name)

def shuffle_node(input_node: Node, layer_name: str) -> Node:
    """Will create a shuffle_node for a given layer in the input_node"""
    node = convert.node(nuke.createNode('Shuffle', inpanel=False))
    set.knob_value(node, "label", f"{layer_name}")
    set.knob_value(node, "in", layer_name)
    set.knob_value(node, "out", constants.RGBA)
    set.node_input(node, input_node, 0)
    return node

def remove_node(input_node: Node) -> Node:
    node = convert.node(nuke.createNode('Remove', inpanel=False))
    set.knob_value(node, "operation", 'keep')
    set.knob_value(node, "channels", constants.RGBA)
    set.node_input(node, input_node, 0)
    return node

def premult_node(input_node: Node) -> Node:
    node = convert.node(nuke.createNode('Premult', inpanel=False))
    set.node_input(node, input_node, 0)
    return node

def dot_node(input_node: Node) -> Node:
    node = convert.node(nuke.createNode('Dot', inpanel=False))
    set.node_input(node, input_node, 0)
    return node

def anchor_node(input_node: Node, title: str) -> Node:
    node = stamps_autoClickedOk.anchor(
        title=title,
        tags=constants.DEFAULT_ANCHOR_TAGS,
        input_node=input_node.nuke_entity,
        node_type=constants.DEFAULT_ANCHOR_TYPE
    )
    node = convert.node(node)
    set.node_input(node, input_node, 0)
    return node

def stamp_node(input_node: Node) -> Node:
    node = stamps_autoClickedOk.stampCreateWired(input_node.nuke_entity)
    return convert.node(node)
