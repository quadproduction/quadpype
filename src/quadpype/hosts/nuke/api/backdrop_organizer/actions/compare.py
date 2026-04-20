from . import get, update
from ..entities import Node

"""
compare.py
----------
Provides comparison utilities for detecting layer variations between two versions
of a file associated with a Read node.

Temporarily swaps the file path on the node to inspect the new file's layers,
then restores the original, returning whether layers were added or removed.
"""

def layer_number(read_node: Node, ext: str, new_file: str) -> bool:
    old_file = get.knob_value(read_node, "file")
    old_layers_data = get.layers_from_node(read_node, ext)

    update.read_file(read_node, new_file)
    new_layers_data = get.layers_from_node(read_node, ext)

    update.read_file(read_node, old_file)

    return len(new_layers_data) > len(old_layers_data)

def layers_variations(read_node: Node, ext: str, new_file: str) -> tuple[dict, dict]:
    old_file = get.knob_value(read_node, "file")
    old_layers_data = get.layers_from_node(read_node, ext)

    update.read_file(read_node, new_file)
    new_layers_data = get.layers_from_node(read_node, ext)

    layers_to_add = get.layers_to_add(old_layers_data, new_layers_data)
    layers_to_delete = get.layers_to_delete(old_layers_data, new_layers_data)

    update.read_file(read_node, old_file)

    return layers_to_add, layers_to_delete
