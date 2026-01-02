import nuke, nukescripts
import ast
from enum import Enum

from quadpype.pipeline.settings import extract_width_and_height
from quadpype.settings import get_project_settings
from quadpype.lib import (
    filter_profiles,
    Logger
)

from quadpype.pipeline.workfile.workfile_template_builder import (
    TemplateProfileNotFound
)
from quadpype.pipeline import (
    get_current_project_name,
    get_current_host_name,
    split_hierarchy,
    format_data,
    get_workfile_build_template,
    get_task_hierarchy_templates,
    get_resolved_name,
    get_family_hierarchy_templates,
    get_create_build_template
)

from .lib import (
    compare_layers,
    decompose_layers,
    generate_stamps,
    create_precomp_merge,
    get_downstream_nodes,
    classify_downstream_nodes_inputs
)

from quadpype.hosts.nuke.nuke_addon.stamps.stamps_autoClickedOk import getDefaultTitle

log = Logger.get_logger(__name__)

DEFAULT_FONT_SIZE = 50
BACKDROP_FONT_SIZE = 75
BACKDROP_PADDING = 15
MAIN_BACKDROP_PADDING = 150
BACKDROP_INSIDE_PADDING = 50
DEFAULT_WIDTH = 50
NODE_SPACING = 110
DOT_PADDING = 34

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

def get_renderlayer_template():
    """Retrieve the renderlayer backdrop template from settings"""
    project_settings = get_project_settings(get_current_project_name())
    try:
        template = (
            project_settings
            [get_current_host_name()]
            ["load"]
            ["renderLayerLoader"]
            ["backdrop_name_template"]
        )
    except Exception:
        raise KeyError("Project has no template set for renderLayerLoader")

    return template

def get_task_hierarchy_settings_data(data, task=None):
    """Retrieve the settings data for the backdrop depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        task (str): fill to bypass task in data dict
    Return:
        dict: A dict of data of the corresponding settings
    """
    # If from create write instance
    if data.get("id") == "pyblish.avalon.instance":
        profiles = get_create_build_template()
        profile_key = {
            "families": data["family"]
        }
    else:
        profiles = get_workfile_build_template("working_hierarchy_templates_by_tasks")
        profile_key = {
            "task_types": data["task"]["name"] if not task else task,
            "families": data["family"]
        }

    profile = filter_profiles(profiles, profile_key)
    if not profile:
        raise TemplateProfileNotFound

    return profile


#-----------Creator-----------------

