import json
import os
import traceback
import importlib
import contextlib
import uuid
from typing import Dict, List, Union, TYPE_CHECKING

import bpy
import addon_utils
from quadpype.lib import Logger, NumberDef
from quadpype.pipeline import get_current_project_name, get_current_asset_name, get_current_context
from quadpype.client import get_asset_by_name
if TYPE_CHECKING:
    from quadpype.pipeline.create import CreateContext  # noqa: F401

from . import pipeline

log = Logger.get_logger(__name__)


def load_scripts(paths):
    """Copy of `load_scripts` from Blender's implementation.

    It is possible that this function will be changed in future and usage will
    be based on Blender version.
    """
    import bpy_types

    loaded_modules = set()

    previous_classes = [
        cls
        for cls in bpy.types.bpy_struct.__subclasses__()
    ]

    def register_module_call(mod):
        register = getattr(mod, "register", None)
        if register:
            try:
                register()
            except:  # noqa E722
                traceback.print_exc()
        else:
            print("\nWarning! '%s' has no register function, "
                  "this is now a requirement for registerable scripts" %
                  mod.__file__)

    def unregister_module_call(mod):
        unregister = getattr(mod, "unregister", None)
        if unregister:
            try:
                unregister()
            except:  # noqa E722
                traceback.print_exc()

    def test_reload(mod):
        # reloading this causes internal errors
        # because the classes from this module are stored internally
        # possibly to refresh internal references too but for now, best not to.
        if mod == bpy_types:
            return mod

        try:
            return importlib.reload(mod)
        except:  # noqa E722
            traceback.print_exc()

    def test_register(mod):
        if mod:
            register_module_call(mod)
            bpy.utils._global_loaded_modules.append(mod.__name__)

    from bpy_restrict_state import RestrictBlend

    with RestrictBlend():
        for base_path in paths:
            for path_subdir in bpy.utils._script_module_dirs:
                path = os.path.join(base_path, path_subdir)
                if not os.path.isdir(path):
                    continue

                bpy.utils._sys_path_ensure_prepend(path)

                # Only add to 'sys.modules' unless this is 'startup'.
                if path_subdir != "startup":
                    continue
                for mod in bpy.utils.modules_from_path(path, loaded_modules):
                    test_register(mod)

    addons_paths = []
    for base_path in paths:
        addons_path = os.path.join(base_path, "addons")
        if not os.path.exists(addons_path):
            continue
        addons_paths.append(addons_path)
        addons_module_path = os.path.join(addons_path, "modules")
        if os.path.exists(addons_module_path):
            bpy.utils._sys_path_ensure_prepend(addons_module_path)

    if addons_paths:
        # Fake addons
        origin_paths = addon_utils.paths

        def new_paths():
            paths = origin_paths() + addons_paths
            return paths

        addon_utils.paths = new_paths
        addon_utils.modules_refresh()

    # load template (if set)
    if any(bpy.utils.app_template_paths()):
        import bl_app_template_utils
        bl_app_template_utils.reset(reload_scripts=False)
        del bl_app_template_utils

    for cls in bpy.types.bpy_struct.__subclasses__():
        if cls in previous_classes:
            continue
        if not getattr(cls, "is_registered", False):
            continue
        for subcls in cls.__subclasses__():
            if not subcls.is_registered:
                print(
                    "Warning, unregistered class: %s(%s)" %
                    (subcls.__name__, cls.__name__)
                )


def append_user_scripts():
    user_scripts = os.getenv("QUADPYPE_BLENDER_USER_SCRIPTS")
    if not user_scripts:
        return

    try:
        load_scripts(user_scripts.split(os.pathsep))
    except Exception:
        print("Couldn't load user scripts \"{}\"".format(user_scripts))
        traceback.print_exc()


def set_app_templates_path():
    # Blender requires the app templates to be in `BLENDER_USER_SCRIPTS`.
    # After running Blender, we set that variable to our custom path, so
    # that the user can use their custom app templates.

    # We look among the scripts paths for one of the paths that contains
    # the app templates. The path must contain the subfolder
    # `startup/bl_app_templates_user`.
    paths = os.getenv("QUADPYPE_BLENDER_USER_SCRIPTS")
    if not paths:
        return

    paths = paths.split(os.pathsep)
    app_templates_path = None
    for path in paths:
        if os.path.isdir(
                os.path.join(path, "startup", "bl_app_templates_user")):
            app_templates_path = path
            break

    if app_templates_path and os.path.isdir(app_templates_path):
        os.environ["BLENDER_USER_SCRIPTS"] = app_templates_path


