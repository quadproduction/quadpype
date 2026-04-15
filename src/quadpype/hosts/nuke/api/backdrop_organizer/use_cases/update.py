import nuke

from ..actions import (
    delete,
    sort,
    compare,
    get,
    update,
    ask,
    set,
    filter,
    generate,
    check,
    convert,
    constants
)
from ..entities import Node

"""
update.py
---------
Provides update pipelines for switching the file path of an existing representation
in Nuke.

Compares layer variations between the old and new file, prompts the user for
confirmation, then selectively deletes obsolete shuffle chains, creates new ones
for added layers, and resizes/repositions the affected backdrops and their
neighbours. Handles both standard representations and render layer group hierarchies.
"""

def representation(read_node: nuke.Node, options: dict, new_file: str) -> bool:
    ext = options["ext"]
    prep_layers = options["prep_layers"]
    create_stamps = options["create_stamps"]

    read_node = convert.node(read_node)

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)

    main_backdrop = filter.main_backdrop_from_hierarchy(backdrops_with_read_node)
    lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)

    old_file = get.knob_value(read_node, "file")

    if check.is_decompose_layer_compatible(ext) and prep_layers:
        has_more_layers = compare.layer_number(read_node, ext, new_file)
        layers_to_add, layers_to_delete = compare.layers_variations(read_node, ext, new_file)

        update.read_file(read_node, new_file)

        proceed = ask.accept_layers_variations(layers_to_add, layers_to_delete)
        if not proceed:
            update.read_file(read_node, old_file)
            return False

        representation_backdrops = filter.remove_main_backdrop(backdrops_with_read_node)
        sort.by_z_order(representation_backdrops)

        representation_upper_level_backdrop = filter.highest_z_order(representation_backdrops)

        original_w = lower_level_backdrop.width
        nodes_to_the_right = get.pipe_nodes_to_the_right(lower_level_backdrop)

        delete.shuffles_and_downstream_from_layers_data(read_node, layers_to_delete)
        representation_nodes = get.nodes_in_backdrops(representation_upper_level_backdrop)

        if layers_to_add:
            new_nodes_created = _create_layers_to_add_shuffle_and_stamp_tree(read_node, layers_to_add, create_stamps)
            update.shuffle_and_downstream_horizontal_align(read_node, ext, layers_to_add)

            if not has_more_layers:
                update.read_file(read_node, new_file)
                return True
            representation_nodes.extend(new_nodes_created)

            update.representation_backdrops_size_based_on_nodes(representation_backdrops, representation_nodes)
            if check.need_move_to_the_right(lower_level_backdrop, nodes_to_the_right):
                update.nodes_to_the_right_position(original_w, lower_level_backdrop, nodes_to_the_right)

            final_nodes = representation_nodes + nodes_to_the_right
            update.backdrop_size_after_update(main_backdrop, final_nodes, original_w, lower_level_backdrop)

        else:
            update.shuffle_and_downstream_horizontal_align(read_node, ext, layers_to_add)

    update.read_file(read_node, new_file)
    return True

def renderlayer_representation(read_node: nuke.Node, options: dict, new_file: str) -> bool:
    ext = options["ext"]
    prep_layers = options["prep_layers"]
    create_stamps = options["create_stamps"]

    read_node = convert.node(read_node)

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)

    main_backdrop = filter.main_backdrop_from_hierarchy(backdrops_with_read_node)
    renderlayergroup_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)
    renderlayer_backdrop = filter.highest_z_order(backdrops_with_read_node)

    old_file = get.knob_value(read_node, "file")

    if check.is_decompose_layer_compatible(ext) and prep_layers:
        has_more_layers = compare.layer_number(read_node, ext, new_file)
        layers_to_add, layers_to_delete = compare.layers_variations(read_node, ext, new_file)

        update.read_file(read_node, new_file)

        proceed = ask.accept_layers_variations(layers_to_add, layers_to_delete)
        if not proceed:
            update.read_file(read_node, old_file)
            return False


        original_group_w = renderlayergroup_backdrop.width
        original_layer_w = renderlayer_backdrop.width

        nodes_to_the_right_in_main = get.pipe_nodes_to_the_right(renderlayergroup_backdrop)
        nodes_to_the_right_in_renderlayergroup_backdrop = get.pipe_nodes_to_the_right_in_renderlayergroup(
            renderlayer_backdrop,
            renderlayergroup_backdrop
        )

        delete.shuffles_and_downstream_from_layers_data(read_node, layers_to_delete)

        renderlayer_nodes = get.nodes_in_backdrops(renderlayer_backdrop)
        renderlayergroup_nodes = get.nodes_in_backdrops(renderlayergroup_backdrop)

        if layers_to_add:
            new_nodes_created = _create_layers_to_add_shuffle_and_stamp_tree(read_node, layers_to_add, create_stamps)

            update.shuffle_and_downstream_horizontal_align(read_node, ext, layers_to_add)

            if not has_more_layers:
                update.read_file(read_node, new_file)
                return True

            renderlayer_nodes.extend(new_nodes_created)
            renderlayergroup_nodes.extend(new_nodes_created)

            # Adapt renderLayer backdrop
            set.backdrop_size_based_on_nodes(renderlayer_backdrop, renderlayer_nodes)
            if check.need_move_to_the_right(renderlayer_backdrop, nodes_to_the_right_in_renderlayergroup_backdrop):
                update.nodes_to_the_right_position(
                    original_layer_w,
                    renderlayer_backdrop,
                    nodes_to_the_right_in_renderlayergroup_backdrop
                )

            # Adapt renderLayerGroup backdrop
            update.backdrop_size_after_update(
                renderlayergroup_backdrop,
                renderlayergroup_nodes,
                original_layer_w,
                renderlayer_backdrop
            )

            if check.need_move_to_the_right(renderlayergroup_backdrop, nodes_to_the_right_in_main):
                update.nodes_to_the_right_position(
                    original_group_w,
                    renderlayergroup_backdrop,
                    nodes_to_the_right_in_main
                )

            final_nodes = renderlayergroup_nodes + nodes_to_the_right_in_main
            update.backdrop_size_after_update(main_backdrop, final_nodes, original_group_w, renderlayergroup_backdrop)

        else:
            update.shuffle_and_downstream_horizontal_align(read_node, ext, layers_to_add)

    update.read_file(read_node, new_file)
    return True


#-----------Private Functions-----------
def _create_layers_to_add_shuffle_and_stamp_tree(read_node: Node, layers_to_add: dict, create_stamps: bool) -> list[Node]:
    new_nodes_created = []
    for index, layer_data in layers_to_add.items():
        new_nodes = generate.shuffle_for_given_layer(read_node, layer_data["name"])
        new_nodes_created.extend(new_nodes)

    if create_stamps:
        nodes_for_anchor = filter.dot_nodes(new_nodes_created)
        anchor_nodes = generate.anchors(nodes_for_anchor)
        stamps_nodes = generate.stamps(anchor_nodes)

        new_nodes_created.extend(anchor_nodes)
        new_nodes_created.extend(stamps_nodes)

    for node in new_nodes_created:
        set.identifier_knob(node, constants.LINKED_READ, read_node.name)

    return new_nodes_created
