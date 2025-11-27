import os
import sys
import re
import traceback
import json
from typing import Callable, Dict, Iterator, List, Optional

import bpy

from . import lib
from . import ops

import pyblish.api
from typing import Union

from quadpype.host import (
    HostBase,
    IWorkfileHost,
    IPublishHost,
    ILoadHost
)
from quadpype.client import get_asset_by_name
from quadpype.pipeline import (
    schema,
    get_current_asset_name,
    register_loader_plugin_path,
    register_creator_plugin_path,
    deregister_loader_plugin_path,
    deregister_creator_plugin_path,
    AVALON_CONTAINER_ID,
    Anatomy,
    get_current_project_name,
    get_current_task_name
)
from quadpype.pipeline.workfile.workfile_template_builder import (
    is_last_workfile_exists,
    should_build_first_workfile
)
from quadpype.tools.utils.workfile_cache import WorkFileCache
from .workfile_template_builder import (
    build_workfile_template,
    BlenderPlaceholderLoadPlugin,
    BlenderPlaceholderCreatePlugin
)

from quadpype.pipeline.workfile import get_template_data_from_session
from quadpype.lib import (
    Logger,
    register_event_callback,
    emit_event,
    StringTemplate
)

from quadpype.settings import get_project_settings
from .workio import (
    open_file,
    save_file,
    current_file,
    has_unsaved_changes,
    file_extensions,
    work_root,
)

from .constants import (
    PUBLISH_PATH,
    LOAD_PATH,
    CREATE_PATH,
    ORIGINAL_EXCEPTHOOK,
    AVALON_CONTAINERS,
    AVALON_PROPERTY,
    CUSTOM_FRAME_OFFSET,
    IS_HEADLESS
)


log = Logger.get_logger(__name__)


class BlenderHost(HostBase, IWorkfileHost, IPublishHost, ILoadHost, WorkFileCache):
    name = "blender"

    def install(self):
        """Override install method from HostBase.
        Install Blender host functionality."""
        install()

    def get_containers(self) -> Iterator:
        """List containers from active Blender scene."""
        return ls()

    def get_workfile_extensions(self) -> List[str]:
        """Override get_workfile_extensions method from IWorkfileHost.
        Get workfile possible extensions.

        Returns:
            List[str]: Workfile extensions.
        """
        return file_extensions()

    def save_workfile(self, dst_path: str = None):
        """Override save_workfile method from IWorkfileHost.
        Save currently opened workfile.

        Args:
            dst_path (str): Where the current scene should be saved. Or use
                current path if `None` is passed.
        """
        _, ext = os.path.splitext(dst_path)
        save_file(dst_path if dst_path else bpy.data.filepath)
        self.add_task_extension(extension=ext)

    def open_workfile(self, filepath: str):
        """Override open_workfile method from IWorkfileHost.
        Open workfile at specified filepath in the host.

        Args:
            filepath (str): Path to workfile.
        """
        open_file(filepath)

    def get_current_workfile(self) -> str:
        """Override get_current_workfile method from IWorkfileHost.
        Retrieve currently opened workfile path.

        Returns:
            str: Path to currently opened workfile.
        """
        return current_file()

    def workfile_has_unsaved_changes(self) -> bool:
        """Override wokfile_has_unsaved_changes method from IWorkfileHost.
        Returns True if opened workfile has no unsaved changes.

        Returns:
            bool: True if scene is saved and False if it has unsaved
                modifications.
        """
        return has_unsaved_changes()

    def work_root(self, session) -> str:
        """Override work_root method from IWorkfileHost.
        Modify workdir per host.

        Args:
            session (dict): Session context data.

        Returns:
            str: Path to new workdir.
        """
        return work_root(session)

    def get_context_data(self) -> dict:
        """Override abstract method from IPublishHost.
        Get global data related to creation-publishing from workfile.

        Returns:
            dict: Context data stored using 'update_context_data'.
        """
        return get_avalon_node(bpy.context.scene)

    def update_context_data(self, data: dict, changes: dict):
        """Override abstract method from IPublishHost.
        Store global context data to workfile.

        Args:
            data (dict): New data as are.
            changes (dict): Only data that has been changed. Each value has
                tuple with '(<old>, <new>)' value.
        """
        lib.imprint(bpy.context.scene, data)

    def get_workfile_build_placeholder_plugins(self):
        return [
            BlenderPlaceholderLoadPlugin,
            BlenderPlaceholderCreatePlugin
        ]


