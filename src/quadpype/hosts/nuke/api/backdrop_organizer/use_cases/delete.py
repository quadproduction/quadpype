import nuke

from ..actions import delete, sort, get, filter, convert

"""
delete.py
---------
Provides deletion pipelines for cleanly removing representations and publish
instances from the Nuke node graph.

Handles full backdrop and inner node cleanup, optional removal of remaining
linked nodes outside the backdrop, and conditional deletion of empty
render layer group backdrops after a render layer is removed.
"""

def representation(read_node: nuke.Node):
    read_node = convert.node(read_node)
    representation_name = read_node.name

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)

    lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)

    delete.backdrop_and_nodes_within(lower_level_backdrop)
    delete.remaining_nodes(representation_name)

def renderlayer_representation(read_node: nuke.Node):
    read_node = convert.node(read_node)
    representation_name = read_node.name

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)

    renderlayergroup_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)
    renderlayer_backdrop = filter.highest_z_order(backdrops_with_read_node)

    delete.backdrop_and_nodes_within(renderlayer_backdrop)
    delete.remaining_nodes(representation_name)
    delete.remaining_renderlayergroup_backdrop(renderlayergroup_backdrop)

def publish(instance_node):
    instance_node = convert.node(instance_node)
    representation_name = instance_node.name

    backdrops_with_read_node = get.backdrops_containing_node(instance_node)
    sort.by_z_order(backdrops_with_read_node)

    lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)
    delete.backdrop_and_nodes_within(lower_level_backdrop)
    delete.remaining_nodes(representation_name)
