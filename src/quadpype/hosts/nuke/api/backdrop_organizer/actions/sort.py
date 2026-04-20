from . import get
from ..entities import Node, Backdrop

"""
sort.py
-------
Provides sorting utilities for lists of nodes and backdrops.

Supports spatial ordering (left-to-right, right-to-left, by Y position),
z-order sorting for backdrops, and index-based ordering of shuffle nodes
relative to their associated layer data.
"""

def by_x_from_left_to_right(nodes: list[Node]):
    nodes.sort(key=lambda nd: nd.x)

def by_x_from_right_to_left(nodes: list[Node]):
    nodes.sort(key=lambda nd: nd.x, reverse=True)

def by_z_order(backdrops: list[Backdrop]):
    backdrops.sort(key=lambda bd: bd.z_order)

def by_y_from_up_to_down(nodes: list[Node]):
    nodes.sort(key=lambda nd: nd.y)

def by_y_from_down_to_up(nodes: list[Node]):
    nodes.sort(key=lambda nd: nd.y, reverse=True)

def shuffle_nodes_by_index(shuffle_nodes: list[Node], layers_data: dict) -> list[Node]:
    name_to_index = {data["name"]: int(index) for index, data in layers_data.items()}

    def get_index(node: Node) -> int:
        node_in = get.knob_value(node, "in")
        return name_to_index.get(node_in, -1)

    return sorted(shuffle_nodes, key=get_index, reverse=True)
