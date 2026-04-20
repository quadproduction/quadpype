from enum import Enum
from typing import Union

from quadpype.pipeline import split_hierarchy
from quadpype.lib import Logger

from . import sort, set, get, update, filter, check, calculate, constants
from ..entities import Node, Backdrop

"""
align.py
--------
Provides alignment and positioning utilities for Nuke nodes and backdrops.

Handles the spatial arrangement of backdrops (main, representation, render layer,
publish) and their inner nodes, based on reference positions, hierarchy levels,
and configurable padding constants.

Main responsibilities:
- Align main backdrops relative to each other (left, right, top, bottom)
- Place representation and publish backdrops within their parent backdrop
- Move inner nodes consistently when their parent backdrop is repositioned
"""
log = Logger.get_logger(__name__)

class Position(Enum):
    notSpec = None
    left = "to_left"
    right = "to_right"
    top = "on_top"
    bottom = "under"

def main_backdrops(nodes_in_main_backdrops: dict[str, list[Node]] = None):
    """Will align and re-arrange all the main backdrops, depending on given position rule in the settings.
    Includes all their nodes inside."""

    #Store actual nodes in main backdrops before alignment
    if not nodes_in_main_backdrops:
        nodes_in_main_backdrops = get.nodes_in_mains_backdrops()

    #Store old position of the main backdrops
    old_main_backdrops_positions = dict()
    for main_backdrop in nodes_in_main_backdrops.keys():
        old_main_backdrops_positions[main_backdrop] = calculate.bounds(get.backdrop(main_backdrop))

    #Move backdrops
    for backdrop_profile in get.main_backdrops_profiles():
        position = Position[backdrop_profile["position"]].value
        if not position:
            continue

        backdrop = get.backdrop(backdrop_profile["name"])
        backdrop_reference = get.backdrop(backdrop_profile["backdrop_ref"])
        if backdrop and backdrop_reference:
            move_backdrop_based_on_ref(backdrop_reference, backdrop, position)

    #Move nodes inside main backdrops
    for main_backdrop, nodes in nodes_in_main_backdrops.items():
        new_x, new_y, *_ = calculate.bounds(get.backdrop(main_backdrop))

        old_x = old_main_backdrops_positions[main_backdrop][0]
        old_y = old_main_backdrops_positions[main_backdrop][1]

        offset_x = new_x-old_x
        offset_y = new_y-old_y

        for node in nodes:
            try:
                x, y, *_ = calculate.bounds(node)
                set.position(node, (x + offset_x), (y + offset_y))
            except ValueError:
                log.info("Node not found, must have been deleted.")
                pass

def move_backdrop_based_on_ref(
        backdrop_ref: Backdrop,
        backdrop_to_move: Backdrop,
        alignment: str,
        padding: int = constants.MAIN_BACKDROP_PADDING
):
    x1, y1, w1, h1 = calculate.bounds(backdrop_ref)
    x2, y2, w2, h2 = calculate.bounds(backdrop_to_move)

    if alignment == Position.left.value:
        new_x = int(x1 - w2 - padding)
        set.position(backdrop_to_move, new_x, y1)

    elif alignment == Position.right.value:
        new_x = int(x1 + w1 + padding)
        set.position(backdrop_to_move, new_x, y1)

    elif alignment == Position.top.value:
        new_y = int(y1 - h2 - padding)
        set.position(backdrop_to_move, x1, new_y)

    elif alignment == Position.bottom.value:
        new_y = int(y1 + h1 + padding)
        set.position(backdrop_to_move, x1, new_y)

#----------Load Representation Backdrops----------
def representation_backdrops(data: dict):
    """Will align the created backdrops for representation with themselves"""
    backdrop_hierarchies = get.resolved_backdrop_load_hierarchies(data)
    for hierarchy in backdrop_hierarchies:
        child_backdrop = None

        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        hierarchy.reverse()
        backdrops = [get.backdrop(h) for h in hierarchy]
        backdrops = filter.remove_main_backdrop(backdrops)
        for level, backdrop in enumerate(backdrops):
            if level == 0:
                child_backdrop = backdrop
                continue

            set.backdrop_size_based_on_nodes(backdrop, child_backdrop)
            bd_x, bd_y = child_backdrop.position

            new_x = bd_x + constants.BACKDROP_INSIDE_X_PADDING
            new_y = bd_y + constants.BACKDROP_INSIDE_Y_PADDING

            set.backdrop_position_with_nodes_within(child_backdrop, new_x, new_y)
            child_backdrop = backdrop

