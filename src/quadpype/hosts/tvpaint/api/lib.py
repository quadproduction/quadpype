import os
import logging
import tempfile
from pathlib import Path

from quadpype.hosts.tvpaint.api import communication_server

log = logging.getLogger(__name__)


def execute_george(george_script, communicator=None):
    if not communicator:
        communicator = communication_server.CommunicationWrapper.communicator
    return communicator.execute_george(george_script)


def execute_george_through_file(george_script, communicator=None):
    """Execute george script with temp file.

    Allows to execute multiline george script without stopping websocket
    client.

    On windows make sure script does not contain paths with backwards
    slashes in paths, TVPaint won't execute properly in that case.

    Args:
        george_script (str): George script to execute. May be multilined.
    """
    if not communicator:
        communicator = communication_server.CommunicationWrapper.communicator

    return communicator.execute_george_through_file(george_script)


def parse_layers_data(data, only_names=False):
    """Parse layers data loaded in 'get_layers_data'."""
    layers = []
    layers_raw = data.split("\n")
    for layer_raw in layers_raw:
        layer_raw = layer_raw.strip()
        if not layer_raw:
            continue
        if only_names:
            (
                name, layer_id
            ) = layer_raw.split("|")
            layer = {
                "name": name,
                "layer_id": int(layer_id)
            }

        else:
            (
                layer_id, group_id, visible, position, opacity, name,
                layer_type,
                frame_start, frame_end, prelighttable, postlighttable,
                selected, editable, sencil_state, is_current
            ) = layer_raw.split("|")
            layer = {
                "layer_id": int(layer_id),
                "group_id": int(group_id),
                "visible": visible == "ON",
                "position": int(position),
                "opacity": get_layer_opacity(layer_id),
                "name": name,
                "type": layer_type,
                "frame_start": int(frame_start),
                "frame_end": int(frame_end),
                "prelighttable": prelighttable == "1",
                "postlighttable": postlighttable == "1",
                "selected": selected == "1",
                "editable": editable == "1",
                "sencil_state": sencil_state,
                "is_current": is_current == "1"
            }
        layers.append(layer)
    return layers


def get_layers_data_george_script(output_filepath, layer_ids=None, only_names=False):
    """Prepare george script which will collect all layers from workfile."""
    output_filepath = output_filepath.replace("\\", "/")
    george_script_lines = [
        # Variable containing full path to output file
        "output_path = \"{}\"".format(output_filepath),
        # Get Current Layer ID
        "tv_LayerCurrentID",
        "current_layer_id = result"
    ]
    # Script part for getting and storing layer information to temp
    layer_data_getter = (
        # Get information about layer's group
        "tv_layercolor \"get\" layer_id",
        "group_id = result",
        "tv_LayerInfo layer_id",
        (
            "PARSE result visible position opacity name"
            " type startFrame endFrame prelighttable postlighttable"
            " selected editable sencilState"
        ),
        # Check if layer ID match `tv_LayerCurrentID`
        "is_current=0",
        "IF CMP(current_layer_id, layer_id)==1",
        # - mark layer as selected if layer id match to current layer id
        "is_current=1",
        "selected=1",
        "END",
    )

    line_data = (
            "line = layer_id'|'group_id'|'visible'|'position'|'opacity'|'"
            "name'|'type'|'startFrame'|'endFrame'|'prelighttable'|'"
            "postlighttable'|'selected'|'editable'|'sencilState'|'is_current",
        )
    if only_names:
        line_data = (
            "line = name'|'layer_id",
        )

    layer_data_getter = layer_data_getter + line_data

    write_line = (
        # Write data to output file
        "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' line",
    )

    layer_data_getter = layer_data_getter + write_line

    # Collect data for all layers if layers are not specified
    if layer_ids is None:
        george_script_lines.extend((
            # Layer loop variables
            "loop = 1",
            "idx = 0",
            # Layers loop
            "WHILE loop",
            "tv_LayerGetID idx",
            "layer_id = result",
            "idx = idx + 1",
            # Stop loop if layer_id is "NONE"
            "IF CMP(layer_id, \"NONE\")==1",
            "loop = 0",
            "ELSE",
            *layer_data_getter,
            "END",
            "END"
        ))
    else:
        for layer_id in layer_ids:
            george_script_lines.append("layer_id = {}".format(layer_id))
            george_script_lines.extend(layer_data_getter)

    return "\n".join(george_script_lines)


def layers_data(layer_ids=None, communicator=None):
    """Backwards compatible function of 'get_layers_data'."""
    return get_layers_data(layer_ids, communicator)


