from . import sort, get, set, filter, check, align, calculate, constants
from ..entities import Node, Backdrop


"""
update.py
---------
Provides high-level update operations that modify the state of nodes and backdrops
in response to representation changes.

Covers backdrop resizing after content updates, horizontal repositioning of nodes
displaced by size changes, Read node file path updates, anchor title refresh,
and vertical/horizontal realignment of shuffle nodes and their downstream chains.
"""

def backdrop_size(backdrop: Backdrop, height: int, width: int):
    if not check.is_height_enough(backdrop, height):
        set.backdrop_size(backdrop,
                                height=height,
                                padding_h=constants.BACKDROP_INSIDE_H_PADDING)

    if not check.is_width_enough(backdrop, width):
        set.backdrop_size(backdrop,
                                width=width,
                                padding_w=constants.BACKDROP_W_PADDING)

def representation_backdrops_size_based_on_nodes(backdrops: list[Backdrop], nodes: list[Node]):
    backdrops.reverse()
    for backdrop in backdrops:
        set.backdrop_size_based_on_nodes(backdrop, nodes)
        nodes.append(backdrop)

def backdrop_size_after_update(
        main_backdrop: Backdrop,
        final_nodes: list[Node],
        original_w: int,
        updated_representation_backdrop: Backdrop
):

    updated_w, updated_h = updated_representation_backdrop.size
    offset_x = updated_w - original_w

    new_x, new_y, new_w, new_h = calculate.bounds(final_nodes)
    final_x = new_x + new_w

    main_w, main_h = main_backdrop.size
    main_x, main_y = main_backdrop.position
    final_main_x = main_x + main_w

    if final_x > final_main_x:
        final_w = main_w + offset_x
        set.backdrop_size(main_backdrop, final_w, main_h)

def nodes_to_the_right_position(
        original_w: int,
        updated_representation_backdrop: Backdrop,
        nodes_to_the_right: list[Node]
):
    updated_w = updated_representation_backdrop.width
    offset_x = updated_w - original_w
    set.nodes_position_with_offset(nodes_to_the_right, offset_x, 0)

def read_file(read_node: Node, new_file: str):
    set.knob_value(read_node, "file", new_file)

def shuffle_and_downstream_horizontal_align(read_node: Node, ext: str, layers_to_add: dict):
    representation_name = read_node.name

    layers_data = get.layers_from_node(read_node, ext)

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)
    lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)

    representation_nodes = get.nodes_linked_to_representation(representation_name)
    shuffle_nodes = filter.shuffle_nodes(representation_nodes)
    shuffle_nodes = sort.shuffle_nodes_by_index(shuffle_nodes, layers_data)

    align.nodes_vertically([read_node, shuffle_nodes[0]], constants.SHUFFLE_Y_PADDING)
    align.nodes_horizontally(shuffle_nodes, constants.SHUFFLE_X_PADDING)
    set.nodes_position_with_offset(shuffle_nodes, 0, constants.SHUFFLE_Y_PADDING)

    layer_names_to_add = [layer_data["name"] for layer_data in layers_to_add.values()]
    for shuffle_node in shuffle_nodes:
        layer_name = get.knob_value(shuffle_node, "in")
        downstream_nodes = list(get.downstream_nodes(shuffle_node))
        if layer_name not in layer_names_to_add:
            downstream_nodes = filter.nodes_in_given_backdrop(downstream_nodes, lower_level_backdrop)

        ref_x, ref_y = shuffle_node.position
        new_y = ref_y + (constants.REMOVE_Y_PADDING * 2)

        sort.by_y_from_up_to_down(downstream_nodes)
        set.nodes_position(downstream_nodes, ref_x, new_y)