def pype_excepthook_handler(*args):
    traceback.print_exception(*args)


def install():
    """Install Blender configuration for Avalon."""
    sys.excepthook = pype_excepthook_handler

    pyblish.api.register_host("blender")
    pyblish.api.register_plugin_path(str(PUBLISH_PATH))

    register_loader_plugin_path(str(LOAD_PATH))
    register_creator_plugin_path(str(CREATE_PATH))

    lib.append_user_scripts()
    lib.set_app_templates_path()

    register_event_callback("new", on_new)
    register_event_callback("open", on_open)

    _register_callbacks()
    _register_events()

    if not IS_HEADLESS:
        ops.register()


def uninstall():
    """Uninstall Blender configuration for Avalon."""
    sys.excepthook = ORIGINAL_EXCEPTHOOK

    pyblish.api.deregister_host("blender")
    pyblish.api.deregister_plugin_path(str(PUBLISH_PATH))

    deregister_loader_plugin_path(str(LOAD_PATH))
    deregister_creator_plugin_path(str(CREATE_PATH))

    if not IS_HEADLESS:
        ops.unregister()


def show_message(title, message):
    from quadpype.widgets.message_window import Window
    from .ops import BlenderApplication

    BlenderApplication.get_app()

    Window(
        parent=None,
        title=title,
        message=message,
        level="warning")


def message_window(title, message):
    from .ops import (
        MainThreadItem,
        execute_in_main_thread,
        _process_app_events
    )

    mti = MainThreadItem(show_message, title, message)
    execute_in_main_thread(mti)
    _process_app_events()


def get_asset_data():
    project_name = get_current_project_name()
    asset_name = get_current_asset_name()
    asset_doc = get_asset_by_name(project_name, asset_name)
    return asset_doc.get("data")


def get_frame_range(asset_entity=None) -> Union[Dict[str, int], None]:
    """Get the asset entity's frame range and handles

    Args:
        asset_entity (Optional[dict]): Task Entity.
            When not provided defaults to current context task.

    Returns:
        Union[Dict[str, int], None]: Dictionary with
            frame start, frame end, handle start, handle end.
    """
    # Set frame start/end
    asset_attributes = asset_entity["data"]
    frame_start = int(asset_attributes["frameStart"])
    frame_end = int(asset_attributes["frameEnd"])
    handle_start = int(asset_attributes["handleStart"])
    handle_end = int(asset_attributes["handleEnd"])
    frame_start_handle = frame_start - handle_start
    frame_end_handle = frame_end + handle_end

    return {
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "handleStart": handle_start,
        "handleEnd": handle_end,
        "frameStartHandle": frame_start_handle,
        "frameEndHandle": frame_end_handle,
    }


def get_parent_data(data):
    parent = data.get('parent', None)
    if not parent:
        hierarchy = data.get('hierarchy')
        if not hierarchy:
            return

        return hierarchy.split('/')[-1]
    return parent


def set_frame_range(data):
    scene = bpy.context.scene

    # Default scene settings
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    fps = scene.render.fps / scene.render.fps_base

    if not data:
        return

    if data.get("frameStart"):
        frame_start = data.get("frameStart")
    if data.get("frameEnd"):
        frame_end = data.get("frameEnd")
    if data.get("fps"):
        fps = data.get("fps")

    # Should handles be included, defined by settings
    task_name = get_current_task_name()
    settings = get_project_settings(get_current_project_name())
    include_handles_settings = settings["blender"]["include_handles"]
    current_task = data.get("tasks").get(task_name)

    include_handles = include_handles_settings["include_handles_default"]
    for item in include_handles_settings["profiles"]:
        if current_task["type"] in item["task_type"]:
            include_handles = item["include_handles"]
            break

    if include_handles:
        frame_start -= int(data.get("handleStart", 0))
        frame_end += int(data.get("handleEnd", 0))

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = round(fps)
    scene.render.fps_base = round(fps) / fps


def apply_frame_offset():
    frame_offset = get_custom_frame_offset()
    scene = bpy.context.scene
    scene.frame_end += frame_offset
    scene.frame_start += frame_offset


