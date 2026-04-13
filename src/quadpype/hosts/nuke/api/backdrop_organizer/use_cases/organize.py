import nuke
import logging

from quadpype.lib import Logger
log = Logger.get_logger(__name__)

from ..actions import get, set, filter, transform, generate, check, convert, align, constants, update
from ..entities import Node

from quadpype.pipeline.workfile.workfile_template_builder import TemplateProfileNotFound

"""
organize.py
-----------
Provides orchestration pipelines for loading and publishing representations in Nuke.

Coordinates the full sequence of main backdrop generation, node tree creation
(shuffle/anchor/stamp), backdrop hierarchy setup, alignment, and identifier tagging
for standard representations, render layer representations, and publish instances.
Exposes safe public wrappers that roll back all created nodes on template errors.
"""

#-----------Load Representation-----------
def _organize_representation(read_node: nuke.Node, options: dict, context: dict):
    generate.main_backdrops()
    nodes_in_main_backdrops = get.nodes_in_mains_backdrops()

    read_node = convert.node(read_node)
    transform.move(read_node, -100000, -100000)

    new_nodes_created = _create_shuffle_and_stamp_tree(read_node, options)

    repre_backdrop = generate.representation_backdrops(context)

    align.nodes_in_backdrop(new_nodes_created, repre_backdrop)
    align.representation_backdrops(context)

    new_nodes_created = get.nodes_in_backdrops(repre_backdrop)
    for node in new_nodes_created:
        set.identifier_knob(node, constants.LINKED_READ, read_node.name)

    main_backdrop = get.main_backdrop_from_parent_backdrop(repre_backdrop)
    nodes_in_main_backdrops[main_backdrop.name].extend(new_nodes_created)

    align.representation_backdrops_in_main(context)
    align.main_backdrops(nodes_in_main_backdrops)

def representation_with_except(read_node: nuke.Node, options: dict, context: dict):
    nodes_before = list(nuke.allNodes())
    try:
        _organize_representation(read_node, options, context)

    except TemplateProfileNotFound:
        for n in nuke.allNodes():
            if n not in nodes_before:
                nuke.delete(n)
        nuke.delete(read_node)
        raise Exception(f"No template found in loader for "
                        f"{context['representation']['context']['task']['name']}")


#-----------Load RenderLayer Representation-----------
def _organize_renderlayer_representation(read_node: nuke.Node, options: dict, context: dict):

    generate.main_backdrops()
    nodes_in_main_backdrops = get.nodes_in_mains_backdrops()

    renderlayer_backdrop = generate.representation_renderlayer_backdrops(context, options)
    main_backdrop = get.main_backdrop_from_parent_backdrop(renderlayer_backdrop)

    renderlayergroup_backdrop = get.backdrop_before_main_from_parent_backdrop(renderlayer_backdrop)
    renderlayergroup_nodes = get.nodes_in_backdrops(renderlayergroup_backdrop)

    read_node = convert.node(read_node)

    new_nodes_created = _create_shuffle_and_stamp_tree(read_node, options)

    if check.reposition_in_main(renderlayer_backdrop):
        renderlayergroup_nodes.extend(new_nodes_created)
        renderlayergroup_nodes.append(renderlayer_backdrop)

        original_w, _ = renderlayergroup_backdrop.size

        nodes_to_the_right = get.pipe_nodes_to_the_right(renderlayergroup_backdrop)

        align.nodes_in_backdrop(new_nodes_created, renderlayer_backdrop)
        align.representation_renderlayergroup_backdrops(context, options)

        nodes_to_the_right = [n for n in nodes_to_the_right if not check.is_linked_to_representation(n, read_node.name)]
        if check.need_move_to_the_right(renderlayer_backdrop, nodes_to_the_right):
            update.nodes_to_the_right_position(original_w, renderlayergroup_backdrop, nodes_to_the_right)

        final_nodes = nodes_to_the_right + renderlayergroup_nodes
        update.backdrop_size_after_update(main_backdrop, final_nodes, original_w, renderlayergroup_backdrop)

    else:
        align.nodes_in_backdrop(new_nodes_created, renderlayer_backdrop)
        align.representation_renderlayergroup_backdrops(context, options)
        align.representation_renderlayergroup_backdrops_in_main(context, options)

    new_nodes_created = get.nodes_in_backdrops(renderlayer_backdrop)
    for node in new_nodes_created:
        set.identifier_knob(node, constants.LINKED_READ, read_node.name)

    nodes_in_main_backdrops[main_backdrop.name].extend(new_nodes_created)

    align.main_backdrops(nodes_in_main_backdrops)

def renderlayer_representation_with_except(read_node: nuke.Node, options: dict, context: dict):
    nodes_before = list(nuke.allNodes())
    try:
        _organize_renderlayer_representation(read_node, options, context)

    except TemplateProfileNotFound:
        for n in nuke.allNodes():
            if n not in nodes_before:
                nuke.delete(n)
        nuke.delete(read_node)
        raise Exception(f"No template found in loader for "
                        f"{context['representation']['context']['task']['name']}")


#-----------Create Publish Representation-----------
def _organize_publish(instance_node: nuke.Node, instance_data: dict):
    generate.main_backdrops()
    nodes_in_main_backdrops = get.nodes_in_mains_backdrops()

    instance_node = convert.node(instance_node)
    transform.move(instance_node, -100000, -100000)

    publish_backdrop = generate.publish_backdrops(instance_data)
    align.nodes_in_backdrop(
        instance_node,
        publish_backdrop,
        constants.NODES_IN_PUBLISH_X_PADDING,
        constants.NODES_IN_PUBLISH_Y_PADDING,
        constants.BACKDROP_PUBLISH_W_PADDING,
        constants.BACKDROP_PUBLISH_H_PADDING
    )
    align.publish_backdrops(instance_data)

    set.identifier_knob(instance_node, constants.LINKED_READ, instance_node.name)

    align.publish_backdrops_in_main(instance_data)
    align.main_backdrops(nodes_in_main_backdrops)

def publish_with_except(instance_node: nuke.Node, instance_data: dict):
    nodes_before = list(nuke.allNodes())
    try:
        _organize_publish(instance_node, instance_data)

    except TemplateProfileNotFound:
        for n in nuke.allNodes():
            if n not in nodes_before:
                nuke.delete(n)
        nuke.delete(instance_node)
        raise Exception(f"No template found in loader for "
                        f"{instance_data['task']}")


#-----------Private Functions-----------
def _create_shuffle_and_stamp_tree(read_node: Node, options: dict) -> list[Node]:
    ext = options["ext"]
    prep_layers = options["prep_layers"]
    create_stamps = options["create_stamps"]

    layers_data = get.layers_from_node(read_node, ext)
    new_nodes_created = [read_node]
    new_nodes = generate.shuffles_for_all_layers(read_node, layers_data)
    new_nodes_created.extend(new_nodes)

    if create_stamps:
        if check.is_decompose_layer_compatible(ext) and prep_layers:
            nodes_for_anchor = filter.dot_nodes(new_nodes)
        else:
            nodes_for_anchor = read_node
        anchor_nodes = generate.anchors(nodes_for_anchor)
        stamps_nodes = generate.stamps(anchor_nodes)

        new_nodes_created.extend(anchor_nodes)
        new_nodes_created.extend(stamps_nodes)

    return new_nodes_created
