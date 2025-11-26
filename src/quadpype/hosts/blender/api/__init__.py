"""Public API

Anything that isn't defined here is INTERNAL and unreliable for external use.

"""

from .pipeline import (
    install,
    uninstall,
    ls,
    publish,
    containerise,
    BlenderHost,
    set_custom_frame_offset,
    get_avalon_node,
    has_avalon_node,
    delete_avalon_node
)

from .plugin import (
    BlenderCreator,
    BlenderLoader,
)

from .workio import (
    open_file,
    save_file,
    current_file,
    has_unsaved_changes,
    file_extensions,
    work_root,
)

from .lib import (
    lsattr,
    lsattrs,
    read,
    map_to_classes_and_names,
    get_objects_from_mapped,
    get_objects_by_ids,
    get_id,
    get_targets_ids,
    set_id,
    set_targets_ids,
    generate_ids,
    add_target_id,
    has_materials,
    maintained_selection,
    maintained_time,
    get_selection,
    get_selected_objects,
    get_selected_collections,
    get_parents_for_collection,
    get_objects_in_collection,
    get_asset_children,
    get_and_select_camera,
    is_camera,
    is_collection,
    get_objects_in_collection
)

from .capture import capture

from .render_lib import prepare_rendering

from .collections import (
    get_corresponding_hierarchies_numbered,
    create_collections_from_hierarchy,
    create_collection,
    get_top_collection
)


__all__ = [
    "install",
    "uninstall",
    "ls",
    "publish",
    "containerise",
    "BlenderHost",
    "get_avalon_node",
    "has_avalon_node",
    "delete_avalon_node",
    "set_custom_frame_offset",
    "BlenderCreator",
    "BlenderLoader",

    # Workfiles API
    "open_file",
    "save_file",
    "current_file",
    "has_unsaved_changes",
    "file_extensions",
    "work_root",

    # Utility functions
    "get_objects_by_ids",
    "get_id",
    "get_targets_ids",
    "set_id",
    "set_targets_ids",
    "generate_ids",
    "add_target_id",
    "has_materials",
    "maintained_selection",
    "maintained_time",
    "lsattr",
    "lsattrs",
    "read",
    "map_to_classes_and_names",
    "get_objects_from_mapped",
    "get_selection",
    "get_selected_objects",
    "get_selected_collections",
    "capture",
    # "unique_name",
    "prepare_rendering",

    # Collections getters
    "get_parents_for_collection",
    "get_objects_in_collection",
    "get_top_collection",

    # Objects manipulation
    "get_asset_children",
    "get_and_select_camera",

    # Checkers
    "is_camera",
    "is_collection",

    # Collections tools
    "get_corresponding_hierarchies_numbered",
    "create_collections_from_hierarchy",
    "create_collection",
]