def imprint(node: bpy.types.bpy_struct_meta_idprop, data: Dict, erase: bool=False):
    r"""Write `data` to `node` as userDefined attributes

    Arguments:
        node: Long name of node
        data: Dictionary of key/value pairs
        erase(optional): Erase previous value insted of updating / adding data

    Example:
        >>> import bpy
        >>> def compute():
        ...   return 6
        ...
        >>> bpy.ops.mesh.primitive_cube_add()
        >>> cube = bpy.context.view_layer.objects.active
        >>> imprint(cube, {
        ...   "regularString": "myFamily",
        ...   "computedValue": lambda: compute()
        ... })
        ...
        >>> cube['avalon']['computedValue']
        6
    """

    imprint_data = dict()

    for key, value in data.items():
        if value is None:
            continue

        if callable(value):
            # Support values evaluated at imprint
            value = value()

        if not isinstance(value, (int, float, bool, str, list, dict)):
            raise TypeError(f"Unsupported type: {type(value)}")

        imprint_data[key] = value

    pipeline.metadata_update(node, imprint_data, erase)


def lsattr(attr: str,
           value: Union[str, int, bool, List, Dict, None] = None) -> List:
    r"""Return nodes matching `attr` and `value`

    Arguments:
        attr: Name of Blender property
        value: Value of attribute. If none
            is provided, return all nodes with this attribute.

    Example:
        >>> lsattr("id", "myId")
        ...   [bpy.data.objects["myNode"]
        >>> lsattr("id")
        ...   [bpy.data.objects["myNode"], bpy.data.objects["myOtherNode"]]

    Returns:
        list
    """

    return lsattrs({attr: value})


def lsattrs(attrs: Dict) -> List:
    r"""Return nodes with the given attribute(s).

    Arguments:
        attrs: Name and value pairs of expected matches

    Example:
        >>> lsattrs({"age": 5})  # Return nodes with an `age` of 5
        # Return nodes with both `age` and `color` of 5 and blue
        >>> lsattrs({"age": 5, "color": "blue"})

    Returns a list.

    """

    # For now return all objects, not filtered by scene/collection/view_layer.
    matches = set()
    for coll in dir(bpy.data):
        if not isinstance(
                getattr(bpy.data, coll),
                bpy.types.bpy_prop_collection,
        ):
            continue
        for node in getattr(bpy.data, coll):
            avalon_prop = pipeline.get_avalon_node(node)
            if not avalon_prop:
                continue

            for attr, value in attrs.items():
                if (avalon_prop.get(attr)
                        and (value is None or avalon_prop.get(attr) == value)):
                    matches.add(node)
    return list(matches)


def read(node: bpy.types.bpy_struct_meta_idprop):
    """Return user-defined attributes from `node`"""

    data = pipeline.get_avalon_node(node)

    # Ignore hidden/internal data
    data = {
        key: value
        for key, value in data.items() if not key.startswith("_")
    }

    return data


def get_object_types_correspondance():
    rna_to_bpy_data = dict()
    for name in dir(bpy.data):
        prop = getattr(bpy.data, name)
        if isinstance(prop, bpy.types.bpy_prop_collection):
            try:
                if len(prop) > 0:
                    identifiers = {pr.bl_rna.identifier for pr in prop}
                    rna_to_bpy_data.update({identifier: name for identifier in identifiers})
            except Exception:
                pass
    return rna_to_bpy_data


def map_to_classes_and_names(blender_objects):
    """ Get a list of blender_objects and produce a dictionary composed of all previous objects
    sorted by types (as accessible from `bpy.data`, and not `bpy.types`, to make it easier
    to load after).

    Arguments:
        blender_objects: list of objects retrieved from Blender scene.

    Returns:
        dict: Objects sorted by objects types, for example :
        {
            'objects': ['eltA', 'eltB'],
            'cameras': ['eltC']
        }
    """
    mapped_values = dict()
    rna_to_bpy_data = get_object_types_correspondance()

    for blender_object in blender_objects:
        object_data_name = rna_to_bpy_data[blender_object.bl_rna.identifier]
        if not mapped_values.get(object_data_name):
            mapped_values[object_data_name] = list()
        mapped_values[object_data_name].append(blender_object.name)

    return mapped_values


