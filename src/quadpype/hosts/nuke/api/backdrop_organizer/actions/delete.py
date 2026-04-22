from typing import Union
import nuke
from ..entities import Node, Backdrop
from . import sort, get, ask, filter, check

"""
delete.py
---------
Provides deletion utilities for Nuke nodes and backdrops.

Handles simple node removal, recursive backdrop cleanup (backdrop and its inner
nodes), and conditional deletion of remaining linked or orphaned nodes after
a representation or render layer group is removed.
"""

def simple_delete(nodes: Union[Node, Backdrop, list[Node], list[Backdrop]]):
    if not check.is_list(nodes):
        nodes = [nodes]
    for node in nodes:
        nuke.delete(node.nuke_entity)

def backdrop_and_nodes_within(backdrop: Backdrop):
    nodes_to_delete = get.nodes_in_backdrops(backdrop)
    simple_delete(nodes_to_delete)
    simple_delete(backdrop)

def remaining_nodes(representation_name):
    """Will search and ask for delete all linked nodes to the given representation that are outside its backdrop"""
    linked_nodes = get.nodes_linked_to_representation(representation_name)
    if linked_nodes:
        msg = "Node outside the representation Backdrop detected:\n\n" + "\n".join(f"* {n.name}" for n in linked_nodes)
        msg = f"{msg}\n\nDelete them too ?"
        proceed = ask.validation(msg)
        if not proceed:
            return
        simple_delete(linked_nodes)

def remaining_renderlayergroup_backdrop(renderlayergroup_backdrop):
    """Will search and delete all nodes in the given renderlayergroup backdrop"""
    remaining_nodes = get.nodes_in_backdrops(renderlayergroup_backdrop)
    if not remaining_nodes:
        simple_delete(renderlayergroup_backdrop)

def shuffles_and_downstream_from_layers_data(read_node: Node, layers_to_delete: dict):
    """Will search and delete all nodes going downstream starting from the shuffle.
     Consider only nodes in the backdrop linked to the read node"""

    if not layers_to_delete:
        return

    representation_name = read_node.name

    backdrops_with_read_node = get.backdrops_containing_node(read_node)
    sort.by_z_order(backdrops_with_read_node)
    lower_level_backdrop = filter.lower_level_backdrop_from_hierarchy(backdrops_with_read_node)

    representation_nodes = get.nodes_linked_to_representation(representation_name)
    shuffle_nodes = filter.shuffle_nodes(representation_nodes)
    shuffle_nodes_to_delete = []
    layer_names_to_delete = [layer_data["name"] for layer_data in layers_to_delete.values()]

    for shuffle_node in shuffle_nodes:
        shuffle_node_layer = get.knob_value(shuffle_node, "in")
        if shuffle_node_layer in layer_names_to_delete:
            shuffle_nodes_to_delete.append(shuffle_node)

    for shuffle_node in shuffle_nodes_to_delete:
        downstream_nodes = get.downstream_nodes(shuffle_node)
        downstream_nodes = filter.nodes_in_given_backdrop(downstream_nodes, lower_level_backdrop)
        simple_delete(downstream_nodes)
        simple_delete(shuffle_node)
