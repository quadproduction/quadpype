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
    maintained_selection,
    maintained_time,
    get_selection,
    # unique_name,
)

from .capture import capture

from .render_lib import prepare_rendering

from .template_resolving import (
    get_resolved_name,
    get_entity_collection_template,
    get_task_collection_template,
    update_parent_data_with_entity_prefix
)


__all__ = [
    "install",
    "uninstall",
    "ls",
    "publish",
    "containerise",
    "BlenderHost",

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
    "maintained_selection",
    "maintained_time",
    "lsattr",
    "lsattrs",
    "read",
    "get_selection",
    "capture",
    # "unique_name",
    "prepare_rendering",

    #Templates for working:
    "get_resolved_name",
    "get_entity_collection_template",
    "get_task_collection_template",
    "update_parent_data_with_entity_prefix"
]