def get_data_type_name(blender_data):
    """Retrieve the name of the data type base on a data block"""
    data_type_dict = map_to_classes_and_names([blender_data])
    return next((k for k, v in data_type_dict.items() if blender_data.name in v), None)


def get_objects_from_mapped(mapped_objects):
    """ Get a list of mapped blender_objects (with objects types as keys and list of objects as values)
    and return retrieved objects from Blender scene, with all inner functions and methods accessible.

    Arguments:
        mapped_objects: Objects sorted by objects types, as produced by `map_to_classes_and_names` function.

    Returns:
        list: Blender objects retrieved from scene.
    """
    blender_objects = list()
    for data_type, blender_objects_names in mapped_objects.items():
        blender_objects.extend(
            [
                getattr(bpy.data, data_type)[blender_object_name]
                for blender_object_name in blender_objects_names
            ]
        )

    return blender_objects


def _outliner_context():
    window = bpy.context.window or bpy.context.window_manager.windows[0]

    try:
        area = next(
            area for area in window.screen.areas
            if area.type == 'OUTLINER')
        region = next(
            region for region in area.regions
            if region.type == 'WINDOW')
    except StopIteration as e:
        raise RuntimeError("Could not find outliner. An outliner space "
                           "must be in the main Blender window.") from e

    return bpy.context.temp_override(
            window=window,
            area=area,
            region=region,
            screen=window.screen
    )


def get_selected_collections():
    """
    Returns a list of the currently selected collections in the outliner.

    Raises:
        RuntimeError: If the outliner cannot be found in the main Blender
        window.

    Returns:
        list: A list of `bpy.types.Collection` objects that are currently
        selected in the outliner.
    """
    with _outliner_context():
        ids = bpy.context.selected_ids

    return [id for id in ids if isinstance(id, bpy.types.Collection)]


def get_selected_objects():
    """
    Returns a list of the currently selected objects in the outliner.

    Raises:
        RuntimeError: If the outliner cannot be found in the main Blender
        window.

    Returns:
        list: A list of `bpy.types.Object` objects that are currently
        selected in the outliner.
    """

    with _outliner_context():
        return bpy.context.selected_objects


def get_selection(include_collections: bool = False) -> List[bpy.types.Object]:
    """
    Returns a list of selected objects in the current Blender scene.

    Args:
        include_collections (bool, optional): Whether to include selected
        collections in the result. Defaults to False.

    Returns:
        List[bpy.types.Object]: A list of selected objects.
    """
    selection = [obj for obj in bpy.context.scene.objects if obj.select_get()]

    if include_collections:
        selection.extend(get_selected_collections())

    return selection


@contextlib.contextmanager
def maintained_selection():
    r"""Maintain selection during context

    Example:
        >>> with maintained_selection():
        ...     # Modify selection
        ...     bpy.ops.object.select_all(action='DESELECT')
        >>> # Selection restored
    """

    previous_selection = get_selection()
    previous_active = bpy.context.view_layer.objects.active
    try:
        yield
    finally:
        # Clear the selection
        for node in get_selection():
            node.select_set(state=False)
        if previous_selection:
            for node in previous_selection:
                try:
                    node.select_set(state=True)
                except ReferenceError:
                    # This could happen if a selected node was deleted during
                    # the context.
                    log.exception("Failed to reselect")
                    continue
        try:
            bpy.context.view_layer.objects.active = previous_active
        except ReferenceError:
            # This could happen if the active node was deleted during the
            # context.
            log.exception("Failed to set active object.")


@contextlib.contextmanager
def maintained_time():
    """Maintain current frame during context."""
    current_time = bpy.context.scene.frame_current
    try:
        yield
    finally:
        bpy.context.scene.frame_current = current_time


def get_all_parents(obj):
    """Get all recursive parents of object.

    Arguments:
        obj (bpy.types.Object): Object to get all parents for.

    Returns:
        List[bpy.types.Object]: All parents of object

    """
    if not isinstance(obj, bpy.types.Object):
        return []

    result = []
    while True:
        obj = obj.parent
        if not obj:
            break
        result.append(obj)
    return result


