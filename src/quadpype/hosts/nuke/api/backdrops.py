import nuke
from enum import Enum

from quadpype.pipeline.settings import extract_width_and_height
from quadpype.settings import get_project_settings
from quadpype.lib import filter_profiles


from quadpype.pipeline import (
    get_current_project_name,
    get_current_host_name,
    split_hierarchy,
    format_data,
    get_workfile_build_template,
    get_task_hierarchy_templates,
    get_resolved_name
)

from .lib import (
    decompose_layers,
    generate_stamps,
    create_precomp_merge
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
    """Retrieve the color for the backdrop depending on the task type
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

    return profile.get("backdrop_color", []) if profiles else []


#-----------Creator-----------------

def create_backdrop(bd_name, bd_color, bd_size=None, font_size=75, z_order=0, position=None):
    """Create a backdrop at the center
    Args:
        bd_name(str): name of the backdrop.
        bd_color(list/tuple): rgba color code, 0-255.
        bd_size(str): the width and height.
        font_size(int): title size.
        z_order(int): depth of the backdrop position.
        position(tuple): the position to set it.
    Return:
        A nuke Backdrop.
        """
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
    """
    Generate all the backdrop hierarchies based on a string like:
        'IMPORT_ASSETS/BG_BG_Conformation'
        IMPORT_ASSETS
        |-> BG_BG_Conformation

    Args:
        backdrops_hierarchy (list or str): a list of str or a str of one or more hierarchy.
        data(dict): template data of the asset.
    Return:
        A nuke Backdrop.
        """
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

def create_main_backdrops_from_list():
    """ Generate all the main backdrops and organize them.
    Return:
        bool: True if success
    """

    for backdrop_profile in get_main_backdrops_profiles():
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
    """Will align and re-arrange all the main backdrops, depending on given position rule."""
    for backdrop_profile in backdrop_profiles:

        position = EnumPosition[backdrop_profile["position"]].value
        if not position:
            continue

        backdrop = _get_backdrop_by_name(backdrop_profile["name"])
        backdrop_reference = _get_backdrop_by_name(backdrop_profile["backdrop_ref"])
        if backdrop and backdrop_reference:
            align_backdrops(backdrop_reference, backdrop, position)

def align_backdrops(backdrop_ref, backdrop_to_move, alignment):
    """Align a given backdrop depending on a reference backdrop"""
    margin = 15

    x1 = backdrop_ref['xpos'].value()
    y1 = backdrop_ref['ypos'].value()
    w1 = backdrop_ref['bdwidth'].value()
    h1 = backdrop_ref['bdheight'].value()

    w2 = backdrop_to_move['bdwidth'].value()
    h2 = backdrop_to_move['bdheight'].value()

    if alignment == "to_left":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 - w2 - margin
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif alignment == "to_right":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 + w1 + margin
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif alignment == "on_top":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 - h2 - margin
        backdrop_to_move["ypos"].setValue(int(new_y))
        return True

    elif alignment == "under":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 + h1 + margin
        backdrop_to_move["ypos"].setValue(new_y)
        return True

    elif alignment == "inside":

        new_y = y1 + margin*10
        new_x = x1 + margin*2
        inside_backdrops = _get_backdrops_in_backdrops(backdrop_ref)
        if inside_backdrops:
            inside_nodes_w, inside_nodes_h, inside_node_x, inside_node_y = _get_nodes_dimensions(
                                                                            _get_backdrops_in_backdrops(backdrop_ref)
                                                                        )
            new_x = new_x + inside_nodes_w + margin
            new_y = inside_node_y

            if backdrop_to_move not in inside_backdrops:
                inside_backdrops.append(backdrop_to_move)
            resize_backdrop_based_on_nodes(backdrop_ref, backdrop_to_move)

        backdrop_to_move["xpos"].setValue(new_x)
        backdrop_to_move["ypos"].setValue(new_y)
        return True

    else:
        return False

def adjust_main_backdrops(main_backdrop=None, backdrop=None, nodes_in_main_backdrops=None):
    """Will align, re-arrange, re-size and move all nodes in all the main backdrops, depending on given position rule.
    Args:
        main_backdrop(BackdropNode): the main backdrop.
        backdrop(BackdropNode): the new backdrop to align.
        nodes_in_main_backdrops(dict): A dict of the nodes already in each main backdrop
        """
    if main_backdrop:
        backdrops_in_main_backdrop = _get_backdrops_in_backdrops(main_backdrop)

        if backdrop and backdrop not in backdrops_in_main_backdrop:
            backdrops_in_main_backdrop.append(backdrop)

        resize_backdrop_based_on_nodes(main_backdrop, backdrops_in_main_backdrop, padding=150)

    actual_main_backdrops_positions = dict()
    for main_backdrop in nodes_in_main_backdrops.keys():
        actual_main_backdrops_positions[main_backdrop] = list(
            _get_nodes_dimensions(_get_backdrop_by_name(main_backdrop))
        )

    align_main_backdrops_from_list(get_main_backdrops_profiles())

    new_main_backdrops_positions = dict()
    for main_backdrops in nodes_in_main_backdrops.keys():
        new_main_backdrops_positions[main_backdrops] = list(
            _get_nodes_dimensions(_get_backdrop_by_name(main_backdrops)))

    for main_backdrop, nodes in nodes_in_main_backdrops.items():
        old_x = actual_main_backdrops_positions[main_backdrop][2]
        old_y = actual_main_backdrops_positions[main_backdrop][3]
        new_x = new_main_backdrops_positions[main_backdrop][2]
        new_y = new_main_backdrops_positions[main_backdrop][3]

        offset_x = new_x-old_x
        offset_y = new_y-old_y

        for node in nodes:
            node['xpos'].setValue(node.xpos() + offset_x)
            node['ypos'].setValue(node.ypos() + offset_y)


#-----------Operations-----------------

def move_backdrop(backdrop, new_x, new_y):
    """Move the backdrop to given coordinate"""
    old_x = backdrop["xpos"].value()
    old_y = backdrop["ypos"].value()
    backdrop["xpos"].setValue(new_x)
    backdrop["ypos"].setValue(new_y)
    inside_backdrops = _get_backdrops_in_backdrops(backdrop)
    for bd in inside_backdrops:
        inside_nodes = _get_nodes_in_backdrops(backdrop)
        move_backdrop(bd, old_x+new_x, old_y+new_y)
        move_nodes_in_backdrop(inside_nodes, backdrop)

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
    """Will resize a backdrop to match the size of a given group of nodes."""
    new_width, new_height, new_x, new_y = _get_nodes_dimensions(nodes)
    bd_width, bd_height, bd_x, bd_y = _get_nodes_dimensions(backdrop)

    new_bd_width = bd_width
    new_bd_height = bd_height
    if new_width + padding > bd_width:
        new_bd_width = new_width+padding
    if new_height + padding > bd_height:
        new_bd_height = new_height+padding*2

    resize_backdrop(backdrop, new_bd_width, new_bd_height)

def move_nodes_in_backdrop(nodes, backdrop, padding = 50):
    """Will move the given list of nodes into the given backdrop.
    Will resize the backdrop if necessary"""
    if not nodes:
        return
    if not isinstance(nodes, list):
        nodes = [nodes]
    resize_backdrop_based_on_nodes(backdrop, nodes, padding)

    bd_x = backdrop['xpos'].value() + padding/2
    bd_y = backdrop['ypos'].value() + padding

    nodes_to_move = sorted(nodes, key=lambda n: n.ypos())

    offset_x = bd_x - min([n.xpos() for n in nodes_to_move])
    offset_y = bd_y - min([n.ypos() for n in nodes_to_move])

    for node in nodes_to_move:
        node['xpos'].setValue(node.xpos() + offset_x)
        node['ypos'].setValue(node.ypos() + offset_y + padding/3)


#-----------Utils-----------------

def get_nodes_in_mains_backdrops():
    return_nodes_in_main_bd = dict()
    for backdrop_profile in get_main_backdrops_profiles():
        return_nodes_in_main_bd[backdrop_profile["name"]] = _get_nodes_in_backdrops(
            _get_backdrop_by_name(backdrop_profile["name"])
        )
    return return_nodes_in_main_bd

def get_first_backdrop_in_first_template(backdrops_hierarchy):
    return _get_backdrop_by_name(split_hierarchy(backdrops_hierarchy[0])[0])

def _backdrop_exists(backdrop_name):
    return backdrop_name in [node["name"].value() for node in nuke.allNodes("BackdropNode")]

def _get_backdrops_in_backdrops(backdrop):
    return [n for n in backdrop.getNodes() if n.Class() == "BackdropNode"]

def _get_nodes_in_backdrops(backdrop):
    return [n for n in backdrop.getNodes()]

def _get_nodes_dimensions(nodes):
    if not nodes:
        return
    if not isinstance(nodes, list):
        return nodes.screenWidth(), nodes.screenHeight(), nodes.xpos() , nodes.ypos()

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


#-----------Nuke Functions-----------------

def pre_organize_by_backdrop():
    create_main_backdrops_from_list()
    nodes_in_main_backdrops = get_nodes_in_mains_backdrops()
    adjust_main_backdrops(nodes_in_main_backdrops=nodes_in_main_backdrops)
    return nodes_in_main_backdrops

def organize_by_backdrop(context, read_node, nodes_in_main_backdrops,
                         is_prep_layer_compatible, prep_layers, create_stamps, pre_comp):

    nodes = [read_node]

    new_nodes = dict()
    if is_prep_layer_compatible and prep_layers:
        new_nodes = decompose_layers(read_node)
        for new_nodes_list in new_nodes.values():
            nodes.extend(new_nodes_list)

    if create_stamps:
        if is_prep_layer_compatible and prep_layers:
            new_stamp_nodes = generate_stamps(new_nodes["dot_nodes"])
        else:
            new_stamp_nodes = generate_stamps(read_node)
        new_nodes.update(new_stamp_nodes)
        for new_nodes_list in new_stamp_nodes.values():
            nodes.extend(new_nodes_list)

    if is_prep_layer_compatible and pre_comp and prep_layers:
        send_nodes = new_nodes["dot_nodes"]
        if create_stamps:
            send_nodes = new_nodes["stamp_nodes"]

        new_precomp_nodes = create_precomp_merge(send_nodes)
        new_nodes.update(new_precomp_nodes)
        for new_nodes_list in new_precomp_nodes.values():
            nodes.extend(new_nodes_list)

    template_data = format_data(
        original_data=context['representation'],
        filter_variant=True,
        app=get_current_host_name()
    )

    backdrop_templates = get_task_hierarchy_templates(
        template_data,
        task=context["representation"]["context"]["task"]['name']
    )

    storage_backdrop = None
    main_backdrop = None
    if backdrop_templates:
        backdrops_hierarchy = [
            get_resolved_name(
                data=template_data,
                template=template
            )
            for template in backdrop_templates
        ]
        storage_backdrop = create_backdrops_from_hierarchy(backdrops_hierarchy, template_data)

        if storage_backdrop:
            move_nodes_in_backdrop(nodes, storage_backdrop)
            main_backdrop = get_first_backdrop_in_first_template(backdrops_hierarchy)
            adjust_main_backdrops(main_backdrop=main_backdrop,
                                  backdrop=storage_backdrop,
                                  nodes_in_main_backdrops=nodes_in_main_backdrops)

    return main_backdrop, storage_backdrop, nodes

def reorganize_inside_main_backdrop(main_backdrop_name):
    padding = 15

    main_backdrop = _get_backdrop_by_name(main_backdrop_name)
    backdrops_in_main_backdrop = _get_backdrops_in_backdrops(main_backdrop)

    backdrops_in_main_backdrop.sort(key=lambda bd: bd['xpos'].value())

    current_x =  main_backdrop['xpos'].value() + padding * 2

    for backdrop in backdrops_in_main_backdrop:
        nodes = _get_nodes_in_backdrops(backdrop)
        backdrop['xpos'].setValue(current_x)
        current_x += backdrop['bdwidth'].value() + padding
        move_nodes_in_backdrop(nodes, backdrop)

    return main_backdrop_name, main_backdrop, backdrops_in_main_backdrop