def get_layers_data(layer_ids=None, communicator=None, only_names=False):
    """Collect all layers information from currently opened workfile."""
    output_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    output_file.close()
    if layer_ids is not None and isinstance(layer_ids, int):
        layer_ids = [layer_ids]

    output_filepath = output_file.name

    george_script = get_layers_data_george_script(output_filepath, layer_ids, only_names)

    execute_george_through_file(george_script, communicator)

    with open(output_filepath, "r") as stream:
        data = stream.read()

    output = parse_layers_data(data, only_names)
    os.remove(output_filepath)
    return output


def parse_group_data(data):
    """Parse group data collected in 'get_groups_data'."""
    output = []
    groups_raw = data.split("\n")
    for group_raw in groups_raw:
        group_raw = group_raw.strip()
        if not group_raw:
            continue

        parts = group_raw.split("|")
        # Check for length and concatenate 2 last items until length match
        # - this happens if name contain spaces
        while len(parts) > 6:
            last_item = parts.pop(-1)
            parts[-1] = "|".join([parts[-1], last_item])
        clip_id, group_id, red, green, blue, name = parts

        group = {
            "group_id": int(group_id),
            "name": name,
            "clip_id": int(clip_id),
            "red": int(red),
            "green": int(green),
            "blue": int(blue),
        }
        output.append(group)
    return output


def groups_data(communicator=None):
    """Backwards compatible function of 'get_groups_data'."""
    return get_groups_data(communicator)


def get_groups_data(communicator=None):
    """Information about groups from current workfile."""
    output_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    output_file.close()

    output_filepath = output_file.name.replace("\\", "/")
    george_script_lines = (
        # Variable containing full path to output file
        "output_path = \"{}\"".format(output_filepath),
        "empty = 0",
        # Loop over 26 groups which is ATM maximum possible (in 11.7)
        # - ref: https://www.tvpaint.com/forum/viewtopic.php?t=13880
        "FOR idx = 1 TO 26",
        # Receive information about groups
        "tv_layercolor \"getcolor\" 0 idx",
        "PARSE result clip_id group_index c_red c_green c_blue group_name",
        # Create and add line to output file
        "line = clip_id'|'group_index'|'c_red'|'c_green'|'c_blue'|'group_name",
        "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' line",
        "END",
    )
    george_script = "\n".join(george_script_lines)
    execute_george_through_file(george_script, communicator)

    with open(output_filepath, "r") as stream:
        data = stream.read()

    output = parse_group_data(data)
    os.remove(output_filepath)
    return output


def get_layers_pre_post_behavior(layer_ids, communicator=None):
    """Collect data about pre and post behavior of layer ids.

    Pre and Post behaviors is enumerator of possible values:
    - "none"
    - "repeat"
    - "pingpong"
    - "hold"

    Example output:
    ```json
    {
        0: {
            "pre": "none",
            "post": "repeat"
        }
    }
    ```

    Returns:
        dict: Key is layer id value is dictionary with "pre" and "post" keys.
    """
    # Skip if is empty
    if not layer_ids:
        return {}

    # Auto convert to list
    if not isinstance(layer_ids, (list, set, tuple)):
        layer_ids = [layer_ids]

    # Prepare temp file
    output_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    output_file.close()

    output_filepath = output_file.name.replace("\\", "/")
    george_script_lines = [
        # Variable containing full path to output file
        "output_path = \"{}\"".format(output_filepath),
    ]
    for layer_id in layer_ids:
        george_script_lines.extend([
            "layer_id = {}".format(layer_id),
            "tv_layerprebehavior layer_id",
            "pre_beh = result",
            "tv_layerpostbehavior layer_id",
            "post_beh = result",
            "line = layer_id'|'pre_beh'|'post_beh",
            "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' line"
        ])

    george_script = "\n".join(george_script_lines)
    execute_george_through_file(george_script, communicator)

    # Read data
    with open(output_filepath, "r") as stream:
        data = stream.read()

    # Remove temp file
    os.remove(output_filepath)

    # Parse data
    output = {}
    raw_lines = data.split("\n")
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 3:
            continue
        layer_id, pre_beh, post_beh = parts
        output[int(layer_id)] = {
            "pre": pre_beh.lower(),
            "post": post_beh.lower()
        }
    return output

def set_layer_post_behavior(layer_id, mode):
    execute_george(f"tv_layerpostbehavior {layer_id} \"{mode}\"")

