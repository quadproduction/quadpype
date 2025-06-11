import nuke
from enum import Enum

from quadpype.pipeline.settings import extract_width_and_height
from quadpype.settings import get_project_settings
from quadpype.lib import filter_profiles


from quadpype.pipeline import (
    get_current_task_name,
    get_current_project_name,
    get_current_host_name,
    split_hierarchy,
    get_workfile_build_template
)

DEFAULT_POSITION = "notSpec"

class EnumPosition(Enum):
    notSpec = None
    left = "to_left"
    right = "to_right"
    top = "on_top"
    bottom = "under"


#-----------Settings Getter-----------------

def get_main_backdrops_profiles():
    """Retrieve the main backdrops profiles from settings"""
    project_settings = get_project_settings(get_current_project_name())
    try:
        profiles = (
            project_settings
            [get_current_host_name()]
            ["load"]
            ["main_backdrops_manager"]
            ["backdrop_profiles"]
        )
    except Exception:
        raise KeyError("Project has no template set for backdrop_profiles")

    return profiles

def get_task_hierarchy_color(data, task=None):
    """Retrieve the template for the folders depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        task (str): fill to bypass task in data dict
    Return:
        str: A template that can be solved later
    """
    profiles = get_workfile_build_template("working_hierarchy_templates_by_tasks")
    profile_key = {
        "task_types": data["task"]["name"] if not task else task,
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)

    if not profile:
        return []

    return profile.get("backdrop_color", [])


#-----------Creator-----------------

def create_backdrop(bd_name, bd_color, bd_size=None, font_size=75, z_order=0, position=None):
    """Create a backdrop at the center"""
    if not  bd_size:
        bd_size = "50x50"
    width, height = extract_width_and_height(bd_size)

    if not position:
        center_x = int(nuke.root().width() / 2)
        center_y = int(nuke.root().height() / 2)
        xpos = center_x
        ypos = center_y - int(height) // 2

    else:
        xpos, ypos = position

    backdrop = nuke.createNode("BackdropNode")
    move_backdrop(backdrop, xpos, ypos)
    resize_backdrop(backdrop, int(width), int(height))
    color_backdrop(backdrop, bd_color)

    backdrop["label"].setValue(bd_name)
    backdrop.setName(bd_name)

    backdrop["z_order"].setValue(z_order)
    backdrop["note_font_size"].setValue(font_size)
    return backdrop

def create_backdrops_from_hierarchy(backdrops_hierarchy, data):
    return_backdrop = None
    bd_color = get_task_hierarchy_color(data)
    z_order = 0
    if not bd_color:
        bd_color = [150, 150, 150, 0]

    if isinstance(backdrops_hierarchy, str):
        backdrops_hierarchy = [backdrops_hierarchy]

    for hierarchy in backdrops_hierarchy:
        if isinstance(hierarchy, str):
            hierarchy = split_hierarchy(hierarchy)

        for level, bd_name in enumerate(hierarchy):
            if _backdrop_exists(bd_name):
                continue
            if level == 0:
                parent = _get_backdrop_by_name(bd_name)
                if parent:
                    z_order = parent["z_order"].value()
            else:
                parent = _get_backdrop_by_name(hierarchy[level - 1])
                z_order = parent["z_order"].value() + 1
            return_backdrop = create_backdrop(
                                    bd_name=bd_name,
                                    bd_color=bd_color,
                                    font_size=50,
                                    z_order = z_order,
                                    position=(-10000,-10000)
                                )
            align_backdrops(parent, return_backdrop, "inside")

    return return_backdrop

def create_main_backdrops_from_list(backdrop_profiles):
    """ Generate all the main backdrops and organize them.
    Args:
        backdrop_profiles (dict): a dict containing all the data to create a backdrop, resize it and place it.
    Return:
        bool: True if success
    """

    for backdrop_profile in backdrop_profiles:
        if _backdrop_exists(backdrop_profile["name"]):
            continue
        create_backdrop(bd_name=backdrop_profile["name"],
                        bd_color=backdrop_profile["color"],
                        bd_size=backdrop_profile["default_size"],
                        font_size=75,
                        z_order=0)

    return True


#-----------Align-----------------

def align_main_backdrops_from_list(backdrop_profiles):
    align_success = False

    for backdrop_profile in backdrop_profiles:
        if not _backdrop_exists(backdrop_profile["name"]):
            create_backdrop(backdrop_profile["name"],
                            backdrop_profile["color"],
                            backdrop_profile["default_size"],
                            font_size=75,
                            z_order=0)

        position = EnumPosition[backdrop_profile["position"]].value
        if not position:
            continue

        backdrop = _get_backdrop_by_name(backdrop_profile["name"])
        backdrop_reference = _get_backdrop_by_name(backdrop_profile["backdrop_ref"])
        if backdrop and backdrop_reference:
            align_success = align_backdrops(backdrop_reference, backdrop, position)

    return align_success