def representation_backdrops_in_main(data: dict):
    """Will align the representation backdrops and their nodes in the corresponding Main Backdrop"""
    backdrop_hierarchies = get.resolved_backdrop_load_hierarchies(data)
    for hierarchy in backdrop_hierarchies:
        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        backdrops = [get.backdrop(h) for h in hierarchy]
        main_backdrop = filter.main_backdrop_from_hierarchy(backdrops)
        lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops)

        pipe_backdrops_in_main = filter.pipe_backdrop([n for n in get.nodes_in_backdrops(main_backdrop)])
        pipe_backdrops_in_main = filter.backdrops_just_before_main(pipe_backdrops_in_main)

        main_x, main_y = main_backdrop.position
        final_w, final_h =lower_level_backdrop.size

        final_x = main_x + constants.BACKDROP_INSIDE_X_PADDING
        final_y = main_y + constants.BACKDROP_INSIDE_Y_PADDING

        if pipe_backdrops_in_main:
            sort.by_x_from_left_to_right(pipe_backdrops_in_main)
            ref_x, ref_y, ref_w, _ = calculate.bounds(pipe_backdrops_in_main)

            final_x = ref_x + ref_w + constants.BACKDROP_INSIDE_X_PADDING
            final_y = ref_y

            final_w, final_h = calculate.final_size_after_align(
                pipe_backdrops_in_main,
                lower_level_backdrop,
                main_backdrop
            )

        update.backdrop_size(main_backdrop, final_h, final_w)
        set.backdrop_position_with_nodes_within(lower_level_backdrop, final_x, final_y)

#----------Load RenderLayer Representation Backdrops----------
def representation_renderlayergroup_backdrops(data: dict, options: dict):
    """Will align the created backdrops for renderlayer representation inside the renderlayergroup backdrop"""
    backdrop_hierarchies = get.resolved_backdrop_load_renderlayergroup_hierarchies(data, options=options)
    for hierarchy in backdrop_hierarchies:
        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        backdrops = [get.backdrop(b) for b in hierarchy]

        renderlayergroup_backdrop = get.renderlayergroup_backdrop_in_hierarchy(data, backdrops, options)
        renderlayer_backdrop = filter.highest_z_order(backdrops)

        main_x, main_y = renderlayergroup_backdrop.position
        final_w, final_h = renderlayer_backdrop.size

        final_x = main_x + constants.BACKDROP_INSIDE_X_PADDING
        final_y = main_y + constants.BACKDROP_INSIDE_Y_PADDING

        renderlayer_backdrops_in_renderlayergroup = filter.pipe_backdrop(
            [n for n in get.nodes_in_backdrops(renderlayergroup_backdrop)]
        )

        if renderlayer_backdrops_in_renderlayergroup:
            sort.by_x_from_left_to_right(renderlayer_backdrops_in_renderlayergroup)
            ref_x, ref_y, ref_w, _ = calculate.bounds(renderlayer_backdrops_in_renderlayergroup)

            final_x = ref_x + ref_w + constants.BACKDROP_INSIDE_X_PADDING
            final_y = ref_y

            final_w, final_h = calculate.final_size_after_align(
                renderlayer_backdrops_in_renderlayergroup,
                renderlayer_backdrop,
                renderlayergroup_backdrop
            )

        update.backdrop_size(renderlayergroup_backdrop, final_h, final_w)
        set.backdrop_position_with_nodes_within(renderlayer_backdrop, final_x, final_y)

def representation_renderlayergroup_backdrops_in_main(data: dict, options: dict):
    """Will align the renderlayergroup backdrops and their nodes, to the right, in the corresponding Main Backdrop"""
    backdrop_hierarchies = get.resolved_backdrop_load_renderlayergroup_hierarchies(data, options=options)
    for hierarchy in backdrop_hierarchies:
        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        backdrops = [get.backdrop(h) for h in hierarchy]
        main_backdrop = filter.main_backdrop_from_hierarchy(backdrops)
        lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops)

        pipe_backdrops_in_main = filter.pipe_backdrop([n for n in get.nodes_in_backdrops(main_backdrop)])
        pipe_backdrops_in_main = filter.backdrops_just_before_main(pipe_backdrops_in_main)

        main_x, main_y = main_backdrop.position
        final_w, final_h = lower_level_backdrop.size

        final_x = main_x + constants.BACKDROP_INSIDE_X_PADDING
        final_y = main_y + constants.BACKDROP_INSIDE_Y_PADDING

        if pipe_backdrops_in_main:
            sort.by_x_from_left_to_right(pipe_backdrops_in_main)
            ref_x, ref_y, ref_w, _ = calculate.bounds(pipe_backdrops_in_main)
            final_x = ref_x + ref_w + constants.BACKDROP_INSIDE_X_PADDING
            final_y = ref_y

            final_w, final_h = calculate.final_size_after_align(
                pipe_backdrops_in_main,
                lower_level_backdrop,
                main_backdrop
            )

        update.backdrop_size(main_backdrop, final_h, final_w)
        set.backdrop_position_with_nodes_within(lower_level_backdrop, final_x, final_y)