def set_resolution(data):
    scene = bpy.context.scene

    # Default scene settings
    resolution_x = scene.render.resolution_x
    resolution_y = scene.render.resolution_y

    if not data:
        return

    if data.get("resolutionWidth"):
        resolution_x = data.get("resolutionWidth")
    if data.get("resolutionHeight"):
        resolution_y = data.get("resolutionHeight")

    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y


def set_unit_scale_from_settings(unit_scale_settings=None):
    if unit_scale_settings is None:
        return
    unit_scale_enabled = unit_scale_settings.get("enabled")
    if unit_scale_enabled:
        unit_scale = unit_scale_settings["base_file_unit_scale"]
        bpy.context.scene.unit_settings.scale_length = unit_scale


def _autobuild_first_workfile():
    if not is_last_workfile_exists() and should_build_first_workfile():
        build_workfile_template()


def on_new():
    _autobuild_first_workfile()
    project = os.getenv("AVALON_PROJECT")
    settings = get_project_settings(project).get("blender")

    set_resolution_startup = settings.get("set_resolution_startup")
    set_frames_startup = settings.get("set_frames_startup")

    data = get_asset_data()

    if set_resolution_startup:
        set_resolution(data)
    if set_frames_startup:
        set_frame_range(data)

    apply_frame_offset()

    unit_scale_settings = settings.get("unit_scale_settings")
    unit_scale_enabled = unit_scale_settings.get("enabled")
    if unit_scale_enabled:
        unit_scale = unit_scale_settings.get("base_file_unit_scale")
        bpy.context.scene.unit_settings.scale_length = unit_scale


def on_open():
    project = os.getenv("AVALON_PROJECT")
    settings = get_project_settings(project).get("blender")

    set_resolution_startup = settings.get("set_resolution_startup")
    set_frames_startup = settings.get("set_frames_startup")

    data = get_asset_data()

    if set_resolution_startup:
        set_resolution(data)
    if set_frames_startup:
        set_frame_range(data)

    apply_frame_offset()

    unit_scale_settings = settings.get("unit_scale_settings")
    unit_scale_enabled = unit_scale_settings.get("enabled")
    apply_on_opening = unit_scale_settings.get("apply_on_opening")
    if unit_scale_enabled and apply_on_opening:
        unit_scale = unit_scale_settings.get("base_file_unit_scale")
        prev_unit_scale = bpy.context.scene.unit_settings.scale_length

        if unit_scale != prev_unit_scale:
            bpy.context.scene.unit_settings.scale_length = unit_scale

            message_window(
                "Base file unit scale changed",
                "Base file unit scale changed to match the project settings.")


def apply_ids():
    for node, new_id in lib.generate_ids(lib.get_objects_concerned_by_ids()):
        lib.set_id(node, new_id, overwrite=False)

    erased_materials_targets_ids = list()
    for obj in bpy.data.objects:
        if not lib.has_materials(obj):
            continue

        for material_slot in obj.material_slots:
            material = material_slot.material
            if not material:
                continue

            if material not in erased_materials_targets_ids:
                lib.set_targets_ids(
                    entity=material,
                    targets_ids=[],
                    overwrite=True
                )
                erased_materials_targets_ids.append(material)

            lib.add_target_id(
                concerned_object=material_slot.material,
                target_id=lib.get_id(obj)
            )


@bpy.app.handlers.persistent
def _on_save_pre(*args):
    apply_ids()
    emit_event("before.save")


@bpy.app.handlers.persistent
def _on_save_post(*args):
    emit_event("save")


@bpy.app.handlers.persistent
def _on_load_post(*args):
    # Detect new file or opening an existing file
    if bpy.data.filepath:
        # Likely this was an open operation since it has a filepath
        emit_event("open")
    else:
        emit_event("new")

    ops.OpenFileCacher.post_load()


def _register_callbacks():
    """Register callbacks for certain events."""
    def _remove_handler(handlers: List, callback: Callable):
        """Remove the callback from the given handler list."""

        try:
            handlers.remove(callback)
        except ValueError:
            pass

    # TODO (jasper): implement on_init callback?

    # Be sure to remove existig ones first.
    _remove_handler(bpy.app.handlers.save_pre, _on_save_pre)
    _remove_handler(bpy.app.handlers.save_post, _on_save_post)
    _remove_handler(bpy.app.handlers.load_post, _on_load_post)

    bpy.app.handlers.save_pre.append(_on_save_pre)
    bpy.app.handlers.save_post.append(_on_save_post)
    bpy.app.handlers.load_post.append(_on_load_post)

    log.info("Installed event handler _on_save_pre...")
    log.info("Installed event handler _on_save_post...")
    log.info("Installed event handler _on_load_post...")