def align_backdrops(backdrop_ref, backdrop_to_move, position):
    """Align a given backdrop depending on a reference backdrop"""
    margin = 15

    x1 = backdrop_ref['xpos'].value()
    y1 = backdrop_ref['ypos'].value()
    w1 = backdrop_ref['bdwidth'].value()
    h1 = backdrop_ref['bdheight'].value()

    x2 = backdrop_to_move['xpos'].value()
    y2 = backdrop_to_move['ypos'].value()
    w2 = backdrop_to_move['bdwidth'].value()
    h2 = backdrop_to_move['bdheight'].value()

    if position == "to_left":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 - w2 - margin
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif position == "to_right":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 + w1 + margin
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif position == "on_top":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 - h2 - margin
        backdrop_to_move["ypos"].setValue(int(new_y))
        return True

    elif position == "under":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 + h1 + margin
        backdrop_to_move["ypos"].setValue(new_y)
        return True

    elif position == "inside":

        new_y = y1 + margin*10
        new_x = x1 + margin*2
        inside_backdrops = _get_backdrops_in_backdrops(backdrop_ref)
        if inside_backdrops:
            inside_nodes_w, inside_nodes_h, inside_node_x, inside_node_y = _get_nodes_dimensions(
                                                                            _get_backdrops_in_backdrops(backdrop_ref)
                                                                        )

            new_x = new_x + inside_nodes_w + margin
            new_y = inside_node_y
        backdrop_to_move["xpos"].setValue(new_x)
        backdrop_to_move["ypos"].setValue(new_y)
        return True

    else:
        return False


#-----------Operations-----------------

def move_backdrop(backdrop, new_x, new_y):
    """Move the backdrop to given coordinate"""
    backdrop["xpos"].setValue(new_x)
    backdrop["ypos"].setValue(new_y)

def resize_backdrop(backdrop, new_width, new_height):
    """Resize the backdrop to given coordinate"""
    backdrop["bdwidth"].setValue(new_width)
    backdrop["bdheight"].setValue(new_height)

def color_backdrop(backdrop, bd_color):
    """Color the given backdrop"""
    if isinstance(bd_color, list):
        bd_color = tuple(bd_color)
    r, g, b, a = bd_color
    backdrop["tile_color"].setValue(_convert_rgb_to_nuke_color(r, g, b))

def resize_backdrop_based_on_nodes(backdrop, nodes, padding = 50):
    new_width, new_height, new_x, new_y = _get_nodes_dimensions(nodes)
    resize_backdrop(backdrop, new_width+padding, new_height+padding*2)

def move_nodes_in_backdrop(nodes, backdrop, padding = 50):
    if not nodes:
        return
    if not isinstance(nodes, list):
        nodes = [nodes]
    resize_backdrop_based_on_nodes(backdrop, nodes, padding)

    # Calculer la nouvelle position de base dans le backdrop
    bd_x = backdrop['xpos'].value() + padding/2
    bd_y = backdrop['ypos'].value() + padding

    # Trier les nodes à déplacer par position Y pour garder l'ordre
    nodes_to_move = sorted(nodes, key=lambda n: n.ypos())

    offset_x = bd_x - min([n.xpos() for n in nodes_to_move])
    offset_y = bd_y - min([n.ypos() for n in nodes_to_move])

    for node in nodes_to_move:
        node['xpos'].setValue(node.xpos() + offset_x)
        node['ypos'].setValue(node.ypos() + offset_y)

#-----------Utils-----------------

def _backdrop_exists(backdrop_name):
    return backdrop_name in [node["name"].value() for node in nuke.allNodes("BackdropNode")]

def _get_backdrops_in_backdrops(backdrop):
    return [n for n in backdrop.getNodes() if n.Class() == "BackdropNode"]

def _get_nodes_dimensions(nodes):
    if not nodes:
        return
    if not isinstance(nodes, list):
        nodes = [nodes]
    # Récupérer les coordonnées extrêmes des nodes
    x_positions = [n.xpos() for n in nodes]
    y_positions = [n.ypos() for n in nodes]
    widths = [n.screenWidth() for n in nodes]
    heights = [n.screenHeight() for n in nodes]

    min_x = min(x_positions)
    min_y = min(y_positions)
    max_x = max(x + w for x, w in zip(x_positions, widths))
    max_y = max(y + h for y, h in zip(y_positions, heights))

    bd_width = max_x - min_x
    bd_height = max_y - min_y

    return bd_width, bd_height, min_x, min_y

def _convert_rgb_to_nuke_color(r, g, b):
    return (r << 24) + (g << 16) + (b << 8)

def _get_backdrop_by_name(bd_name):
    """Get a backdrop depending on the given name"""
    return nuke.toNode(bd_name) if nuke.toNode(bd_name).Class() == "BackdropNode" else None
