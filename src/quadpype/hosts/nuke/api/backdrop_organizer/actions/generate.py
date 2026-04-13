from typing import Union

from quadpype.pipeline import split_hierarchy

from . import get, create, set, transform, check, align, calculate, constants
from ..entities import Node, Backdrop

from quadpype.lib import Logger

"""
generate.py
-----------
Provides high-level generation pipelines for creating and arranging groups
of Nuke nodes and backdrops in a single coordinated operation.

Combines creation, alignment, and identifier setup to build complete structures:
main backdrop layouts, layer decomposition trees (shuffle/remove/premult/dot),
anchor and stamp chains, and representation or publish backdrop hierarchies
derived from project settings.
"""

log = Logger.get_logger(__name__)

def main_backdrops(identifier: str = constants.MAIN_BACKDROP):
    for backdrop_profile in get.main_backdrops_profiles():
        create.backdrop(
            bd_name=backdrop_profile["name"],
            bd_color=backdrop_profile["color"],
            fill_backdrop=backdrop_profile["fill_backdrop"],
            bd_size=backdrop_profile["default_size"],
            font_size=constants.BACKDROP_FONT_SIZE,
            z_order=0,
            identifier=identifier
            )
    align.main_backdrops()

def shuffles_for_all_layers(input_node: Node, layers_data: dict = None) -> list[Node]:
    """Will generate the node tree to properly decompose all layers from the input_node.
    Will also align them."""
    if not layers_data:
        log.warning("No layers data given, abort this generation")
        return list()

    shuffle_nodes=[]
    remove_nodes=[]
    premult_nodes=[]
    dot_nodes=[]

    for index, layer_data in enumerate(layers_data.values()):
        layer_name = layer_data.get("name")

        shuffle = create.shuffle_node(input_node, layer_name)
        shuffle_nodes.append(shuffle)

        remove = create.remove_node(shuffle)
        remove_nodes.append(remove)

        premult = create.premult_node(remove)
        premult_nodes.append(premult)

        dot = create.dot_node(premult)
        dot_nodes.append(dot)
        set.knob_value(dot, 'label', f"{layer_name}")

    align.nodes_vertically([input_node, shuffle_nodes[0]], constants.SHUFFLE_Y_PADDING)
    align.nodes_horizontally(shuffle_nodes, constants.SHUFFLE_X_PADDING)
    transform.offset_nodes(shuffle_nodes, 0, constants.SHUFFLE_Y_PADDING)
    transform.offset_nodes(remove_nodes, 0, constants.REMOVE_Y_PADDING)
    transform.offset_nodes(premult_nodes, 0, constants.PREMULT_Y_PADDING)
    transform.offset_nodes(dot_nodes, 0, constants.DOT_Y_PADDING)

    return shuffle_nodes + remove_nodes + premult_nodes + dot_nodes

def anchors(input_nodes: Union[list[Node], Node]) -> list[Node]:
    """Create an anchor for each input_node and also align them."""
    anchor_nodes = []

    if not check.is_list(input_nodes):
        input_nodes = [input_nodes]

    for index, node in enumerate(input_nodes):
        title = get.knob_value(node, "label")
        if not title:
            title = node.name
        anchor = create.anchor_node(node, title)
        anchor_nodes.append(anchor)

    align.nodes_vertically([input_nodes[0], anchor_nodes[0]], constants.ANCHOR_Y_ALIGN_OFFSET)
    transform.offset_nodes(anchor_nodes[1:], 0, constants.ANCHOR_Y_PADDING)

    return anchor_nodes

def stamps(input_anchors: Union[list[Node], Node]) -> list[Node]:
    """Create a stamp for each input_node and also align them."""
    stamps_nodes = []

    if not check.is_list(input_anchors):
        input_anchors = [input_anchors]

    for index, node in enumerate(input_anchors):
        stamp = create.stamp_node(node)
        stamps_nodes.append(stamp)

    transform.offset_nodes(stamps_nodes, 0, constants.STAMP_Y_PADDING)

    return stamps_nodes

def shuffle_for_given_layer(input_node: Node, layer_name: str ) -> list[Node]:
    """Will generate the node tree to properly decompose for a given layer, from the input_node."""

    shuffle_nodes=[]
    remove_nodes=[]
    premult_nodes=[]
    dot_nodes=[]

    shuffle = create.shuffle_node(input_node, layer_name)
    shuffle_nodes.append(shuffle)

    remove = create.remove_node(shuffle)
    remove_nodes.append(remove)

    premult = create.premult_node(remove)
    premult_nodes.append(premult)

    dot = create.dot_node(premult)
    dot_nodes.append(dot)
    set.knob_value(dot, 'label', f"{layer_name}")

    transform.offset_nodes(shuffle_nodes, 0, constants.SHUFFLE_Y_PADDING)
    transform.offset_nodes(remove_nodes, 0, constants.REMOVE_Y_PADDING)
    transform.offset_nodes(premult_nodes, 0, constants.PREMULT_Y_PADDING)
    transform.offset_nodes(dot_nodes, 0, constants.DOT_Y_PADDING)

    return shuffle_nodes + remove_nodes + premult_nodes + dot_nodes