def _on_task_changed():
    """Callback for when the task in the context is changed."""

    # TODO (jasper): Blender has no concept of projects or workspace.
    # It would be nice to override 'bpy.ops.wm.open_mainfile' so it takes the
    # workdir as starting directory.  But I don't know if that is possible.
    # Another option would be to create a custom 'File Selector' and add the
    # `directory` attribute, so it opens in that directory (does it?).
    # https://docs.blender.org/api/blender2.8/bpy.types.Operator.html#calling-a-file-selector
    # https://docs.blender.org/api/blender2.8/bpy.types.WindowManager.html#bpy.types.WindowManager.fileselect_add
    workdir = os.getenv("AVALON_WORKDIR")
    log.info("New working directory: %s", workdir)


def _register_events():
    """Install callbacks for specific events."""

    register_event_callback("taskChanged", _on_task_changed)
    log.info("Installed event callback for 'taskChanged'...")


def _discover_gui() -> Optional[Callable]:
    """Return the most desirable of the currently registered GUIs"""

    # Prefer last registered
    guis = reversed(pyblish.api.registered_guis())

    for gui in guis:
        try:
            gui = __import__(gui).show
        except (ImportError, AttributeError):
            continue
        else:
            return gui

    return None


def add_to_avalon_container(container: bpy.types.Collection):
    """Add the container to the Avalon container."""

    avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
    if not avalon_container:
        avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)

        # Link the container to the scene so it's easily visible to the artist
        # and can be managed easily. Otherwise it's only found in "Blender
        # File" view and it will be removed by Blenders garbage collection,
        # unless you set a 'fake user'.
        bpy.context.scene.collection.children.link(avalon_container)

    if isinstance(container, bpy.types.Object):
        avalon_container.objects.link(container)
    elif isinstance(container, bpy.types.Collection) and container not in list(avalon_container.children):
        avalon_container.children.link(container)

    # Disable Avalon containers for the view layers.
    for view_layer in bpy.context.scene.view_layers:
        for child in view_layer.layer_collection.children:
            if child.collection == avalon_container:
                child.exclude = True


def metadata_update(node: bpy.types.bpy_struct_meta_idprop, data: Dict, erase: bool, set_property: str=AVALON_PROPERTY):
    """Imprint the node with metadata.

    Existing metadata will be updated.

    We use json to dump data into strings and allow library override.

    Arguments:
        node: Long name of node
        data: Dictionary of key/value pairs
        erase: Erase previous value insted of updating / adding data
        set_property: Name of the property to store data
    """

    existing_data = dict() if erase else get_avalon_node(node)
    for key, value in data.items():
        if value is None:
            continue
        existing_data[key] = value

    node[set_property] = json.dumps(existing_data)
    node.property_overridable_library_set(f'["{set_property}"]', True)


def set_custom_frame_offset(custom_frame_offset):
    """ Write custom frame offset value as retrieved from settings in scene properties.
    Populate each scene in file to avoid retrieving incorrect values.
    """
    for scene in bpy.data.scenes:
        scene[CUSTOM_FRAME_OFFSET] = custom_frame_offset


def get_custom_frame_offset():
    """ Get custom frame start from current scene properties.
    If not found in scene properties, get it from project settings
    and automatically set value to property CUSTOM_FRAME_OFFSET.
    """
    custom_frame_offset = bpy.context.scene.get(CUSTOM_FRAME_OFFSET, None)
    if custom_frame_offset:
        return custom_frame_offset

    project_name = os.environ.get('AVALON_PROJECT', None)
    if not project_name:
        print("Can not retrieve project name from environment variable 'AVALON_PROJECT'.")
        set_custom_frame_offset(0)
        return

    project_settings = get_project_settings(project_name)

    frame_offset_settings = project_settings.get('blender', {}).get('FrameStartOffset', None)
    if not frame_offset_settings:
        print("Can not retrieve settings for plugin 'FrameStartOffset'.")
        set_custom_frame_offset(0)
        return

    if not frame_offset_settings.get('enabled', False):
        print("rame Start Offset has not been enabled and will not be set for current scene.")
        set_custom_frame_offset(0)
        return

    custom_frame_offset = frame_offset_settings.get('frame_start_offset', 0)
    set_custom_frame_offset(custom_frame_offset)
    print(f"Frame Start Offset with a value of {custom_frame_offset} have been applied to scenes properties.")

    return custom_frame_offset