def get_objects_in_collection(collection):
    """Retrieve recursively  all objects in a collection, even in sub collection"""
    objects = list(collection.objects)
    for sub_collection in collection.children:
        objects.extend(get_objects_in_collection(sub_collection))
    return objects


def get_highest_root(objects):
    """Get the highest object (the least parents) among the objects.

    If multiple objects have the same amount of parents (or no parents) the
    first object found in the input iterable will be returned.

    Note that this will *not* return objects outside of the input list, as
    such it will not return the root of node from a child node. It is purely
    intended to find the highest object among a list of objects. To instead
    get the root from one object use, e.g. `get_all_parents(obj)[-1]`

    Arguments:
        objects (List[bpy.types.Object]): Objects to find the highest root in.

    Returns:
        Optional[bpy.types.Object]: First highest root found or None if no
            `bpy.types.Object` found in input list.

    """
    included_objects = {obj.name_full for obj in objects}
    num_parents_to_obj = {}
    for obj in objects:
        if isinstance(obj, bpy.types.Object):
            parents = get_all_parents(obj)
            # included parents
            parents = [parent for parent in parents if
                       parent.name_full in included_objects]
            if not parents:
                # A node without parents must be a highest root
                return obj

            num_parents_to_obj.setdefault(len(parents), obj)

    if not num_parents_to_obj:
        return

    minimum_parent = min(num_parents_to_obj)
    return num_parents_to_obj[minimum_parent]


def get_objects_concerned_by_ids():
    return list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.collections)


def get_id(entity=None, entity_name=None):
    """Get the `cbId` attribute of the given entity.

    Args:
        entity (object): blender object to retrieve the attribute from
        entity_name (str): the name of the entity to retrieve the attribute from
    Returns:
        str: id of asked entity

    """
    return _get_property("id", entity, entity_name)


def get_targets_ids(entity=None, entity_name=None):
    """Get the `targets_ids` attribute of the given entity.

    Args:
        entity (object): blender object to retrieve the attribute from
        entity_name (str): the name of the entity to retrieve the attribute from
    Returns:
        list[str]: list of targets ids of asked entity

    """
    targets_ids_property = _get_property("targets_ids", entity, entity_name)
    if not targets_ids_property:
        return []

    return json.loads(targets_ids_property)


def _get_property(property_name, entity=None, entity_name=None):
    """Get the given property attribute of the given entity.

    Args:
        property_name (str): name of the property to retrieve
        entity (object): blender object to retrieve the attribute from
        entity_name (str): the name of the entity to retrieve the attribute from
    Returns:
        any: value of asked property from entity

    """
    if not any([entity, entity_name]):
        return None

    if not entity:
        objects = get_objects_concerned_by_ids()
        try:
            entity = next(
                iter(
                    entity for entity in objects
                    if entity.name == entity_name
                )
            )
        except StopIteration:
            return None

    try:
        return entity.get(property_name, None)
    except RuntimeError:
        log.warning("Failed to retrieve id on %s", entity)
        return None


def get_objects_by_ids(ids):
    """Retrieve objects in scene with given ids.

    Args:
        ids (str, list[str]): single or list of ids to search for

    Returns:
        list: A list of blender objects.
    """
    return [
        obj for obj in get_objects_concerned_by_ids()
        if get_id(obj) in ids
    ]


def generate_ids(objects, asset_id=None):
    """Returns new unique ids for the given objects.

    Args:
        objects (list): List of objects.
        asset_id (str or bson.ObjectId): The database id for the *asset* to
            generate for. When None provided the current asset in the
            active session is used.

    Returns:
        list: A list of (objects, id) tuples.

    """

    if asset_id is None:
        # Get the asset ID from the database for the asset of current context
        project_name = get_current_project_name()
        asset_name = get_current_asset_name()
        asset_doc = get_asset_by_name(project_name, asset_name, fields=["_id"])
        assert asset_doc, "No current asset found in Session"
        asset_id = asset_doc['_id']

    objects_ids = []
    for entity in objects:
        _, uid = str(uuid.uuid4()).rsplit("-", 1)
        unique_id = "{}:{}".format(asset_id, uid)
        objects_ids.append((entity, unique_id))

    return objects_ids


