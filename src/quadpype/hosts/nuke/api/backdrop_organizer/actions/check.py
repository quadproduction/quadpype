import nuke

from . import get, filter, calculate, constants
from ..entities import Node, Backdrop

"""
check.py
--------
Provides boolean predicate functions for type, state, and spatial checks
on Nuke nodes and backdrops.

Covers node class identification (Read, Dot, Shuffle, Backdrop, etc.),
knob existence and value checks, spatial fit validation (size, width, height),
backdrop typing (main, load, publish), and pipeline-specific conditions
such as layer compatibility or repositioning necessity.
"""

def is_string(var) -> bool:
    return isinstance(var, str)

def is_list(var) -> bool:
    return isinstance(var, list)

def backdrop_exists(backdrop_name: str) -> bool:
    return backdrop_name in [node["name"].value() for node in nuke.allNodes("BackdropNode")]

def is_node_in_backdrop(node: Node, backdrop: Backdrop) -> bool:
    return node.name in [n.name for n in get.nodes_in_backdrops(backdrop)]

def is_space_in_backdrop_enough(backdrop: Backdrop, nodes: list[Node]) -> bool:
    _, _, n_w, n_h = calculate.bounds(nodes)
    _, _, b_w, b_h = calculate.bounds(backdrop)
    return n_w < b_w and n_h < b_h

def is_size_enough(backdrop: Backdrop, width: int, height:int) -> bool:
    _, _, b_w, b_h = calculate.bounds(backdrop)
    return width < b_w and height < b_h

def is_height_enough(backdrop: Backdrop, height: int) -> bool:
    _, _, _, b_h = calculate.bounds(backdrop)
    return height < b_h

def is_width_enough(backdrop: Backdrop, width: int) -> bool:
    _, _, b_w, _ = calculate.bounds(backdrop)
    return width < b_w

def is_main_backdrop(backdrop: Backdrop) -> bool:
    return backdrop.nuke_entity.knob(constants.MAIN_BACKDROP) is not None

def is_load_backdrop(backdrop: Backdrop) -> bool:
    return backdrop.nuke_entity.knob(constants.LOAD_BACKDROP) is not None

def is_publish_backdrop(backdrop: Backdrop) -> bool:
    return backdrop.nuke_entity.knob(constants.PUBLISH_BACKDROP) is not None

def has_knob(node: Node, knob: str) -> bool:
    if node.nuke_entity.knob(knob):
        return True
    return False

def is_pipe_node(node: Node) -> bool:
    return any(node.nuke_entity.knob(t) for t in [
        constants.MAIN_BACKDROP,
        constants.LOAD_BACKDROP,
        constants.LOAD_RENDERLAYER_BACKDROP,
        constants.PUBLISH_BACKDROP,
        constants.PARENT_BACKDROP
    ]
        )

def is_linked_to_representation(node: Node, representation: str) -> bool:
    linked_knob = node.nuke_entity.knob(constants.LINKED_READ)
    if linked_knob is None:
        return False
    return get.knob_value(node, constants.LINKED_READ) == representation

def has_pipe_backdrops_on_its_right(backdrop: Backdrop) -> bool:
    main_backdrop = get.main_backdrop_from_parent_backdrop(backdrop)
    pipe_backdrops_in_main = filter.pipe_backdrop(
            [n for n in get.nodes_in_backdrops(main_backdrop)]
        )
    if backdrop in pipe_backdrops_in_main:
        pipe_backdrops_in_main.remove(backdrop)

    backdrop_x, _, backdrop_w, _ = calculate.bounds(backdrop)
    ref_x = backdrop_x + backdrop_w

    bd_in_main_x, _, bd_in_main_w, _ = calculate.bounds(pipe_backdrops_in_main)
    bd_in_main_ref_x = bd_in_main_x + bd_in_main_w

    return ref_x < bd_in_main_ref_x

def is_backdrop_before_main_from_parent_backdrop(backdrop: Backdrop) -> bool:
    parent_backdrop = get.parent_backdrop_from_pipe_backdrop(backdrop)
    return is_main_backdrop(parent_backdrop)

def is_decompose_layer_compatible(ext: str) -> bool:
    return ext in (set(constants.PSD_EXT) | set(constants.EXR_EXT))

def is_psd(ext: str) -> bool:
    return ext in constants.PSD_EXT

def is_exr(ext: str) -> bool:
    return ext in constants.EXR_EXT

def is_dot(node: Node) -> bool:
    return node.nuke_class == "Dot"

def is_shuffle(node: Node) -> bool:
    return node.nuke_class== "Shuffle"

def is_premult(node: Node) -> bool:
    return node.nuke_class == "Premult"

def is_remove(node: Node) -> bool:
    return node.nuke_class == "Remove"

def is_read(node: Node) -> bool:
    return node.nuke_class == "Read"

def is_nuke_backdrop(node: nuke.Node) -> bool:
    return node.Class() == "BackdropNode"

def is_backdrop(node: Node) -> bool:
    return node.nuke_class == "BackdropNode"

def is_anchor(node: Node) -> bool:
    return node.nuke_class == "NoOp"

def is_stamp(node: Node) -> bool:
    return node.nuke_class == "PostageStamp"

def reposition_in_main(backdrop: Backdrop) -> bool:
    """Check if the given backdrop is in a Main Backdrop,
    and will have to be repositioned at the same place after align"""
    backdrop_before_main = get.backdrop_before_main_from_parent_backdrop(backdrop)
    main_backdrop = get.main_backdrop_from_parent_backdrop(backdrop)

    if not is_node_in_backdrop(backdrop_before_main, main_backdrop):
        return False
    if not has_pipe_backdrops_on_its_right(backdrop_before_main):
        return False
    return True

def shuffle_layer(node : Node, layer_name: str):
    shuffle_layer_name = get.knob_value(node, "in")
    return shuffle_layer_name == layer_name

def need_move_to_the_right(
        updated_representation_backdrop: Backdrop,
        nodes_to_the_right: list[Node]
) -> bool:
    if not nodes_to_the_right:
        return False
    updated_w, _ = updated_representation_backdrop.size
    updated_x, _ = updated_representation_backdrop.position
    new_x = updated_w + updated_x + constants.BACKDROP_INSIDE_X_PADDING

    nodes_x, nodes_y, _, _ = calculate.bounds(nodes_to_the_right)

    return new_x > nodes_x