def get_layers_exposure_frames(layer_ids, layers_data=None, communicator=None):
    """Get exposure frames.

    Easily said returns frames where keyframes are. Recognized with george
    function `tv_exposureinfo` returning "Head".

    Args:
        layer_ids (list): Ids of a layers for which exposure frames should
            look for.
        layers_data (list): Precollected layers data. If are not passed then
            'get_layers_data' is used.
        communicator (BaseCommunicator): Communicator used for communication
            with TVPaint.

    Returns:
        dict: Frames where exposure is set to "Head" by layer id.
    """

    if layers_data is None:
        layers_data = get_layers_data(layer_ids)
    _layers_by_id = {
        layer["layer_id"]: layer
        for layer in layers_data
    }
    layers_by_id = {
        layer_id: _layers_by_id.get(layer_id)
        for layer_id in layer_ids
    }
    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    tmp_file.close()
    tmp_output_path = tmp_file.name.replace("\\", "/")
    george_script_lines = [
        "output_path = \"{}\"".format(tmp_output_path)
    ]

    output = {}
    layer_id_mapping = {}
    for layer_id, layer_data in layers_by_id.items():
        layer_id_mapping[str(layer_id)] = layer_id
        output[layer_id] = []
        if not layer_data:
            continue
        first_frame = layer_data["frame_start"]
        last_frame = layer_data["frame_end"]
        george_script_lines.extend([
            "line = \"\"",
            "layer_id = {}".format(layer_id),
            "line = line''layer_id",
            "tv_layerset layer_id",
            "frame = {}".format(first_frame),
            "WHILE (frame <= {})".format(last_frame),
            "tv_exposureinfo frame",
            "exposure = result",
            "IF (CMP(exposure, \"Head\") == 1)",
            "line = line'|'frame",
            "END",
            "frame = frame + 1",
            "END",
            "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' line"
        ])

    execute_george_through_file("\n".join(george_script_lines), communicator)

    with open(tmp_output_path, "r") as stream:
        data = stream.read()

    os.remove(tmp_output_path)

    lines = []
    for line in data.split("\n"):
        line = line.strip()
        if line:
            lines.append(line)

    for line in lines:
        line_items = list(line.split("|"))
        layer_id = line_items.pop(0)
        _layer_id = layer_id_mapping[layer_id]
        output[_layer_id] = [int(frame) for frame in line_items]

    return output


def get_exposure_frames(
    layer_id, first_frame=None, last_frame=None, communicator=None
):
    """Get exposure frames.

    Easily said returns frames where keyframes are. Recognized with george
    function `tv_exposureinfo` returning "Head".

    Args:
        layer_id (int): Id of a layer for which exposure frames should
            look for.
        first_frame (int): From which frame will look for exposure frames.
            Used layers first frame if not entered.
        last_frame (int): Last frame where will look for exposure frames.
            Used layers last frame if not entered.

    Returns:
        list: Frames where exposure is set to "Head".
    """
    if first_frame is None or last_frame is None:
        layer = layers_data(layer_id)[0]
        if first_frame is None:
            first_frame = layer["frame_start"]
        if last_frame is None:
            last_frame = layer["frame_end"]

    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    tmp_file.close()
    tmp_output_path = tmp_file.name.replace("\\", "/")
    george_script_lines = [
        "tv_layerset {}".format(layer_id),
        "output_path = \"{}\"".format(tmp_output_path),
        "output = \"\"",
        "frame = {}".format(first_frame),
        "WHILE (frame <= {})".format(last_frame),
        "tv_exposureinfo frame",
        "exposure = result",
        "IF (CMP(exposure, \"Head\") == 1)",
        "IF (CMP(output, \"\") == 1)",
        "output = output''frame",
        "ELSE",
        "output = output'|'frame",
        "END",
        "END",
        "frame = frame + 1",
        "END",
        "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' output"
    ]

    execute_george_through_file("\n".join(george_script_lines), communicator)

    with open(tmp_output_path, "r") as stream:
        data = stream.read()

    os.remove(tmp_output_path)

    lines = []
    for line in data.split("\n"):
        line = line.strip()
        if line:
            lines.append(line)

    exposure_frames = []
    for line in lines:
        for frame in line.split("|"):
            exposure_frames.append(int(frame))
    return exposure_frames