def set_id(entity, unique_id, overwrite=False):
    """Add cbId to `entity` unless one already exists.

    Args:
        entity (object): the blender object to add the "cbId" on
        unique_id (str): The unique node id to assign.
            This should be generated by `generate_ids`.
        overwrite (bool, optional): When True overrides the current value even
            if `entity` already has an id. Defaults to False.

    Returns:
        None

    """
    _set_property(
        entity=entity,
        property_name="id",
        property_value=unique_id,
        overwrite=overwrite
    )


def set_targets_ids(entity, targets_ids, overwrite=False):
    """Add targets_ids to `entity` unless one already exists.

    Args:
        entity (object): the blender object to add the "cbId" on
        targets_ids (list[str]): targets_ids to assign.
            These should be retrieved from objects and first generated by `generate_ids`.
        overwrite (bool, optional): When True overrides the current value even
            if `entity` already has targets ids. Defaults to False.

    Returns:
        None

    """
    _set_property(
        entity=entity,
        property_name="targets_ids",
        property_value=json.dumps(targets_ids),
        overwrite=overwrite
    )


def _set_property(entity, property_name, property_value, overwrite):
    """set property with given value.

    Args:
        entity (object): the blender object to add property
        property_name (str): Name of the property to update
        property_value (str, list): Value of the property to set
        overwrite (bool, optional): When True overrides the current value even
            if `entity` already has given property. Defaults to False.

    Returns:
        None

    """
    exists = entity.get(property_name)
    if not exists or overwrite:
        entity[property_name] = property_value


def add_target_id(concerned_object, target_id):
    targets_ids = get_targets_ids(concerned_object)

    if target_id in targets_ids:
        return

    targets_ids.append(target_id)
    set_targets_ids(
        entity=concerned_object,
        targets_ids=targets_ids,
        overwrite=True
    )


def has_materials(obj):
    return (
        obj and
        not is_collection(obj) and
        hasattr(obj, 'material_slots') and
        len(obj.material_slots) > 0
    )


@contextlib.contextmanager
def attribute_overrides(
        obj,
        attribute_values
):
    """Apply attribute or property overrides during context.

    Supports nested/deep overrides, that is also why it does not use **kwargs
    as function arguments because it requires the keys to support dots (`.`).

    Example:
        >>> with attribute_overrides(scene, {
        ...     "render.fps": 30,
        ...     "frame_start": 1001}
        ... ):
        ...     print(scene.render.fps)
        ...     print(scene.frame_start)
        # 30
        # 1001

    Arguments:
        obj (Any): The object to set attributes and properties on.
        attribute_values: (dict[str, Any]): The property names mapped to the
            values that will be applied during the context.
    """
    if not attribute_values:
        # do nothing
        yield
        return

    # Helper functions to get and set nested keys on the scene object like
    # e.g. "scene.unit_settings.scale_length" or "scene.render.fps"
    # by doing `setattr_deep(scene, "unit_settings.scale_length", 10)`
    def getattr_deep(root, path):
        for key in path.split("."):
            root = getattr(root, key)
        return root

    def setattr_deep(root, path, value):
        keys = path.split(".")
        last_key = keys.pop()
        for key in keys:
            root = getattr(root, key)
        return setattr(root, last_key, value)

    # Get original values
    original = {
        key: getattr_deep(obj, key) for key in attribute_values
    }
    try:
        for key, value in attribute_values.items():
            setattr_deep(obj, key, value)
        yield
    finally:
        for key, value in original.items():
            setattr_deep(obj, key, value)


def collect_animation_defs(step=True, fps=False):
    """Get the basic animation attribute definitions for the publisher.

    Arguments:
        create_context (CreateContext): The context of publisher will be
            used to define the defaults for the attributes to use the current
            context's entity frame range as default values.
        step (bool): Whether to include `step` attribute definition.
        fps (bool): Whether to include `fps` attribute definition.

    Returns:
        List[NumberDef]: List of number attribute definitions.

    """

    # get scene values as defaults
    scene = bpy.context.scene

    # use task entity attributes to set defaults based on current context
    project_name = get_current_project_name()
    asset_name = get_current_asset_name()
    attrib = get_asset_by_name(project_name, asset_name)
    frame_start = attrib.get("frameStart", scene.frame_start)
    frame_end = attrib.get("frameEnd", scene.frame_end)
    handle_start = attrib.get("handleStart", 0)
    handle_end = attrib.get("handleEnd", 0)

    # build attributes
    defs = [
        NumberDef("frameStart",
                  label="Frame Start",
                  default=frame_start,
                  decimals=0),
        NumberDef("frameEnd",
                  label="Frame End",
                  default=frame_end,
                  decimals=0),
        NumberDef("handleStart",
                  label="Handle Start",
                  tooltip="Frames added before frame start to use as handles.",
                  default=handle_start,
                  decimals=0),
        NumberDef("handleEnd",
                  label="Handle End",
                  tooltip="Frames added after frame end to use as handles.",
                  default=handle_end,
                  decimals=0),
    ]

    if step:
        defs.append(
            NumberDef(
                "step",
                label="Step size",
                tooltip="Number of frames to skip forward while rendering/"
                        "playing back each frame",
                default=1,
                decimals=0
            )
        )

    if fps:
        current_fps = scene.render.fps / scene.render.fps_base
        fps_def = NumberDef(
            "fps", label="FPS", default=current_fps, decimals=5
        )
        defs.append(fps_def)

    return defs