#----------Publish Backdrops----------
def publish_backdrops(data: dict):
    """Will align the created backdrops for publish with themselves"""
    backdrop_hierarchies = get.resolved_backdrop_publish_hierarchies(data)
    for hierarchy in backdrop_hierarchies:
        child_backdrop = None

        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        hierarchy.reverse()
        backdrops = [get.backdrop(h) for h in hierarchy]
        backdrops = filter.remove_main_backdrop(backdrops)
        for level, backdrop in enumerate(backdrops):
            if level == 0:
                child_backdrop = backdrop
                continue

            set.backdrop_size_based_on_nodes(backdrop, child_backdrop)
            bd_x, bd_y = child_backdrop.position

            new_x = bd_x + constants.BACKDROP_INSIDE_X_PADDING
            new_y = bd_y + constants.BACKDROP_INSIDE_Y_PADDING

            set.backdrop_position_with_nodes_within(child_backdrop, new_x, new_y)
            child_backdrop = backdrop

def publish_backdrops_in_main(data: dict):
    """Will align the publishing backdrops and their nodes in the corresponding Main Backdrop"""
    backdrop_hierarchies = get.resolved_backdrop_publish_hierarchies(data)
    for hierarchy in backdrop_hierarchies:
        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        backdrops = [get.backdrop(h) for h in hierarchy]
        main_backdrop = filter.main_backdrop_from_hierarchy(backdrops)
        lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops)

        pipe_backdrops_in_main = filter.pipe_backdrop([n for n in get.nodes_in_backdrops(main_backdrop)])
        pipe_backdrops_in_main = filter.backdrops_just_before_main(pipe_backdrops_in_main)

        main_x, main_y = main_backdrop.position
        final_w, final_h =lower_level_backdrop.size

        final_x = main_x + constants.BACKDROP_INSIDE_X_PADDING
        final_y = main_y + constants.BACKDROP_INSIDE_Y_PADDING

        if pipe_backdrops_in_main:
            sort.by_x_from_left_to_right(pipe_backdrops_in_main)
            ref_x, ref_y, ref_w, _ = calculate.bounds(pipe_backdrops_in_main)

            final_x = ref_x + ref_w + constants.BACKDROP_INSIDE_X_PADDING
            final_y = ref_y

            final_w, final_h = calculate.final_size_after_align(
                pipe_backdrops_in_main,
                lower_level_backdrop,
                main_backdrop
            )

        update.backdrop_size(main_backdrop, final_h, final_w)
        set.backdrop_position_with_nodes_within(lower_level_backdrop, final_x, final_y)

#----------Nodes----------
def nodes_in_backdrop(
        nodes: Union[list[Node], Node],
        backdrop: Backdrop,
        padding_x: int = None,
        padding_y: int = None,
        padding_w: int = None,
        padding_h: int = None
):
    """Move given nodes inside a backdrop, will resize the backdrop if necessary"""
    if not padding_x:
        padding_x = constants.NODES_IN_BACKDROP_X_PADDING
    if not padding_y:
        padding_y = constants.NODES_IN_BACKDROP_Y_PADDING
    if not padding_w:
        padding_w = constants.BACKDROP_W_PADDING
    if not padding_h:
        padding_h = constants.BACKDROP_H_PADDING

    if not check.is_list(nodes):
        nodes = [nodes]
    if not check.is_space_in_backdrop_enough(backdrop, nodes):
        set.backdrop_size_based_on_nodes(backdrop, nodes, padding_w, padding_h)

    bd_x, bd_y = backdrop.position

    new_x = bd_x + padding_x
    new_y = bd_y + padding_y

    set.nodes_position(nodes, new_x, new_y)

def nodes_horizontally(nodes: list[Node], padding: int):
    """Will align horizontally the given nodes with a given spacing padding"""
    ref_x, ref_y = nodes[0].position
    for index, node in enumerate(nodes[1:]):
        new_x = ref_x + (padding * (index+1))
        set.position(node, new_x, ref_y)

def nodes_vertically(nodes: list[Node], padding: int):
    """Will align horizontally the given nodes with a given spacing padding"""
    ref_x, ref_y = nodes[0].position

    if check.is_dot(nodes[0]):
        ref_x = ref_x - constants.DOT_X_ALIGN_OFFSET

    for index, node in enumerate(nodes[1:]):
        new_y = ref_y + (padding * (index+1))
        set.position(node, ref_x, new_y)