def get_scene_data(communicator=None):
    """Scene data of currently opened scene.

    Result contains resolution, pixel aspect, fps mark in/out with states,
    frame start and background color.

    Returns:
        dict: Scene data collected in many ways.
    """
    workfile_info = execute_george("tv_projectinfo", communicator)
    workfile_info_parts = workfile_info.split(" ")

    # Project frame start - not used
    workfile_info_parts.pop(-1)
    field_order = workfile_info_parts.pop(-1)
    frame_rate = float(workfile_info_parts.pop(-1))
    pixel_apsect = float(workfile_info_parts.pop(-1))
    height = int(workfile_info_parts.pop(-1))
    width = int(workfile_info_parts.pop(-1))

    # Marks return as "{frame - 1} {state} ", example "0 set".
    result = execute_george("tv_markin", communicator)
    mark_in_frame, mark_in_state, _ = result.split(" ")

    result = execute_george("tv_markout", communicator)
    mark_out_frame, mark_out_state, _ = result.split(" ")

    start_frame = execute_george("tv_startframe", communicator)
    return {
        "width": width,
        "height": height,
        "pixel_aspect": pixel_apsect,
        "fps": frame_rate,
        "field_order": field_order,
        "mark_in": int(mark_in_frame),
        "mark_in_state": mark_in_state,
        "mark_in_set": mark_in_state == "set",
        "mark_out": int(mark_out_frame),
        "mark_out_state": mark_out_state,
        "mark_out_set": mark_out_state == "set",
        "start_frame": int(start_frame),
        "bg_color": get_scene_bg_color(communicator)
    }


def get_scene_bg_color(communicator=None):
    """Background color set on the scene.

    Is important for review exporting where scene bg color is used as
    the background color.
    """
    output_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="a_tvp_", suffix=".txt", delete=False
    )
    output_file.close()
    output_filepath = output_file.name.replace("\\", "/")
    george_script_lines = [
        # Variable containing the full path to the output file
        "output_path = \"{}\"".format(output_filepath),
        "tv_background",
        "bg_color = result",
        # Write data to the output file
        "tv_writetextfile \"strict\" \"append\" '\"'output_path'\"' bg_color"
    ]

    george_script = "\n".join(george_script_lines)
    execute_george_through_file(george_script, communicator)

    with open(output_filepath, "r") as stream:
        data = stream.read()

    os.remove(output_filepath)
    data = data.strip()
    if not data:
        return None
    return data.split(" ")


def get_layer_opacity(layer_id):
    """Return the opacity set on layer.
    layer_id(int): id of the layer to get the opacity
    Returns:
        int: Layer Opacity (0-100).
    """
    execute_george("tv_layerset {}".format(layer_id))
    opacity = execute_george("tv_layerdensity")
    execute_george("tv_layerdensity {}".format(opacity))
    return int(opacity)

def remove_layer(layer_id):
    execute_george_through_file("tv_layerkill {}".format(layer_id))

def rename_layer(layer_id, name):
    execute_george_through_file(f"tv_layerrename {layer_id} \"{name}\"")

def get_active_layer():
    active_layer = execute_george("tv_LayerCurrentID")
    return int(active_layer)

def get_layer_position(layer_id):
    layer_position = execute_george(f"tv_LayerGetPos {layer_id}")
    return int(layer_position)

def set_layer_position(layer_position):
    execute_george(f"tv_LayerMove {layer_position}")

def lock_layer(layer_id):
    execute_george("tv_layerset {}".format(layer_id))
    execute_george("tv_layerlock {} 1".format(layer_id))

def get_layer_position_and_size(layer_id):
    execute_george("tv_layerset {}".format(layer_id))
    image_bound = execute_george("tv_imagegetbound")
    x, y, width, height = map(int, image_bound.split())
    return int(x), int(y), int(width), int(height)

def get_project_size():
    width = execute_george("tv_GetWidth")
    height = execute_george("tv_GetHeight")
    return int(width), int(height)

