from . import check
from ..entities import Node, Backdrop

"""
filter.py
---------
Provides filtering utilities to extract subsets of nodes and backdrops based
on type, role, or pipeline attributes.

Covers hierarchy-level filtering (main, lower-level), pipe backdrop detection,
node class filtering (shuffle, dot, remove, premult, anchor, stamp, read),
and representation-based linking checks.
"""

def remove_main_backdrop(backdrops: list[Backdrop]) -> list[Backdrop]:
    """Remove the Main backdrops in a given hierarchy"""
    return [b for b in backdrops if not check.is_main_backdrop(b)]

def main_backdrop_from_hierarchy(backdrops: list[Backdrop]) -> Backdrop:
    """Return the Main Backdrop in a hierarchy"""
    return next((b for b in backdrops if check.is_main_backdrop(b)), None)

def lower_level_backdrop_from_hierarchy(backdrops: list[Backdrop]) -> Backdrop:
    """Return the First Backdrop in a hierarchy just after the Main Backdrop"""
    return next(b for b in backdrops if not check.is_main_backdrop(b))

def pipe_backdrop(backdrops: list[Backdrop]) -> list[Backdrop]:
    """Return only the backdrops that possess a pipe knob"""
    return [b for b in backdrops if check.is_pipe_node(b) and check.is_backdrop(b)]

def backdrops_just_before_main(backdrops: list[Backdrop]) -> list[Backdrop]:
    return [b for b in backdrops if check.is_backdrop_before_main_from_parent_backdrop(b) and check.is_backdrop(b)]

def highest_z_order(backdrops: list[Backdrop]) -> Backdrop:
    return max(backdrops, key=lambda bd: bd.nuke_entity.knob("z_order").value())

def linked_to_representation(node_list: list[Node], representation: str) -> list[Node]:
    return [n for n in node_list if check.is_linked_to_representation(n, representation)]

def nodes_in_given_backdrop(node_list: list[Node], backdrop: Backdrop):
    return [n for n in node_list if check.is_node_in_backdrop(n, backdrop)]

def shuffle_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_shuffle(n)]

def remove_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_remove(n)]

def premult_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_premult(n)]

def dot_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_dot(n)]

def read_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_dot(n)]

def anchor_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_anchor(n)]

def stamp_nodes(node_list: list[Node]) -> list[Node]:
    return [n for n in node_list if check.is_stamp(n)]