def create_backdrop(bd_name, bd_color, bd_size=None, fill_backdrop=True,
                    font_size=BACKDROP_FONT_SIZE, z_order=0, position=None):
    """Create a backdrop at the center
    Args:
        bd_name(str): name of the backdrop.
        bd_color(list/tuple): rgba color code, 0-255.
        fill_backdrop(bool): set the appearance of the backdrop.
        bd_size(str): the width and height.
        font_size(int): title size.
        z_order(int): depth of the backdrop position.
        position(tuple): the position to set it.
    Return:
        A nuke Backdrop.
        """
    if not bd_size:
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
    if not fill_backdrop:
        backdrop["appearance"].setValue("Border")
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
    z_order = 0

    if isinstance(backdrops_hierarchy, str):
        backdrops_hierarchy = [backdrops_hierarchy]

    for hierarchy in backdrops_hierarchy:
        if isinstance(hierarchy, str):
            hierarchy = split_hierarchy(hierarchy)

        for level, bd_name in enumerate(hierarchy):
            if _backdrop_exists(bd_name):
                continue

            bd_settings = get_task_hierarchy_settings_data(data)
            fill_backdrop =  bd_settings.get("fill_backdrop", True)
            bd_color = bd_settings.get("backdrop_color", [])
            if not bd_color:
                bd_color = [150, 150, 150, 0]

            if level == 0:
                parent = _get_backdrop_by_name(bd_name)
                if parent:
                    z_order = parent["z_order"].value()

            elif 0 < level < (len(hierarchy)-1):
                bd_color = [int(x * 0.75) for x in bd_color]
                parent = _get_backdrop_by_name(hierarchy[level - 1])
                z_order = parent["z_order"].value() + 1

            else:
                parent = _get_backdrop_by_name(hierarchy[level - 1])
                z_order = parent["z_order"].value() + 1
            return_backdrop = create_backdrop(
                                    bd_name=bd_name,
                                    bd_color=bd_color,
                                    fill_backdrop=fill_backdrop,
                                    font_size=DEFAULT_FONT_SIZE,
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
                        fill_backdrop=backdrop_profile["fill_backdrop"],
                        bd_size=backdrop_profile["default_size"],
                        font_size=BACKDROP_FONT_SIZE,
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

def align_backdrops(backdrop_ref, backdrop_to_move, alignment, padding=BACKDROP_PADDING):
    """Align a given backdrop depending on a reference backdrop"""

    x1 = backdrop_ref['xpos'].value()
    y1 = backdrop_ref['ypos'].value()
    w1 = backdrop_ref['bdwidth'].value()
    h1 = backdrop_ref['bdheight'].value()

    w2 = backdrop_to_move['bdwidth'].value()
    h2 = backdrop_to_move['bdheight'].value()

    if alignment == "to_left":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 - w2 - padding
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif alignment == "to_right":
        backdrop_to_move["ypos"].setValue(y1)
        new_x = x1 + w1 + padding
        backdrop_to_move["xpos"].setValue(int(new_x))
        return True

    elif alignment == "on_top":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 - h2 - padding
        backdrop_to_move["ypos"].setValue(int(new_y))
        return True

    elif alignment == "under":
        backdrop_to_move["xpos"].setValue(x1)
        new_y = y1 + h1 + padding
        backdrop_to_move["ypos"].setValue(new_y)
        return True

    elif alignment == "inside":

        new_y = y1 + padding*10
        new_x = x1 + padding*2
        inside_backdrops = _get_backdrops_in_backdrops(backdrop_ref)
        if inside_backdrops:
            inside_nodes_w, inside_nodes_h, inside_node_x, inside_node_y = _get_nodes_dimensions(
                                                                            _get_backdrops_in_backdrops(backdrop_ref)
                                                                        )
            new_x = new_x + inside_nodes_w + padding
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

        resize_backdrop_based_on_nodes(main_backdrop, backdrops_in_main_backdrop, padding=MAIN_BACKDROP_PADDING)

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
        inside_nodes = get_nodes_in_backdrops(backdrop)
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

def resize_backdrop_based_on_nodes(backdrop, nodes, padding=BACKDROP_INSIDE_PADDING, shrink=False):
    """Will resize a backdrop to match the size of a given group of nodes."""
    new_width, new_height, new_x, new_y = _get_nodes_dimensions(nodes)
    bd_width, bd_height, bd_x, bd_y = _get_nodes_dimensions(backdrop)

    new_bd_width = bd_width
    new_bd_height = bd_height
    if new_width + padding > bd_width or shrink:
        new_bd_width = new_width+padding
    if new_height + padding > bd_height or shrink:
        new_bd_height = new_height+padding*2

    resize_backdrop(backdrop, new_bd_width, new_bd_height)

def move_nodes_in_backdrop(nodes, backdrop, padding=BACKDROP_INSIDE_PADDING):
    """Will move the given list of nodes into the given backdrop.
    Will resize the backdrop if necessary"""
    if not nodes:
        return
    if not isinstance(nodes, list):
        nodes = [nodes]
    resize_backdrop_based_on_nodes(backdrop, nodes, padding)
    ret = list()
    bd_x = backdrop['xpos'].value() + padding/2
    bd_y = backdrop['ypos'].value() + padding

    nodes_to_move = sorted(nodes, key=lambda n: n.ypos())

    offset_x = bd_x - min([n.xpos() for n in nodes_to_move])
    offset_y = bd_y - min([n.ypos() for n in nodes_to_move])

    for node in nodes_to_move:
        node['xpos'].setValue(node.xpos() + offset_x)
        node['ypos'].setValue(node.ypos() + offset_y + padding/3)
        ret.append((node.name(), node.xpos(), node.ypos(), (node.xpos() + offset_x), (node.ypos() + offset_y + padding/3)))
    return ret

def move_backdrop_inside_backdrop(backdrop_to_move, main_backdrop, padding=BACKDROP_INSIDE_PADDING):
    """Will move the backdrop_to_move inside main_backdrop with all the nodes
    Will resize the main_backdrop if necessary"""

    adjust_backdrop_padding = int(padding * 1.5)

    backdrop_to_move_nodes = get_nodes_in_backdrops(backdrop_to_move)
    nodes_to_move = sorted(backdrop_to_move_nodes, key=lambda n: n.ypos())

    backdrops_in_main_backdrop = _get_backdrops_in_backdrops(main_backdrop)
    backdrops_in_main_backdrop.sort(key=lambda bd: bd['xpos'].value())

    if backdrop_to_move in backdrops_in_main_backdrop:
        backdrops_in_main_backdrop.remove(backdrop_to_move)

    additional_padding = 0
    if backdrops_in_main_backdrop:
        additional_padding = sum([b['bdwidth'].value() for b in backdrops_in_main_backdrop])
        additional_padding = additional_padding + (adjust_backdrop_padding * len(backdrops_in_main_backdrop))

        bd_move_width, bd_move_height, bd_move_x, bd_move_y = _get_nodes_dimensions(backdrop_to_move)
        main_backdrop['bdwidth'].setValue(main_backdrop['bdwidth'].value() + bd_move_width + adjust_backdrop_padding)

    else:
        resize_backdrop_based_on_nodes(main_backdrop, backdrop_to_move, adjust_backdrop_padding)

    backdrop_to_move['xpos'].setValue(main_backdrop['xpos'].value() + adjust_backdrop_padding / 2 + additional_padding)
    backdrop_to_move['ypos'].setValue(main_backdrop['ypos'].value() + adjust_backdrop_padding)

    bd_x = backdrop_to_move['xpos'].value() + padding / 2
    bd_y = backdrop_to_move['ypos'].value() + padding

    offset_x = bd_x - min([n.xpos() for n in nodes_to_move])
    offset_y = bd_y - min([n.ypos() for n in nodes_to_move])

    for node in nodes_to_move:
        node['xpos'].setValue(node.xpos() + offset_x)
        node['ypos'].setValue(node.ypos() + offset_y + padding / 3)

#-----------Utils-----------------

def get_nodes_in_mains_backdrops():
    return_nodes_in_main_bd = dict()
    for backdrop_profile in get_main_backdrops_profiles():
        return_nodes_in_main_bd[backdrop_profile["name"]] = get_nodes_in_backdrops(
            _get_backdrop_by_name(backdrop_profile["name"])
        )
    return return_nodes_in_main_bd

def get_first_backdrop_in_first_template(backdrops_hierarchy):
    return _get_backdrop_by_name(split_hierarchy(backdrops_hierarchy[0])[0])

def _backdrop_exists(backdrop_name):
    return backdrop_name in [node["name"].value() for node in nuke.allNodes("BackdropNode")]

def _get_backdrops_in_backdrops(backdrop):
    return [n for n in backdrop.getNodes() if n.Class() == "BackdropNode"]

def get_nodes_in_backdrops(backdrop):
    return [n for n in backdrop.getNodes()]

def _get_node_names_in_backdrops(backdrop):
    return [n.name() for n in backdrop.getNodes()]

def _get_nodes_dimensions(nodes):
    if not nodes:
        return
    if not isinstance(nodes, list):
        if nodes.Class() == "BackdropNode":
            return nodes["bdwidth"].value(), nodes["bdheight"].value(), nodes["xpos"].value(), nodes["ypos"].value()
        else:
            return nodes.screenWidth(), nodes.screenHeight(), nodes.xpos() , nodes.ypos()

    x_positions = [n.xpos() for n in nodes]
    y_positions = [n.ypos() for n in nodes]
    # A condition is necessary, because when a node is newly created, screenWidth return 0 and not the correct width
    widths = [n.screenWidth() if (n.screenWidth() > 0) else DEFAULT_WIDTH for n in nodes]
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

def organize_by_backdrop(data, node, nodes_in_main_backdrops, options,
                         padding=BACKDROP_INSIDE_PADDING, unique_number="001"):
    """
    Create and organize in backdrop the loaded media or the created write instance node
    Args:
        data(dict): data to the context of the loaded element or data of the render create
        node: the nuke node to treat, a Read or a Group
        nodes_in_main_backdrops(dict): A dict representing nodes in each main backdrops
        options(dict): A dict of load options
            The primary options are:
            - is_prep_layer_compatible: is the file composed of layer like an exr or psd
            - prep_layers: Will decompose the layers
            - create_stamps: trigger the creation of stamps per layers
            - pre_comp: Generate the merge tree
            - ext: Needed to know how to get the layers from media (psd and exr work differently).
            - subset_group: Name of the subsetgroup, aka part of a RenderLayer, if any
        padding(int): padding to add inside the backdrop
        unique_number(str): a sting of "###" to indicate the unique number
    """
    nodes = [node]

    # If created write instance, no options are given
    if options:
        is_prep_layer_compatible = options.get("is_prep_layer_compatible", True)
        prep_layers = options.get("prep_layers", True)
        create_stamps = options.get("create_stamps", True)
        pre_comp = options.get("pre_comp", True)
        ext = options.get("ext", "")

        new_nodes = dict()
        if is_prep_layer_compatible and prep_layers:
            new_nodes = decompose_layers(node, ext=ext)
            for new_nodes_list in new_nodes.values():
                nodes.extend(new_nodes_list)

        if create_stamps:
            if is_prep_layer_compatible and prep_layers:
                new_stamp_nodes = generate_stamps(new_nodes["dot_nodes"])
            else:
                new_stamp_nodes = generate_stamps(node)
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

    template_data = data
    # If loaded element, "representation" is present, so set the data.
    if data.get("representation"):
        template_data = format_data(
            original_data=data["representation"],
            filter_variant=True,
            app=get_current_host_name()
        )
        backdrop_templates = get_task_hierarchy_templates(
            template_data,
            task=data["representation"]["context"]["task"]["name"]
        )
    #Else if we create a write render instance
    else:
        backdrop_templates = get_family_hierarchy_templates(
            template_data
        )

    main_backdrop = None
    if not backdrop_templates:
        raise TemplateProfileNotFound

    subset_group = ""

    if options.get("subset_group", False):
        subset_group_template = get_renderlayer_template()
        template_data["subset_group"] = options["subset_group"]

        subset_group = get_resolved_name(
            data=template_data,
            template=subset_group_template,
            unique_number=unique_number
        )

        new_hierarchy = []
        for hierarchy in backdrop_templates:
            parts = hierarchy.split("/")
            parts.insert(-1, subset_group_template)
            new_hierarchy.append("/".join(parts))
        backdrop_templates = new_hierarchy

    backdrops_hierarchy = [
        get_resolved_name(
            data=template_data,
            template=template,
            unique_number=unique_number
        )
        for template in backdrop_templates
    ]
    storage_backdrop = create_backdrops_from_hierarchy(backdrops_hierarchy, template_data)

    if not storage_backdrop:
        return main_backdrop, storage_backdrop, subset_group, nodes

    main_backdrop = get_first_backdrop_in_first_template(backdrops_hierarchy)
    if isinstance(backdrops_hierarchy, str):
        backdrops_hierarchy = [backdrops_hierarchy]

    for hierarchy in backdrops_hierarchy:
        if isinstance(hierarchy, str):
            hierarchy = split_hierarchy(hierarchy)

        revert_hierarchy = list(reversed(hierarchy))
        for level, bd_name in enumerate(revert_hierarchy):
            backdrop = _get_backdrop_by_name(bd_name)

            if level == len(revert_hierarchy)-1:
                continue
            parent_backdrop = _get_backdrop_by_name(revert_hierarchy[level + 1])

            if level == 0:
                move_nodes_in_backdrop(nodes, backdrop, padding=padding)
                main_backdrop = get_first_backdrop_in_first_template(backdrops_hierarchy)
                adjust_main_backdrops(main_backdrop=main_backdrop,
                                      backdrop=backdrop,
                                      nodes_in_main_backdrops=nodes_in_main_backdrops)
                continue

            if 0 < level < (len(hierarchy) - 1):
                child_backdrop = _get_backdrop_by_name(revert_hierarchy[level-1])
                move_backdrop_inside_backdrop(child_backdrop, backdrop)

            adjust_main_backdrops(main_backdrop=parent_backdrop,
                                  backdrop=backdrop,
                                  nodes_in_main_backdrops=nodes_in_main_backdrops)

    return main_backdrop, storage_backdrop, subset_group, nodes

def update_by_backdrop(container, old_layers, new_layers, ask_proceed=True):
    """
    Will update the elements based on options. Will keep extra nodes and reorganized all.
    Args:
        container(dict): Data of the element treated
        old_layers(dict): A dict compiling layers data on previous version
        new_layers(dict): A dict compiling layers data on the new version
        ask_proceed(bool): A bool to activate or not the dialog window to alert of layers change.
    """
    main_backdrop = _get_backdrop_by_name(container.get("main_backdrop"))
    storage_backdrop = _get_backdrop_by_name(container.get("storage_backdrop"))
    read_node = container.get("node")
    options = ast.literal_eval(container.get("options"))

    prep_layers = options.get("prep_layers", False)
    create_stamps = options.get("create_stamps", False)
    pre_comp = options.get("pre_comp", False)
    is_prep_layer_compatible = options.get("is_prep_layer_compatible", False)
    ext = options.get("ext", None)
    subset_group = options.get("subset_group", False)

    node_names_in_backdrop = _get_node_names_in_backdrops(storage_backdrop)

    # Var declarations
    new_created_node_names = list()
    shuffle_dot_nodes = dict()
    shuffle_nodes = dict()
    new_stamp_nodes = dict()
    create_stamp_nodes = dict()
    stamp_nodes = dict()
    existing_node_inputs = dict()
    existing_merge_nodes = set()


    anchor_nodes = [nuke.toNode(n) for n in node_names_in_backdrop if nuke.toNode(n) and
                    nuke.toNode(n).Class() == "NoOp"]

    # If only stamp, only update
    if (create_stamps and not pre_comp and not prep_layers) or not is_prep_layer_compatible:
        new_title = getDefaultTitle(read_node)
        anchor_nodes[0]["title"].setValue(new_title)
        return

    #Move nodes to not interfere with existing
    if not subset_group:
        move_backdrop(storage_backdrop, 200000, 200000)
        move_nodes_in_backdrop([nuke.toNode(n) for n in node_names_in_backdrop if nuke.toNode(n)], storage_backdrop)

    reorganize_inside_main_backdrop(container.get("main_backdrop"))

    origin_x = read_node.xpos() + (NODE_SPACING * max([int(i) for i in new_layers.keys()]))
    nodes_in_main_backdrops = get_nodes_in_mains_backdrops()
    new_layers_to_add, old_layers_to_delete = (compare_layers(old_layers, new_layers, ask_proceed))

    nukescripts.clear_selection_recursive()

    # Process decompose layer
    if prep_layers and is_prep_layer_compatible:
        stop_class = "NoOp"
        include_stop_node = False
        if not create_stamps:
            stop_class = "Dot"
            include_stop_node = True
        # Generate Node Data and Downstream
        shuffle_nodes = {
            nuke.toNode(n)['in'].value() : {
                "name" : n,
                "downstream_nodes" : get_downstream_nodes(
                 nuke.toNode(n),
                 visited=set(),
                 stop_class=stop_class,
                 include_stop_node=include_stop_node
                )
            }
            for n in node_names_in_backdrop if _is_node_and_shuffle_node(n)
        }
        shuffle_y_origin = max([nuke.toNode(n["name"]).ypos() for n in shuffle_nodes.values()])
        # Delete Old
        delete_dict = dict()
        for index, old_layer_data in old_layers_to_delete.items():
            if old_layer_data["name"] in shuffle_nodes.keys():
                shuffle_node = nuke.toNode(shuffle_nodes[old_layer_data["name"]]["name"])
                if not shuffle_node:
                    continue
                # Unplug Input to prevent auto reconnect of Nuke
                shuffle_node.setInput(0, None)
                downstream_nodes = shuffle_nodes[old_layer_data["name"]]["downstream_nodes"]
                # Security in case get_downstream_nodes failed in Generate Node Data and Downstream
                # For no known reason, sometimes get_downstream_nodes() return None
                if not downstream_nodes:
                    downstream_nodes = get_downstream_nodes(shuffle_node,
                                                            visited=set(),
                                                            stop_class=stop_class,
                                                            include_stop_node=include_stop_node)
                sorted_downstream_nodes = sorted(list(downstream_nodes), key=lambda n: n.ypos())
                # Store the existing Merge Tree for later treatment if the layer "0" is deleted
                if int(index) == 0 and pre_comp:
                    existing_merge_nodes = get_downstream_nodes(sorted_downstream_nodes[-1],
                                                                visited=set(),
                                                                stop_class="Dot",
                                                                include_stop_node=False)

                if not create_stamps and pre_comp:
                    precomp_extra_nodes = get_downstream_nodes(sorted_downstream_nodes[-1],
                                                            visited=set(),
                                                            stop_class="Dot",
                                                            include_stop_node=False)
                    sorted_downstream_nodes.extend(list(precomp_extra_nodes))
                # Store nodes to delete by names, except Merge, they will be treated later
                delete_dict[shuffle_node] = [n.name() for n in sorted_downstream_nodes if n.Class() != "Merge2"]

        #Proceed to delete all nodes related to old layers that are not present in the new layers
        for shuffle_node, sorted_downstream_nodes_to_delete in delete_dict.items():
            nuke.delete(shuffle_node)
            for node_to_delete in sorted_downstream_nodes_to_delete:
                if not nuke.toNode(node_to_delete):
                    continue
                nuke.delete(nuke.toNode(node_to_delete))

        # Process New
        for index, new_layer_data in new_layers.items():
            # If exists, move nodes and store datas
            if new_layer_data["name"] in shuffle_nodes.keys():
                shuffle_node = nuke.toNode(shuffle_nodes[new_layer_data["name"]]["name"])
                shuffle_node["xpos"].setValue(origin_x - (NODE_SPACING * int(index)))
                downstream_nodes = shuffle_nodes[new_layer_data["name"]]["downstream_nodes"]
                # Security in case get_downstream_nodes failed in Generate Node Data and Downstream
                # For no known reason, sometimes get_downstream_nodes() return None
                if not downstream_nodes:
                    downstream_nodes = get_downstream_nodes(shuffle_node,
                                                            visited=set(),
                                                            stop_class=stop_class,
                                                            include_stop_node=include_stop_node)
                sorted_downstream_nodes = sorted(list(downstream_nodes), key=lambda n: n.ypos())
                last_node = sorted_downstream_nodes[-1]
                #If the old layer 0 is present in new layers, but at a different index, retrieve the merge tree from it.
                if _is_old_layer_zero_at_a_different_index(old_layers, new_layer_data):
                    existing_merge_nodes = get_downstream_nodes(last_node,
                                                                visited=set(),
                                                                stop_class="Dot",
                                                                include_stop_node=False)
                # Move downstream Nodes
                for node in sorted_downstream_nodes:
                    dot_offset = 0
                    if node.Class() == "Dot":
                        dot_offset = DOT_PADDING
                        shuffle_dot_nodes[index] = node
                    node["xpos"].setValue(shuffle_node.xpos() + dot_offset)

                #Store existing extra nodes between last dot and merge tree
                if not create_stamps and pre_comp:
                    stop_class = "Dot"
                    # If the old layer 0 is present in new layers, but at a different index, it's connected to a merge
                    # and not a dot
                    if _is_old_layer_zero_at_a_different_index(old_layers, new_layer_data):
                        stop_class = "Merge2"
                    downstream_dot_nodes = get_downstream_nodes(last_node,
                                                                visited=set(),
                                                                stop_class=stop_class,
                                                                include_stop_node=True)
                    sorted_downstream_dot_nodes = sorted(list(downstream_dot_nodes), key=lambda n: n.ypos())
                    if sorted_downstream_dot_nodes:
                        existing_node_inputs[last_node.name()] = classify_downstream_nodes_inputs(
                            sorted_downstream_dot_nodes)
            # Else Create
            else:
                new_shuffle_nodes = decompose_layers(read_node,
                                                     specific_layer={index:new_layers[index]},
                                                     coordinates=[origin_x - (NODE_SPACING * int(index)),
                                                                  shuffle_y_origin],
                                                     ext=ext
                                                     )
                #Store newly created dots for merge tree re-creation
                shuffle_dot_nodes[index] = new_shuffle_nodes["dot_nodes"][0]
                for new_node_list in new_shuffle_nodes.values():
                    new_created_node_names.extend(n.name() for n in new_node_list)

        nukescripts.clear_selection_recursive()

    # Process Stamps
    if create_stamps and is_prep_layer_compatible:
        anchor_nodes = {nuke.toNode(n)['title'].value(): n for n in  node_names_in_backdrop if nuke.toNode(n) and
                         nuke.toNode(n).Class() == "NoOp"}
        stamp_nodes = {nuke.toNode(n)['title'].value(): n for n in node_names_in_backdrop if nuke.toNode(n) and
                         nuke.toNode(n).Class() == "PostageStamp"}

        # Delete Old and store datas
        delete_dict = dict()
        for index, old_layer_data in old_layers_to_delete.items():
            if old_layer_data["name"] in anchor_nodes.keys():
                stop_class = "Dot"
                # Store the existing Merge Tree for later treatment if the layer "0" is deleted
                if int(index) == 0 and pre_comp:
                    existing_merge_nodes = get_downstream_nodes(nuke.toNode(stamp_nodes[old_layer_data["name"]]),
                                                                visited=set(),
                                                                stop_class="Dot",
                                                                include_stop_node=False)
                    stop_class = "Merge2"

                stamp_downstream_nodes = get_downstream_nodes(nuke.toNode(stamp_nodes[old_layer_data["name"]]),
                                                                visited=set(),
                                                                stop_class=stop_class,
                                                                include_stop_node=False)
                # Store nodes to delete by names, except Merge, they will be treated later
                delete_dict[old_layer_data["name"]] = [n.name() for n in stamp_downstream_nodes if
                                                       n.Class() != "Merge2"]

        # Proceed to delete all nodes related to old layers that are not present in the new layers
        for node_names, sorted_downstream_nodes_to_delete in delete_dict.items():
            nuke.delete(nuke.toNode(anchor_nodes[node_names]))
            nuke.delete(nuke.toNode(stamp_nodes[node_names]))
            for node_to_delete in sorted_downstream_nodes_to_delete:
                if not nuke.toNode(node_to_delete):
                    continue
                nuke.delete(nuke.toNode(node_to_delete))

        # Process New
        for index, new_layer_data in new_layers.items():
            # If exists, move nodes and store downstream nodes
            if new_layer_data["name"] in stamp_nodes.keys():
                anchor_node = nuke.toNode(anchor_nodes[new_layer_data["name"]])
                anchor_node["xpos"].setValue(origin_x - NODE_SPACING * int(index))
                stamp_node = nuke.toNode(stamp_nodes[new_layer_data["name"]])
                stamp_node["xpos"].setValue(origin_x - NODE_SPACING * int(index))
                create_stamp_nodes[index] = stamp_node
                stop_class = "Dot"
                # If the old layer 0 is present in new layers, but at a different index, it's connected to a merge
                # and not a dot
                if _is_old_layer_zero_at_a_different_index(old_layers, new_layer_data):
                    stop_class = "Merge2"
                stamp_downstream_nodes = get_downstream_nodes(stamp_node,
                                                              visited=set(),
                                                              stop_class=stop_class,
                                                              include_stop_node=True)

                sorted_downstream_nodes = sorted(list(stamp_downstream_nodes), key=lambda n: n.ypos())
                if sorted_downstream_nodes:
                    existing_node_inputs[stamp_node.name()] = classify_downstream_nodes_inputs(sorted_downstream_nodes)

                #Retrieve Merge tree from moved stamp node if pre_comp
                if _is_old_layer_zero_at_a_different_index(old_layers, new_layer_data) and pre_comp:
                    existing_merge_nodes = get_downstream_nodes(stamp_node,
                                                                 visited=set(),
                                                                 stop_class="Dot",
                                                                 include_stop_node=False)
            # Else Create
            else:
                new_create_stamp_nodes = generate_stamps(shuffle_dot_nodes[index])
                # Store newly created dots for merge tree re-creation
                new_stamp_nodes[index] = new_create_stamp_nodes["stamp_nodes"]
                create_stamp_nodes[index] = new_create_stamp_nodes["stamp_nodes"][0]
                for new_node_list in new_create_stamp_nodes.values():
                    new_created_node_names.extend(n.name() for n in new_node_list)

        nukescripts.clear_selection_recursive()

    # Process Merge tree
    if pre_comp and is_prep_layer_compatible:
        iter_nodes = dict()
        #Depending on options, the start nodes aren't the same
        if prep_layers and not create_stamps:
            iter_nodes = dict(sorted(shuffle_dot_nodes.items(), key=lambda x: int(x[0]), reverse=True))
        if create_stamps:
            iter_nodes = dict(sorted(create_stamp_nodes.items(), key=lambda x: int(x[0]), reverse=True))

        existing_merge_nodes = [n for n in existing_merge_nodes if n.Class() == "Merge2"]
        last_merge_output_nodes = sorted(list(get_downstream_nodes((sorted(existing_merge_nodes,
                                                                           key=lambda n: n.ypos())[-1]),
                                                                   stop_class="Dot",
                                                                   include_stop_node=True)),
                                         key=lambda n: n.ypos())
        #Deconnect last merge node output
        last_merge_output_nodes[0].setInput(0, None)

        #Delete all existing tree and related dot
        for merge_node in existing_merge_nodes:
            nuke.delete(merge_node.input(1))
            nuke.delete(merge_node)

        # Create the new merge tree, and treating the reconnection at the same time
        new_created_merge_nodes = create_precomp_merge([v for v in iter_nodes.values()],
                                                       last_merge_output_nodes,
                                                       existing_node_inputs)
        for new_node_list in new_created_merge_nodes.values():
            new_created_node_names.extend(n.name() for n in new_node_list)

    node_names_in_backdrop.extend(new_created_node_names)
    nodes_in_backdrop = {nuke.toNode(n) for n in node_names_in_backdrop if nuke.toNode(n)}

    # Adjust backdrop organisation
    if not subset_group:
        resize_backdrop_based_on_nodes(storage_backdrop, list(nodes_in_backdrop), shrink=True)
        align_backdrops(main_backdrop, storage_backdrop, "inside")
        move_nodes_in_backdrop(list(nodes_in_backdrop), storage_backdrop)
    adjust_main_backdrops(main_backdrop=main_backdrop,
                          backdrop=storage_backdrop,
                          nodes_in_main_backdrops=nodes_in_main_backdrops)

    return

def _is_node_and_shuffle_node(node):
    return nuke.toNode(node) and nuke.toNode(node).Class() == "Shuffle"

def _is_old_layer_zero_at_a_different_index(old_layers, new_layer_data):
    return next((k for k, v in old_layers.items() if v.get("name") == new_layer_data["name"]), None) == "0"

def reorganize_inside_main_backdrop(main_backdrop_name):
    padding = 15

    main_backdrop = _get_backdrop_by_name(main_backdrop_name)
    backdrops_in_main_backdrop = _get_backdrops_in_backdrops(main_backdrop)

    backdrops_in_main_backdrop.sort(key=lambda bd: bd['xpos'].value())

    current_x =  main_backdrop['xpos'].value() + padding * 2

    for backdrop in backdrops_in_main_backdrop:
        backdrops_in_backdrop = _get_backdrops_in_backdrops(backdrop)
        for bd in backdrops_in_backdrop:
            if bd not in backdrops_in_main_backdrop:
                continue
            backdrops_in_main_backdrop.remove(bd)
        nodes = get_nodes_in_backdrops(backdrop)
        backdrop['xpos'].setValue(current_x)
        main_backdrop['bdwidth'].setValue(main_backdrop.xpos() + current_x)
        current_x += backdrop['bdwidth'].value() + padding
        move_nodes_in_backdrop(nodes, backdrop)

    main_backdrop['bdwidth'].setValue(main_backdrop.xpos() + current_x)
    pre_organize_by_backdrop()

    return