def transform_layer(layer_id, scale_x, scale_y, pos_x, pos_y):
    fx_text = f"""[85ca1887-ffd2-fe45-bfe6-19e6cf06e1ed]
    active=1
    autokeyidgeneration=1
    classauid=3296ea12-bc40-11d7-97d1-00105aafaaab
    disclosed=1
    localename=KeyFramer
    name=KeyFramer
    param_0_0_0__lockx=0
    param_0_0_0__locky=0
    param_0_0_0__lockz=0
    param_0_0_0__myname=Décalage /position
    param_0_0_0__value={pos_x} {pos_y} 0
    param_0_0_0__value_interpolation=0
    param_0_0_0_key_0_kp_val={pos_x} {pos_y} 0 0 0 0 0 0 0 0 0 0
    param_0_0_1__lockx=0
    param_0_0_1__locky=0
    param_0_0_1__lockz=0
    param_0_0_1__myname=Décalage /pivot
    param_0_0_1__value=0 0 0
    param_0_0_1__value_interpolation=0
    param_0_0_1_key_0_kp_val=0 0 0 0 0 0 0 0 0 0 0 0
    param_0_0_2__align=0
    param_0_0_2__angle=0
    param_0_0_2__myname=Roulis
    param_0_0_2_key_0_kp_val=0 0 0 0 0 0
    param_0_0_3__align=0
    param_0_0_3__angle=0
    param_0_0_3__myname=Tangage
    param_0_0_3_key_0_kp_val=0 0 0 0 0 0
    param_0_0_4__align=0
    param_0_0_4__angle=0
    param_0_0_4__myname=Cap
    param_0_0_4_key_0_kp_val=0 0 0 0 0 0
    param_0_0_5_0_0__myname=Largeur
    param_0_0_5_0_0__scalefactor=1
    param_0_0_5_0_0__value={scale_x}
    param_0_0_5_0_0_key_0_kp_val={scale_x} 0 0 0 0 0
    param_0_0_5_0_1__myname=Hauteur
    param_0_0_5_0_1__scalefactor=1
    param_0_0_5_0_1__value={scale_y}
    param_0_0_5_0_1_key_0_kp_val={scale_y} 0 0 0 0 0
    param_0_0_5_0__myname=Préserver l'aspect
    param_0_0_5_1_0__myname=Taille
    param_0_0_5_1_0__scalefactor=1
    param_0_0_5_1_0__value=100
    param_0_0_5_1_0_key_0_kp_val=100 0 0 0 0 0
    param_0_0_5_1_1__myname=Ratio
    param_0_0_5_1_1__scalefactor=1
    param_0_0_5_1_1__value=1
    param_0_0_5_1__myname=Préserver l'aspect
    param_0_0_5__myname=Préserver l'aspect
    param_0_0_5_disclosed=1
    param_0_0_5_enum=0
    param_0_0_6__myname=Bruit
    param_0_0_6__scalefactor=1
    param_0_0_6__value=0
    param_0_0_6_key_0_kp_val=0 0 0 0 0 0
    param_0_0__myname=Position
    param_0_1_0__myname=Source
    param_0_1_0_behavior=1
    param_0_1_0_flipx=0
    param_0_1_0_flipy=0
    param_0_1_0_id=00000000-0000-0000-0000-000000000000
    param_0_1_0_key_0_kp_val=0 0 0 0 0 0
    param_0_1_0_libraryid=00000000-0000-0000-0000-000000000000
    param_0_1_0_offset=0
    param_0_1_0_path=/
    param_0_1_0_postbehavior=2
    param_0_1_0_prebehavior=5
    param_0_1_0_type=0
    param_0_1_1__myname=Mélanger
    param_0_1_1__value=0
    param_0_1_2__myname=Opacité
    param_0_1_2__scalefactor=1
    param_0_1_2__value=100
    param_0_1_2_key_0_kp_val=100 0 0 0 0 0
    param_0_1_3__myname=Remplir
    param_0_1_3__value=0
    param_0_1_4_0__myname=Taille du flou
    param_0_1_4_0__scalefactor=1
    param_0_1_4_0__value=50
    param_0_1_4_0_key_0_kp_val=50 0 0 0 0 0
    param_0_1_4_1__myname=Pas de déplacement
    param_0_1_4_1__value=8
    param_0_1_4__myname=Flou de mouvement
    param_0_1_4_disclosed=1
    param_0_1_4_on=0
    param_0_1_5__myname=Anticrénel.
    param_0_1_5__value=1
    param_0_1_6__myname=Z Camera
    param_0_1_6__scalefactor=1
    param_0_1_6__value=1000
    param_0_1_6_key_0_kp_val=1000 0 0 0 0 0
    param_0_1__myname=Source
    param_0__myname=Menu
    param_0_disclosed=1
    param_0_enum=0
    timewrapper=0
    timewrapperprofileprof_current=0
    timewrapperprofileprof_linear=1
    timewrapperprofileprof_name=KeyFramer Profil d'accélération
    timewrapperprofileprof_numpoint=2
    timewrapperprofileprof_point0=0 0
    timewrapperprofileprof_point1=1 1
    username=KeyFramer

    [stack]
    count=1
    filter_00=85ca1887-ffd2-fe45-bfe6-19e6cf06e1ed
    """

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as temp_file:
        temp_file.write(b'\xef\xbb\xbf' + fx_text.encode('utf-8'))
        temp_file.close()
        temp_path = temp_file.name.replace('\\', '/')
        try:
            george_script = f"""
    tv_layerset {layer_id}
    tv_StackOpen
    tv_stackload "{temp_path}"
    tv_StackApply {layer_id} "allframes"
    tv_StackClear
    tv_StackClose
    tv_Refresh
    """
            execute_george_through_file(george_script)
        finally:
            Path(temp_path).unlink(missing_ok=True)

def show_warning(msg):
    execute_george_through_file(f"tv_warn \"{msg}\"")