def representation_backdrops(data: dict) -> Backdrop:
    """Create all the backdrops for the representation based on the settings"""
    backdrop_profile = get.backdrop_load_profile_by_task(data)
    backdrop_hierarchies = get.resolved_backdrop_load_hierarchies(data)

    for hierarchy in backdrop_hierarchies:
        parent_backdrop = None
        previous_backdrop = None
        z_order = 0

        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        bd_color = backdrop_profile["backdrop_color"]

        colors = calculate.color_hierarchy(bd_color, hierarchy)
        for level, bd_name in enumerate(hierarchy):
            if level == 0:
                parent_backdrop = get.backdrop(bd_name)

                if parent_backdrop:
                    z_order = get.knob_value(parent_backdrop, "z_order")
                if check.is_main_backdrop(parent_backdrop):
                    continue

            elif 0 < level < (len(hierarchy) - 1):
                previous_backdrop = hierarchy[level - 1]
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            else:
                previous_backdrop = hierarchy[level - 1]
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            parent_backdrop = create.backdrop(
                bd_name=bd_name,
                bd_color=colors[level],
                fill_backdrop=backdrop_profile["fill_backdrop"],
                bd_size=backdrop_profile.get("default_size", constants.DEFAULT_BACKDROP_SIZE),
                font_size=constants.BACKDROP_FONT_SIZE,
                z_order=z_order,
                position=(-10000, -10000),
                identifier=constants.LOAD_BACKDROP
            )
            bd_color = [int(x * 0.75) for x in bd_color]
            set.identifier_knob(parent_backdrop, constants.PARENT_BACKDROP, previous_backdrop)

        return parent_backdrop

def representation_renderlayer_backdrops(data: dict, options: dict) -> Backdrop:
    """Create all the backdrops for the representation of a render layer based on the settings"""
    backdrop_profile = get.backdrop_load_profile_by_task(data)
    backdrop_hierarchies = get.resolved_backdrop_load_renderlayergroup_hierarchies(data, options=options)

    for hierarchy in backdrop_hierarchies:
        parent_backdrop = None
        previous_backdrop = None
        z_order = 0

        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        bd_color = backdrop_profile["backdrop_color"]

        colors = calculate.color_hierarchy(bd_color, hierarchy)
        for level, bd_name in enumerate(hierarchy):
            if level == 0:
                parent_backdrop = get.backdrop(bd_name)

                if parent_backdrop:
                    z_order = get.knob_value(parent_backdrop, "z_order")
                if check.is_main_backdrop(parent_backdrop):
                    continue

            elif 0 < level < (len(hierarchy) - 1):
                previous_backdrop = hierarchy[level - 1]
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            else:
                previous_backdrop = hierarchy[level - 1]
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            parent_backdrop = create.backdrop(
                bd_name=bd_name,
                bd_color=colors[level],
                fill_backdrop=backdrop_profile["fill_backdrop"],
                bd_size=backdrop_profile.get("default_size", constants.DEFAULT_BACKDROP_SIZE),
                font_size=constants.BACKDROP_FONT_SIZE,
                z_order=z_order,
                position=(-10000, -10000),
                identifier=constants.LOAD_RENDERLAYER_BACKDROP
            )
            bd_color = [int(x * 0.75) for x in bd_color]
            set.identifier_knob(parent_backdrop, constants.PARENT_BACKDROP, previous_backdrop)

        return parent_backdrop

def publish_backdrops(data: dict) -> Backdrop:
    """Create all the backdrops for the publish based on the settings"""
    backdrop_profile = get.backdrop_publish_profile_by_task(data)
    backdrop_hierarchies = get.resolved_backdrop_publish_hierarchies(data)

    for hierarchy in backdrop_hierarchies:
        parent_backdrop = None
        main_backdrop = None
        z_order = 0

        if check.is_string(hierarchy):
            hierarchy = split_hierarchy(hierarchy)

        bd_color = backdrop_profile["backdrop_color"]

        colors = calculate.color_hierarchy(bd_color, hierarchy)
        for level, bd_name in enumerate(hierarchy):
            if level == 0:
                parent_backdrop = get.backdrop(bd_name)
                main_backdrop = get.backdrop(bd_name)

                if parent_backdrop:
                    z_order = get.knob_value(parent_backdrop, "z_order")
                if check.is_main_backdrop(parent_backdrop):
                    continue

            elif 0 < level < (len(hierarchy) - 1):
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            else:
                z_order = get.knob_value(parent_backdrop, "z_order") + 1

            parent_backdrop = create.backdrop(
                bd_name=bd_name,
                bd_color=colors[level],
                font_size=constants.BACKDROP_FONT_SIZE,
                z_order=z_order,
                position=(-10000, -10000),
                identifier=constants.PUBLISH_BACKDROP
            )
            bd_color = [int(x * 0.75) for x in bd_color]
            set.identifier_knob(parent_backdrop, constants.PARENT_BACKDROP, main_backdrop.name)

        return parent_backdrop