def get_avalon_node(node, get_property=AVALON_PROPERTY):
    """ Return avalon node content.

    By default we expect a single string (json dump), but we also want to handle
    special cases with specific Blender data types.

    Arguments:
        node: blender object
        get_property: property to search

    Returns:
        dict: AVALON_PROPERTY custom prop content
    """
    node_content = node.get(get_property, '{}')

    # For IDPropertyGroup (which is not accessible through bpy.types)
    if hasattr(node_content, 'to_dict'):
        return node_content.to_dict()

    return json.loads(node_content)


def has_avalon_node(node):
    """ Check if avalon custom prop exists for given object.

    Arguments:
        node: blender object

    Returns:
        bool: True is AVALON_PROPERTY exists for given object, False otherwise.
    """
    return bool(node.get(AVALON_PROPERTY, False))


def delete_avalon_node(node):
    """ Delete avalon custom prop for given object.

    Arguments:
        node: blender object
    """

    del node[AVALON_PROPERTY]


def containerise(name: str,
                 namespace: str,
                 nodes: List,
                 context: Dict,
                 loader: Optional[str] = None,
                 suffix: Optional[str] = "CON") -> bpy.types.Collection:
    """Bundle `nodes` into an assembly and imprint it with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        name: Name of resulting assembly
        namespace: Namespace under which to host container
        nodes: Long names of nodes to containerise
        context: Asset information
        loader: Name of loader used to produce this container.
        suffix: Suffix of container, defaults to `_CON`.

    Returns:
        The container assembly

    """

    node_name = f"{context['asset']['name']}_{name}"
    if namespace:
        node_name = f"{namespace}:{node_name}"
    if suffix:
        node_name = f"{node_name}_{suffix}"
    container = bpy.data.collections.new(name=node_name)
    # Link the children nodes
    for obj in nodes:
        container.objects.link(obj)

    data = {
        "schema": "quadpype:container-2.0",
        "id": AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace or '',
        "loader": str(loader),
        "representation": str(context["representation"]["_id"]),
    }

    metadata_update(container, data, erase=False)
    add_to_avalon_container(container)

    return container


def containerise_existing(
        container: bpy.types.Collection,
        name: str,
        namespace: str,
        context: Dict,
        loader: Optional[str] = None,
        suffix: Optional[str] = "CON") -> bpy.types.Collection:
    """Imprint or update container with metadata.

    Arguments:
        name: Name of resulting assembly
        namespace: Namespace under which to host container
        context: Asset information
        loader: Name of loader used to produce this container.
        suffix: Suffix of container, defaults to `_CON`.

    Returns:
        The container assembly
    """

    node_name = container.name
    if suffix:
        node_name = f"{node_name}_{suffix}"
    container.name = node_name
    data = {
        "schema": "quadpype:container-2.0",
        "id": AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace or '',
        "loader": str(loader),
        "representation": str(context["representation"]["_id"]),
    }

    metadata_update(container, data, erase=False)
    add_to_avalon_container(container)

    return container


def parse_container(container: bpy.types.Collection,
                    validate: bool = True) -> Dict:
    """Return the container node's full container data.

    Args:
        container: A container node name.
        validate: turn the validation for the container on or off

    Returns:
        The container schema data for this container node.

    """

    data = lib.read(container)

    # Append transient data
    data["objectName"] = container.name
    data["node"] = container  # store parsed object for easy access in loader

    if validate:
        schema.validate(data)

    return data


def ls() -> Iterator:
    """List containers from active Blender scene.

    This is the host-equivalent of api.ls(), but instead of listing assets on
    disk, it lists assets already loaded in Blender; once loaded they are
    called containers.
    """
    container_ids = {
        # Backwards compatibility
        AVALON_CONTAINER_ID
    }

    for container in lib.lsattr("id", AVALON_CONTAINER_ID):
        yield parse_container(container)

    # Compositor nodes are not in `bpy.data` that `lib.lsattr` looks in.
    node_tree = bpy.context.scene.node_tree
    if node_tree:
        for node in node_tree.nodes:
            if get_avalon_node(node).get("id", None) not in container_ids:
                continue

            yield parse_container(node)

