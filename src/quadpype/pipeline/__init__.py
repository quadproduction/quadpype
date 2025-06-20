from .constants import (
    AVALON_CONTAINER_ID,
    HOST_WORKFILE_EXTENSIONS,
)

from .mongodb import (
    AvalonMongoDB,
)
from .anatomy import Anatomy

from .create import (
    BaseCreator,
    Creator,
    AutoCreator,
    HiddenCreator,
    CreatedInstance,
    CreatorError,

    LegacyCreator,
    legacy_create,

    discover_creator_plugins,
    discover_legacy_creator_plugins,
    register_creator_plugin,
    deregister_creator_plugin,
    register_creator_plugin_path,
    deregister_creator_plugin_path
)

from .load import (
    HeroVersionType,
    IncompatibleLoaderError,
    LoaderPlugin,
    SubsetLoaderPlugin,

    discover_loader_plugins,
    register_loader_plugin,
    deregister_loader_plugin_path,
    register_loader_plugin_path,
    deregister_loader_plugin,

    load_container,
    remove_container,
    update_container,
    switch_container,

    loaders_from_representation,
    get_representation_path,
    get_representation_context,
    get_repres_contexts
)

from .publish import (
    PublishValidationError,
    PublishXmlValidationError,
    KnownPublishError,
    QuadPypePyblishPluginMixin,
    OptionalPyblishPluginMixin
)

from .actions import (
    LauncherAction,
    LauncherTaskAction,

    ApplicationAction,

    InventoryAction,

    discover_launcher_actions,
    register_launcher_action,
    register_launcher_action_path,

    discover_inventory_actions,
    register_inventory_action,
    register_inventory_action_path,
    deregister_inventory_action,
    deregister_inventory_action_path
)

from .context_tools import (
    install_quadpype_plugins,
    install_host,
    uninstall_host,
    is_installed,

    register_root,
    registered_root,

    register_host,
    registered_host,
    deregister_host,
    get_process_id,

    get_global_context,
    get_current_context,
    get_current_host_name,
    get_current_project_name,
    get_current_asset_name,
    get_current_task_name
)

from .action import (
    BuilderAction,

    discover_builder_plugins,
    register_builder_action,
    register_builder_action_path,
    deregister_builder_action,
    deregister_builder_action_path,

    get_actions_by_name,
    action_with_repre_context
)

from .templates import (
    get_load_naming_template,
    get_loaded_naming_finder_template,
    get_task_hierarchy_templates,
    get_workfile_build_template,
    get_resolved_name,
    format_data,
    get_parent_data,
    split_hierarchy,
    is_current_asset_shot,
    extract_sequence_and_shot
)

from .settings import (
    get_available_resolutions,
    extract_width_and_height
)

install = install_host
uninstall = uninstall_host


__all__ = (
    "AVALON_CONTAINER_ID",
    "HOST_WORKFILE_EXTENSIONS",

    # --- MongoDB ---
    "AvalonMongoDB",

    # --- Anatomy ---
    "Anatomy",

    # --- Create ---
    "BaseCreator",
    "Creator",
    "AutoCreator",
    "HiddenCreator",
    "CreatedInstance",
    "CreatorError",

    "CreatorError",

    # - legacy creation
    "LegacyCreator",
    "legacy_create",

    "discover_creator_plugins",
    "discover_legacy_creator_plugins",
    "register_creator_plugin",
    "deregister_creator_plugin",
    "register_creator_plugin_path",
    "deregister_creator_plugin_path",

    # --- Load ---
    "HeroVersionType",
    "IncompatibleLoaderError",
    "LoaderPlugin",
    "SubsetLoaderPlugin",

    "discover_loader_plugins",
    "register_loader_plugin",
    "deregister_loader_plugin_path",
    "register_loader_plugin_path",
    "deregister_loader_plugin",

    "load_container",
    "remove_container",
    "update_container",
    "switch_container",

    "loaders_from_representation",
    "get_representation_path",
    "get_representation_context",
    "get_repres_contexts",

    # --- Publish ---
    "PublishValidationError",
    "PublishXmlValidationError",
    "KnownPublishError",
    "QuadPypePyblishPluginMixin",
    "OptionalPyblishPluginMixin",

    # --- Actions ---
    "LauncherAction",
    "LauncherTaskAction",

    "ApplicationAction",
    "InventoryAction",

    "discover_launcher_actions",
    "register_launcher_action",
    "register_launcher_action_path",

    "discover_inventory_actions",
    "register_inventory_action",
    "register_inventory_action_path",
    "deregister_inventory_action",
    "deregister_inventory_action_path",

    # --- Process context ---
    "install_quadpype_plugins",
    "install_host",
    "uninstall_host",
    "is_installed",

    "register_root",
    "registered_root",

    "register_host",
    "registered_host",
    "deregister_host",
    "get_process_id",

    "get_global_context",
    "get_current_context",
    "get_current_host_name",
    "get_current_project_name",
    "get_current_asset_name",
    "get_current_task_name",

    # --- Action ---
    "BuilderAction",

    "discover_builder_plugins",
    "register_builder_action",
    "register_builder_action_path",
    "deregister_builder_action",
    "deregister_builder_action_path",

    "get_actions_by_name",
    "action_with_repre_context",

    # Backwards compatible function names
    "install",
    "uninstall",

    # --- Templates ---
    "get_load_naming_template",
    "get_loaded_naming_finder_template",
    "get_task_hierarchy_templates",
    "get_workfile_build_template",
    "get_resolved_name",
    "format_data",
    "get_parent_data",
    "split_hierarchy",
    "is_current_asset_shot",
    "extract_sequence_and_shot"

    # --- Settings ---
    "get_available_resolutions",
    "extract_width_and_height",

)