def get_cache_modifiers(obj, modifier_type="MESH_SEQUENCE_CACHE"):
    modifiers_dict = {}
    modifiers = [modifier for modifier in obj.modifiers
                 if modifier.type == modifier_type]
    if modifiers:
        modifiers_dict[obj.name] = modifiers
    else:
        for sub_obj in obj.children:
            for ob in sub_obj.children:
                cache_modifiers = [modifier for modifier in ob.modifiers
                                   if modifier.type == modifier_type]
                modifiers_dict[ob.name] = cache_modifiers
    return modifiers_dict


def get_blender_version():
    """Get Blender Version
    """
    major, minor, subversion = bpy.app.version
    return major, minor, subversion


def get_parents_for_collection(collection, collections=None):
    if not collections:
        collections = bpy.data.collections
    return [c for c in collections if c.user_of_id(collection)]


def get_parent_collections_for_object(obj):
    """Retrieve the object parent's collection
    Args:
        obj (bpy.types.Object or str): a blender object or its name
    Return:
        bpy.types.Collection: The parent collection
    """
    parent_collections = set()
    if isinstance(obj, str):
        obj = bpy.data.objects.get(obj)

    if not obj:
        raise ValueError("Object doesn't exist")

    if obj:
        for coll in bpy.data.collections:
            if obj.name in coll.objects:
                parent_collections.add(coll)

    return parent_collections


def make_scene_empty(scene=None):
    """Delete all objects, worlds and collections in given scene and clean everything.
        Args:
            scene (bpy.types.Scene or str): a blender scene object, or its name
    """

    # If no scene scpecified
    if scene is None:
        # Not specified: it's the current scene.
        scene = bpy.context.scene
    else:
        # if scene is a scene.name
        if isinstance(scene, str):
            # Specified by name: get the scene object.
            scene = bpy.data.scenes[scene]
        # Otherwise, assume it's a scene object already.

    # Remove objects.
    for object_ in scene.objects:
        bpy.data.objects.remove(object_, do_unlink=True)

    # Remove worlds.
    for world_ in bpy.data.worlds:
        bpy.data.worlds.remove(world_, do_unlink=True)

    # Remove collections.
    for coll_ in bpy.data.collections:
        bpy.data.collections.remove(coll_, do_unlink=True)

    # Remove linked library
    for lib in bpy.data.libraries:
        bpy.data.libraries.remove(lib, do_unlink=True)

    # Clean everything
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def purge_orphans(is_recursive):
    data_types = [attr for attr in dir(bpy.data) if
                    isinstance(getattr(bpy.data, attr), bpy.types.bpy_prop_collection)]

    for data_type in data_types:
        data_collection = getattr(bpy.data, data_type)

        for item in list(data_collection):
            if item.users == 0:
                data_collection.remove(item)

    if is_recursive:
        purge_orphans(is_recursive=False)


def get_asset_children(asset):
    return list(asset.objects) if isinstance(asset, bpy.types.Collection) else list(asset.children)


def get_and_select_camera(objects):
    for blender_object in objects:
        if blender_object.type == "CAMERA":
            blender_object.select_set(True)
            return blender_object.data

        camera = get_and_select_camera(list(blender_object.children))
        if camera:
            return camera


def is_camera(obj):
    return isinstance(obj, bpy.types.Object) and obj.type == "CAMERA"


def is_collection(obj):
    return isinstance(obj, bpy.types.Collection)