def publish():
    """Shorthand to publish from within host."""

    return pyblish.util.publish()


def get_path_from_template(template_module, template_name, template_data={}, bump_version=False, makedirs=False):
    """ Build path from asked template based on actual context"""
    anatomy = Anatomy()
    templates = anatomy.templates.get(template_module)
    if not templates:
        raise NotImplemented(f"'{template_module}' template need to be setted in your project settings")

    template_session_data = {'root': anatomy.roots, **get_template_data_from_session()}
    template_session_data.update(template_data)

    if 'version' in templates[template_name]:
        template_folder_path = os.path.normpath(StringTemplate.format_template(templates['folder'], template_session_data))

        if not os.path.exists(template_folder_path):
            template_session_data.update({'version': 1})
        else:
            latest_version = 1
            regex = fr'v(\d{{{templates["version_padding"]}}})$'
            for version in os.listdir(template_folder_path):
                match = re.search(regex, version)
                if not match:
                    continue

                version_num = int(match.group(1))
                latest_version = max(latest_version, version_num + 1 if bump_version else 0)

            template_session_data.update({'version': latest_version})

    render_node_path = os.path.normpath(StringTemplate.format_template(templates[template_name], template_session_data))
    if makedirs:
        if os.path.isdir(render_node_path):
            os.makedirs(render_node_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(render_node_path), exist_ok=True)

    return render_node_path


def get_container(objects: list = [], collections: list = []):
    """Retrieve the instance container based on given objects and collections"""
    for coll in collections:
        if has_avalon_node(coll):
            return coll

    for empty in [obj for obj in objects if obj.type == 'EMPTY']:
        if has_avalon_node(empty) and empty.parent is None:
            return empty

    return None


def get_container_content(container):
    """Retrieve all objects and collection in the given container"""
    if lib.is_collection(container):
        return [*container.objects, *container.children]

    return [obj for obj in bpy.data.objects if obj.parent == container]

def get_non_keyed_property_to_export():
    project = os.getenv("AVALON_PROJECT")
    settings = get_project_settings(project).get("blender")
    return settings["publish"]["ExtractNonKeyedProperties"]["properties"]

def copy_render_settings(src_scene, dst_scene):

    engine = src_scene.render.engine
    dst_scene.render.engine = engine

    render_settings = {
        "CYCLES": "cycles",
        "BLENDER_EEVEE": "eevee",
        "BLENDER_EEVEE_NEXT": "eevee",
        "BLENDER_WORKBENCH": "workbench",
        "RENDER": "render",
        "DISPLAY": "display",
        "DISPLAY_SETTINGS": "display_settings",
        "VIEW_SETTINGS": "view_settings",
        "SEQ_COLORSPACE": "sequencer_colorspace_settings"
    }

    for setting_name, attr in render_settings.items():
        src_settings = getattr(src_scene, attr, None)
        dst_settings = getattr(dst_scene, attr, None)
        if not all([src_settings, dst_settings]):
            continue

        for prop in src_settings.bl_rna.properties:
            if prop.identifier == "rna_type":
                continue
            try:
                setattr(dst_settings, prop.identifier, getattr(src_settings, prop.identifier))
            except Exception:
                pass

    data = get_asset_data()
    set_resolution(data)
    set_frame_range(data)
    apply_frame_offset()

    if not all([hasattr(src_scene.display, "shading"), hasattr(dst_scene.display, "shading")]):
        return
    for prop in src_scene.display.shading.bl_rna.properties:
        if prop.identifier == "rna_type":
            continue
        try:
            setattr(dst_scene.display.shading, prop.identifier, getattr(src_scene.display.shading, prop.identifier))
        except Exception:
            pass

def is_material_from_loaded_look(material):
    avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
    if not avalon_container:
        return False
    look_instances = [col for col in avalon_container.children if has_avalon_node(col)
                      and get_avalon_node(col).get("family") == "look"]
    for look_instance in look_instances:
        mats_members = lib.get_objects_from_mapped(get_avalon_node(look_instance)["members"])
        if material in mats_members:
            return look_instance
    return None
