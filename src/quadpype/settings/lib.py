import os
import json
import functools
import logging
import platform
import copy

from appdirs import user_data_dir
from typing import Union, List
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import certifi
from pymongo import MongoClient
from semver import VersionInfo

from .exceptions import (
    SaveWarningExc
)
from .constants import (
    M_OVERRIDDEN_KEY,

    METADATA_KEYS,

    DEFAULTS_DIR,

    CORE_KEYS,
    CORE_SETTINGS_DOC_KEY,
    CORE_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY,
    PROJECT_SETTINGS_KEY,
    PROJECT_ANATOMY_KEY,
    DEFAULT_PROJECT_KEY,

    ENV_SETTINGS_KEY,
    APPS_SETTINGS_KEY,
    ADDONS_SETTINGS_KEY,
    PROJECTS_SETTINGS_KEY,

    DATABASE_ALL_VERSIONS_KEY,
    DATABASE_VERSIONS_ORDER,
    DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY
)

log = logging.getLogger(__name__)

JSON_EXC = getattr(json.decoder, "JSONDecodeError", ValueError)


# Variable where cache of default settings are stored
_DEFAULT_SETTINGS = None

# Handler for studio overrides
_SETTINGS_HANDLER = None


def calculate_changes(old_value, new_value):
    changes = {}
    for key, value in new_value.items():
        if key not in old_value:
            changes[key] = value
            continue

        _value = old_value[key]
        if isinstance(value, dict) and isinstance(_value, dict):
            _changes = calculate_changes(_value, value)
            if _changes:
                changes[key] = _changes
            continue

        if _value != value:
            changes[key] = value
    return changes


def create_settings_handler():
    from .handlers import MongoSettingsHandler
    # Handler can't be created in global space on initialization but only when needed.
    return MongoSettingsHandler()


def require_settings_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _SETTINGS_HANDLER
        if _SETTINGS_HANDLER is None:
            _SETTINGS_HANDLER = create_settings_handler()
        return func(*args, **kwargs)
    return wrapper


@require_settings_handler
def get_global_settings_last_saved_info():
    return _SETTINGS_HANDLER.get_global_settings_last_saved_info()  #noqa


@require_settings_handler
def get_project_settings_last_saved_info(project_name):
    return _SETTINGS_HANDLER.get_project_settings_last_saved_info(project_name)


@require_settings_handler
def get_last_opened_info():
    return _SETTINGS_HANDLER.get_last_opened_info()


@require_settings_handler
def opened_settings_ui():
    return _SETTINGS_HANDLER.opened_settings_ui()


@require_settings_handler
def closed_settings_ui(info_obj):
    return _SETTINGS_HANDLER.closed_settings_ui(info_obj)


@require_settings_handler
def save_studio_settings(data):
    """Save studio overrides of global settings.

    Triggers callbacks on modules that want to know about global settings
    changes.

    Callbacks are triggered on all modules. They must check if their enabled
    value has changed.

    For saving of data cares registered Settings handler.

    Warning messages are not logged as module raising them should log it within
    it's logger.

    Args:
        data(dict): Overrides data with metadata defying studio overrides.

    Raises:
        SaveWarningExc: If any module raises the exception.
    """
    # Notify QuadPype modules
    from quadpype.modules import ModulesManager, ISettingsChangeListener

    old_data = get_global_settings()
    default_values = get_default_settings()[GLOBAL_SETTINGS_KEY]
    new_data = apply_overrides(default_values, copy.deepcopy(data))
    new_data_with_metadata = copy.deepcopy(new_data)
    clear_metadata_from_settings(new_data)

    changes = calculate_changes(old_data, new_data)
    modules_manager = ModulesManager(new_data)

    warnings = []
    for module in modules_manager.get_enabled_modules():
        if isinstance(module, ISettingsChangeListener):
            try:
                module.on_global_settings_save(
                    old_data, new_data, changes, new_data_with_metadata
                )
            except SaveWarningExc as exc:
                warnings.extend(exc.warnings)

    _SETTINGS_HANDLER.save_change_log(None, changes, "global")
    _SETTINGS_HANDLER.save_studio_settings(data)
    if warnings:
        raise SaveWarningExc(warnings)


@require_settings_handler
def save_project_settings(project_name, overrides):
    """Save studio overrides of project settings.

    Old value, new value and changes are passed to enabled modules that want to
    know about settings changes.

    For saving of data cares registered Settings handler.

    Warning messages are not logged as module raising them should log it within
    it's logger.

    Args:
        project_name (str): Project name for which overrides are passed.
            Default project's value is None.
        overrides(dict): Overrides data with metadata defying studio overrides.

    Raises:
        SaveWarningExc: If any module raises the exception.
    """
    # Notify QuadPype modules
    from quadpype.modules import ModulesManager, ISettingsChangeListener

    default_values = get_default_settings()[PROJECT_SETTINGS_KEY]
    if project_name:
        old_data = get_project_settings(project_name)

        studio_overrides = get_studio_project_settings_overrides()
        studio_values = apply_overrides(default_values, studio_overrides)
        clear_metadata_from_settings(studio_values)
        new_data = apply_overrides(studio_values, copy.deepcopy(overrides))

    else:
        old_data = get_default_project_settings(exclude_locals=True)
        new_data = apply_overrides(default_values, copy.deepcopy(overrides))

    new_data_with_metadata = copy.deepcopy(new_data)
    clear_metadata_from_settings(new_data)

    changes = calculate_changes(old_data, new_data)
    modules_manager = ModulesManager()
    warnings = []
    for module in modules_manager.get_enabled_modules():
        if isinstance(module, ISettingsChangeListener):
            try:
                module.on_project_settings_save(
                    old_data,
                    new_data,
                    project_name,
                    changes,
                    new_data_with_metadata
                )
            except SaveWarningExc as exc:
                warnings.extend(exc.warnings)
    _SETTINGS_HANDLER.save_change_log(project_name, changes, "project")
    _SETTINGS_HANDLER.save_project_settings(project_name, overrides)

    if warnings:
        raise SaveWarningExc(warnings)


@require_settings_handler
def save_project_anatomy(project_name, anatomy_data):
    """Save studio overrides of project anatomy.

    Old value, new value and changes are passed to enabled modules that want to
    know about settings changes.

    For saving of data cares registered Settings handler.

    Warning messages are not logged as module raising them should log it within
    it's logger.

    Args:
        project_name (str): Project name for which overrides are passed.
            Default project's value is None.
        overrides(dict): Overrides data with metadata defying studio overrides.

    Raises:
        SaveWarningExc: If any module raises the exception.
    """
    bypass_protect_attrs = anatomy_data.pop("bypass_protect_anatomy_attributes", None)
    # Notify QuadPype modules
    from quadpype.modules import ModulesManager, ISettingsChangeListener

    default_values = get_default_settings()[PROJECT_ANATOMY_KEY]
    if project_name:
        old_data = get_anatomy_settings(project_name)

        studio_overrides = get_studio_project_settings_overrides()
        studio_values = apply_overrides(default_values, studio_overrides)
        clear_metadata_from_settings(studio_values)
        new_data = apply_overrides(studio_values, copy.deepcopy(anatomy_data))

    else:
        old_data = get_default_anatomy_settings(exclude_locals=True)
        new_data = apply_overrides(default_values, copy.deepcopy(anatomy_data))

    new_data_with_metadata = copy.deepcopy(new_data)
    if bypass_protect_attrs is not None:
        new_data_with_metadata["bypass_protect_anatomy_attributes"] = bypass_protect_attrs
    clear_metadata_from_settings(new_data)

    changes = calculate_changes(old_data, new_data)
    modules_manager = ModulesManager()
    warnings = []
    for module in modules_manager.get_enabled_modules():
        if isinstance(module, ISettingsChangeListener):
            try:
                module.on_project_anatomy_save(
                    old_data,
                    new_data,
                    changes,
                    project_name,
                    new_data_with_metadata
                )
            except SaveWarningExc as exc:
                warnings.extend(exc.warnings)

    _SETTINGS_HANDLER.save_change_log(project_name, changes, "anatomy")
    _SETTINGS_HANDLER.save_project_anatomy(project_name, anatomy_data)

    if warnings:
        raise SaveWarningExc(warnings)


def _global_settings_backwards_compatible_conversion(studio_overrides):
    # Backwards compatibility of tools 3.9.1 - 3.9.2 to keep
    #   "tools" environments
    if (
        "tools" in studio_overrides
        and "tool_groups" in studio_overrides["tools"]
    ):
        tool_groups = studio_overrides["tools"]["tool_groups"]
        for tool_group, group_value in tool_groups.items():
            if tool_group in METADATA_KEYS:
                continue

            variants = group_value.get("variants")
            if not variants:
                continue

            for key in set(variants.keys()):
                if key in METADATA_KEYS:
                    continue

                variant_value = variants[key]
                if "environment" not in variant_value:
                    variants[key] = {
                        "environment": variant_value
                    }


def _project_anatomy_backwards_compatible_conversion(project_anatomy):
    # Backwards compatibility of node settings in Nuke 3.9.x - 3.10.0
    # - source PR - https://github.com/quadproduction/quadpype/pull/3143
    value = project_anatomy
    for key in ("imageio", "nuke", "nodes", "requiredNodes"):
        if key not in value:
            return
        value = value[key]

    for item in value:
        for node in item.get("knobs") or []:
            if "type" in node:
                break
            node["type"] = "__legacy__"


@require_settings_handler
def get_studio_global_settings_overrides(return_version=False):
    output = _SETTINGS_HANDLER.get_studio_global_settings_overrides(
        return_version
    )
    value = output
    if return_version:
        value, _ = output
    _global_settings_backwards_compatible_conversion(value)
    return output


@require_settings_handler
def get_studio_project_settings_overrides(return_version=False):
    return _SETTINGS_HANDLER.get_studio_project_settings_overrides(
        return_version
    )


@require_settings_handler
def get_studio_project_anatomy_overrides(return_version=False):
    return _SETTINGS_HANDLER.get_studio_project_anatomy_overrides(
        return_version
    )


@require_settings_handler
def get_project_settings_overrides(project_name, return_version=False):
    return _SETTINGS_HANDLER.get_project_settings_overrides(
        project_name, return_version
    )


@require_settings_handler
def get_project_anatomy_overrides(project_name):
    output = _SETTINGS_HANDLER.get_project_anatomy_overrides(project_name, return_version=False)
    _project_anatomy_backwards_compatible_conversion(output)
    return output


@require_settings_handler
def get_studio_global_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_global_settings_overrides_for_version(version)
    )


@require_settings_handler
def get_studio_project_anatomy_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_project_anatomy_overrides_for_version(version)
    )


@require_settings_handler
def get_studio_project_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_project_settings_overrides_for_version(version)
    )


@require_settings_handler
def get_project_settings_overrides_for_version(
    project_name, version
):
    return (
        _SETTINGS_HANDLER
        .get_project_settings_overrides_for_version(project_name, version)
    )


@require_settings_handler
def get_available_studio_global_settings_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_global_settings_overrides_versions(
            sorted=sorted
        )
    )


@require_settings_handler
def get_available_studio_project_anatomy_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_project_anatomy_overrides_versions(
            sorted=sorted
        )
    )


@require_settings_handler
def get_available_studio_project_settings_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_project_settings_overrides_versions(
            sorted=sorted
        )
    )


@require_settings_handler
def get_available_project_settings_overrides_versions(
    project_name, sorted=None
):
    return (
        _SETTINGS_HANDLER
        .get_available_project_settings_overrides_versions(
            project_name, sorted=sorted
        )
    )


@require_settings_handler
def find_closest_version_for_projects(project_names):
    return (
        _SETTINGS_HANDLER
        .find_closest_version_for_projects(project_names)
    )


@require_settings_handler
def clear_studio_global_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_global_settings_overrides_for_version(version)
    )


@require_settings_handler
def clear_studio_project_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_project_settings_overrides_for_version(version)
    )


@require_settings_handler
def clear_studio_project_anatomy_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_project_anatomy_overrides_for_version(version)
    )


@require_settings_handler
def clear_project_settings_overrides_for_version(
    version, project_name
):
    return _SETTINGS_HANDLER.clear_project_settings_overrides_for_version(
        version, project_name
    )


def reset_default_settings():
    """Reset cache of default settings. Can't be used now."""
    global _DEFAULT_SETTINGS
    _DEFAULT_SETTINGS = None


def _get_default_settings():
    from quadpype.modules import get_module_settings_defs

    defaults = load_quadpype_default_settings()

    module_settings_defs = get_module_settings_defs()
    for module_settings_def_cls in module_settings_defs:
        module_settings_def = module_settings_def_cls()
        global_defaults = module_settings_def.get_defaults(
            GLOBAL_SETTINGS_KEY
        ) or {}
        for path, value in global_defaults.items():
            if not path:
                continue

            subdict = defaults[GLOBAL_SETTINGS_KEY]
            path_items = list(path.split("/"))
            last_key = path_items.pop(-1)
            for key in path_items:
                subdict = subdict[key]
            subdict[last_key] = value

        project_defaults = module_settings_def.get_defaults(
            PROJECT_SETTINGS_KEY
        ) or {}
        for path, value in project_defaults.items():
            if not path:
                continue

            subdict = defaults
            path_items = list(path.split("/"))
            last_key = path_items.pop(-1)
            for key in path_items:
                subdict = subdict[key]
            subdict[last_key] = value

    return defaults


def get_default_settings():
    """Get default settings.

    Returns:
        dict: Loaded default settings.
    """
    global _DEFAULT_SETTINGS
    if _DEFAULT_SETTINGS is None:
        _DEFAULT_SETTINGS = _get_default_settings()
    return copy.deepcopy(_DEFAULT_SETTINGS)


def _apply_applications_settings_override(global_settings, user_settings):
    current_platform = platform.system().lower()
    apps_settings = global_settings[APPS_SETTINGS_KEY]
    additional_apps = apps_settings["additional_apps"]
    for app_group_name, value in user_settings[APPS_SETTINGS_KEY].items():
        if not value:
            continue

        if (
                app_group_name not in apps_settings
                and app_group_name not in additional_apps
        ):
            continue

        if app_group_name in apps_settings:
            variants = apps_settings[app_group_name]["variants"]

        else:
            variants = (
                apps_settings["additional_apps"][app_group_name]["variants"]
            )

        for app_name, app_value in value.items():
            if (
                    not app_value
                    or app_name not in variants
                    or "executables" not in variants[app_name]
            ):
                continue

            executable = app_value.get("executable")
            if not executable:
                continue
            platform_executables = variants[app_name]["executables"].get(
                current_platform
            )
            # TODO This is temporary fix until launch arguments will be stored
            #   per platform and not per executable.
            # - user settings store only executable
            new_executables = [executable]
            new_executables.extend(platform_executables)
            variants[app_name]["executables"] = new_executables


def _apply_modules_settings_override(global_settings, user_settings):
    modules_settings = global_settings[ADDONS_SETTINGS_KEY]
    for module_name, prop in user_settings[ADDONS_SETTINGS_KEY].items():
        modules_settings[module_name].update(prop)


def apply_user_settings_on_global_settings(global_settings, user_settings):
    """Apply user settings on studio global settings.

    ATM user settings can modify only application executables. Executable
    values are not overridden but prepended.
    """
    if not user_settings:
        return

    if APPS_SETTINGS_KEY in user_settings:
        _apply_applications_settings_override(global_settings, user_settings)

    if ADDONS_SETTINGS_KEY in user_settings:
        _apply_modules_settings_override(global_settings, user_settings)


def apply_user_settings_on_anatomy_settings(
    anatomy_settings, user_settings, project_name, site_name=None
):
    """Apply user settings on anatomy settings.

    ATM user settings can modify project roots. Project name is required as
    user settings have data stored data by project's name.

    User settings override root values in this order:
    1.) Check if user settings contain overrides for default project and
        apply its values on roots if there are any.
    2.) If passed `project_name` is not None then check project specific
        overrides in user settings for the project and apply its value on
        roots if there are any.

    NOTE: Root values of default project from user settings are always applied
        if are set.

    Args:
        anatomy_settings (dict): Data for anatomy settings.
        user_settings (dict): Data of user settings.
        project_name (str): Name of project for which anatomy data are.
        site_name (str): Name of the site
    """
    if not user_settings:
        return

    local_project_settings = user_settings.get(PROJECTS_SETTINGS_KEY) or {}

    # Check for roots existence in user settings first
    roots_project_locals = (
        local_project_settings
        .get(project_name, {})
    )
    roots_default_locals = (
        local_project_settings
        .get(DEFAULT_PROJECT_KEY, {})
    )

    # Skip rest of processing if roots are not set
    if not roots_project_locals and not roots_default_locals:
        return

    # Get active site from settings
    if site_name is None:
        if project_name:
            project_settings = get_project_settings(project_name)
        else:
            project_settings = get_default_project_settings()
        site_name = (
            project_settings["global"]["sync_server"]["config"]["active_site"]
        )

    # QUESTION should raise an exception?
    if not site_name:
        return

    # Combine roots from user settings
    roots_locals = roots_default_locals.get(site_name) or {}
    roots_locals.update(roots_project_locals.get(site_name) or {})
    # Skip processing if roots for current active site are not available in
    #   user settings
    if not roots_locals:
        return

    current_platform = platform.system().lower()

    root_data = anatomy_settings["roots"]
    for root_name, path in roots_locals.items():
        if root_name not in root_data:
            continue
        anatomy_settings["roots"][root_name][current_platform] = (
            path
        )


def get_site_local_overrides(project_name, site_name, user_settings=None):
    """Site overrides from user settings for passed project and site name.

    Args:
        project_name (str): For which project are overrides.
        site_name (str): For which site are overrides needed.
        user_settings (dict): Preloaded user settings. They are loaded
            automatically if not passed.
    """
    # Check if user settings were passed
    if user_settings is None:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()

    output = {}

    # Skip if user settings are empty
    if not user_settings:
        return output

    local_project_settings = user_settings.get(PROJECTS_SETTINGS_KEY) or {}

    # Prepare overrides for entered project and for default project
    project_locals = None
    if project_name:
        project_locals = local_project_settings.get(project_name)
    default_project_locals = local_project_settings.get(DEFAULT_PROJECT_KEY)

    # First load and use user settings from default project
    if default_project_locals and site_name in default_project_locals:
        output.update(default_project_locals[site_name])

    # Apply project specific user settings if there are any
    if project_locals and site_name in project_locals:
        output.update(project_locals[site_name])

    return output


def apply_user_settings_on_project_settings(
    project_settings, user_settings, project_name
):
    """Apply user settings on project settings.

    Currently, is modifying active site and remote site in sync server.

    Args:
        project_settings (dict): Data for project settings.
        user_settings (dict): Data of user settings.
        project_name (str): Name of project for which settings data are.
    """
    if not user_settings:
        return

    local_project_settings = user_settings.get(PROJECTS_SETTINGS_KEY)
    if not local_project_settings:
        return

    project_locals = local_project_settings.get(project_name) or {}
    default_locals = local_project_settings.get(DEFAULT_PROJECT_KEY) or {}
    active_site = (
        project_locals.get("active_site")
        or default_locals.get("active_site")
    )
    remote_site = (
        project_locals.get("remote_site")
        or default_locals.get("remote_site")
    )

    sync_server_config = project_settings["global"]["sync_server"]["config"]
    if active_site:
        sync_server_config["active_site"] = active_site

    if remote_site:
        sync_server_config["remote_site"] = remote_site


def get_global_settings(clear_metadata=True, exclude_locals=None):
    """Global settings with applied studio overrides."""
    default_values = get_default_settings()[GLOBAL_SETTINGS_KEY]
    studio_values = get_studio_global_settings_overrides()
    result = apply_overrides(default_values, studio_values)

    # Clear overrides metadata from settings
    if clear_metadata:
        clear_metadata_from_settings(result)

    # Apply user settings
    # Default behavior is based on `clear_metadata` value
    if exclude_locals is None:
        exclude_locals = not clear_metadata

    if not exclude_locals:
        # TODO user settings may be required to apply for environments
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        apply_user_settings_on_global_settings(result, user_settings)

    return result


def get_default_project_settings(clear_metadata=True, exclude_locals=None):
    """Project settings with applied studio's default project overrides."""
    default_values = get_default_settings()[PROJECT_SETTINGS_KEY]
    studio_values = get_studio_project_settings_overrides()
    result = apply_overrides(default_values, studio_values)
    # Clear overrides metadata from settings
    if clear_metadata:
        clear_metadata_from_settings(result)

    # Apply user settings
    if exclude_locals is None:
        exclude_locals = not clear_metadata

    if not exclude_locals:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        apply_user_settings_on_project_settings(
            result, user_settings, None
        )
    return result


def get_default_anatomy_settings(clear_metadata=True, exclude_locals=None):
    """Project anatomy data with applied studio's default project overrides."""
    default_values = get_default_settings()[PROJECT_ANATOMY_KEY]
    studio_values = get_studio_project_anatomy_overrides()

    result = apply_overrides(default_values, studio_values)
    # Clear overrides metadata from settings
    if clear_metadata:
        clear_metadata_from_settings(result)

    # Apply user settings
    if exclude_locals is None:
        exclude_locals = not clear_metadata

    if not exclude_locals:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        apply_user_settings_on_anatomy_settings(
            result, user_settings, None
        )
    return result


def get_anatomy_settings(
    project_name, site_name=None, clear_metadata=True, exclude_locals=None
):
    """Project anatomy data with applied studio and project overrides."""
    if not project_name:
        raise ValueError(
            "Must enter project name. Call "
            "`get_default_anatomy_settings` to get project defaults."
        )

    studio_overrides = get_default_anatomy_settings(False)
    project_overrides = get_project_anatomy_overrides(
        project_name
    )
    result = copy.deepcopy(studio_overrides)
    if project_overrides:
        for key, value in project_overrides.items():
            result[key] = value

    # Clear overrides metadata from settings
    if clear_metadata:
        clear_metadata_from_settings(result)

    # Apply user settings
    if exclude_locals is None:
        exclude_locals = not clear_metadata

    if not exclude_locals:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        apply_user_settings_on_anatomy_settings(
            result, user_settings, project_name, site_name
        )

    return result


def _get_project_settings(
    project_name, clear_metadata=True, exclude_locals=None
):
    """Project settings with applied studio and project overrides."""
    if not project_name:
        raise ValueError(
            "Must enter project name."
            " Call `get_default_project_settings` to get project defaults."
        )

    studio_overrides = get_default_project_settings(False)
    project_overrides = get_project_settings_overrides(
        project_name
    )

    result = apply_overrides(studio_overrides, project_overrides)

    # Clear overrides metadata from settings
    if clear_metadata:
        clear_metadata_from_settings(result)

    # Apply user settings
    if exclude_locals is None:
        exclude_locals = not clear_metadata

    if not exclude_locals:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        apply_user_settings_on_project_settings(
            result, user_settings, project_name
        )

    return result


def get_current_project_settings():
    """Project settings for current context project.

    Project name should be stored in environment variable `AVALON_PROJECT`.
    This function should be used only in host context where environment
    variable must be set and should not happen that any part of process will
    change the value of the environment variable.
    """
    project_name = os.getenv("AVALON_PROJECT")
    if not project_name:
        raise ValueError(
            "Missing context project in environment variable `AVALON_PROJECT`."
        )
    return get_project_settings(project_name)


@require_settings_handler
def _get_core_settings():
    default_settings = load_quadpype_default_settings()
    default_values = default_settings[GLOBAL_SETTINGS_KEY][CORE_SETTINGS_KEY]
    studio_values = _SETTINGS_HANDLER.get_core_settings()
    return {
        key: studio_values.get(key, default_values.get(key))
        for key in CORE_KEYS
    }


def get_core_settings():
    return _get_core_settings()


def _get_general_environments():
    """Get general environments.

    Function is implemented to be able to load general environments without using
    `get_default_settings`.
    """
    # Use only QuadPype defaults.
    # - prevent to use `get_global_settings` where `get_default_settings`
    #   is used
    default_values = load_quadpype_default_settings()
    global_settings = default_values[GLOBAL_SETTINGS_KEY]
    studio_overrides = get_studio_global_settings_overrides()

    result = apply_overrides(global_settings, studio_overrides)
    environments = result[CORE_SETTINGS_KEY]["environment"]

    clear_metadata_from_settings(environments)

    whitelist_envs = result[CORE_SETTINGS_KEY].get("local_env_white_list")
    if whitelist_envs:
        from quadpype.lib import get_user_settings
        user_settings = get_user_settings()
        local_envs = user_settings.get(ENV_SETTINGS_KEY) or {}
        for key, value in local_envs.items():
            if key in whitelist_envs and key in environments:
                environments[key] = value

    return environments


def get_general_environments():
    return _get_general_environments()


def get_project_settings(project_name, *args, **kwargs):
    return _get_project_settings(project_name, *args, **kwargs)


###############################################################################
# The following function doesn't require database or settings handler(s) to run
# This is needed for the bootstrapping process
###############################################################################


def load_json_file(filepath):
    # Load json data
    try:
        with open(filepath, "r") as opened_file:
            return json.load(opened_file)
    except JSON_EXC:
        raise IOError("File has invalid json format \"{}\"".format(filepath))


def load_jsons_from_dir(path, *args, **kwargs):
    """Load all .json files with content from entered folder path.

    Data are loaded recursively from a directory and recreate the
    hierarchy as a dictionary.

    Entered path hierarchy:
    |_ folder1
    | |_ data1.json
    |_ folder2
      |_ subfolder1
        |_ data2.json

    Will result in:
    ```javascript
    {
        "folder1": {
            "data1": "CONTENT OF FILE"
        },
        "folder2": {
            "subfolder1": {
                "data2": "CONTENT OF FILE"
            }
        }
    }
    ```

    Args:
        path (str): Path to the root folder where the json hierarchy starts.

    Returns:
        dict: Loaded data.
    """
    output = {}

    path = os.path.normpath(path)
    if not os.path.exists(path):
        # TODO warning
        return output

    sub_keys = list(kwargs.pop("subkeys", args))
    for sub_key in tuple(sub_keys):
        _path = os.path.join(path, sub_key)
        if not os.path.exists(_path):
            break

        path = _path
        sub_keys.pop(0)

    base_len = len(path) + 1
    for base, _directories, filenames in os.walk(path):
        base_items_str = base[base_len:]
        if not base_items_str:
            base_items = []
        else:
            base_items = base_items_str.split(os.path.sep)

        for filename in filenames:
            basename, ext = os.path.splitext(filename)
            if ext == ".json":
                full_path = os.path.join(base, filename)
                value = load_json_file(full_path)
                dict_keys = base_items + [basename]
                output = subkey_merge(output, value, dict_keys)

    for sub_key in sub_keys:
        output = output[sub_key]
    return output


def subkey_merge(_dict, value, keys):
    key = keys.pop(0)
    if not keys:
        _dict[key] = value
        return _dict

    if key not in _dict:
        _dict[key] = {}
    _dict[key] = subkey_merge(_dict[key], value, keys)

    return _dict


def load_quadpype_default_settings():
    """Load QuadPype default settings."""
    return load_jsons_from_dir(DEFAULTS_DIR)


def clear_metadata_from_settings(values):
    """Remove all metadata keys from loaded settings."""
    if isinstance(values, dict):
        for key in tuple(values.keys()):
            if key in METADATA_KEYS:
                values.pop(key)
            else:
                clear_metadata_from_settings(values[key])
    elif isinstance(values, list):
        for item in values:
            clear_metadata_from_settings(item)


def should_add_certificate_path_to_mongo_url(mongo_url):
    """Check if we should add ca certificate to mongo url.

    Since 30.9.2021 cloud mongo requires newer certificates that are not
    available on most of the workstations. This adds path to certifi certificate
    which is valid for it. To add the certificate path url must have scheme
    'mongodb+srv' or has 'ssl=true' or 'tls=true' in url query.
    """
    parsed = urlparse(mongo_url)
    query = parse_qs(parsed.query)
    lowered_query_keys = set(key.lower() for key in query.keys())
    add_certificate = False
    # Check if url 'ssl' or 'tls' are set to 'true'
    for key in ("ssl", "tls"):
        if key in query and "true" in query[key]:
            add_certificate = True
            break

    # Check if url contains 'mongodb+srv'
    if not add_certificate and parsed.scheme == "mongodb+srv":
        add_certificate = True

    # Check if url does already contain certificate path
    if add_certificate and "tlscafile" in lowered_query_keys:
        add_certificate = False
    return add_certificate


def get_versions_order_doc(collection, projection=None):
    return collection.find_one(
        { "type": DATABASE_VERSIONS_ORDER },
        projection
    ) or {}


def check_version_order(collection, version_str):
    """Create/update mongo document where QuadPype versions are stored
    in semantic version order.

    This document can be then used to find closes version of settings in
    processes where 'PackageVersion' is not available.
    """

    # Query document holding sorted list of version strings
    doc = get_versions_order_doc(collection)
    if not doc:
        doc = { "type": DATABASE_VERSIONS_ORDER }

    if DATABASE_ALL_VERSIONS_KEY not in doc:
        doc[DATABASE_ALL_VERSIONS_KEY] = []

    # Skip if current version is already available
    if version_str in doc[DATABASE_ALL_VERSIONS_KEY]:
        return

    if version_str not in doc[DATABASE_ALL_VERSIONS_KEY]:
        # Add all versions into list
        all_objected_versions = [
            VersionInfo.parse(version=version_str)
        ]
        for version_str in doc[DATABASE_ALL_VERSIONS_KEY]:
            all_objected_versions.append(
                VersionInfo.parse(version=version_str)
            )

        doc[DATABASE_ALL_VERSIONS_KEY] = [
            str(version) for version in sorted(all_objected_versions)
        ]

    collection.replace_one(
        { "type": DATABASE_VERSIONS_ORDER },
        doc,
        upsert=True
    )


def get_global_settings_overrides_for_version_doc(collection, version_str):
    return collection.find_one({ "type": DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY, "version": version_str })


def find_closest_settings_id(collection, version_str, key, legacy_key, additional_filters=None, versioned_doc=None):
    """Try to find closes available versioned settings for settings key.

    This method should be used only if settings for current QuadPype
    version are not available.

    Args:
        collection: MongoDB collection
        version_str: QuadPype version string
        key(str): Settings key under which are settings stored ("type").
        legacy_key(str): Settings key under which were stored not versioned
            settings.
        additional_filters(dict): Additional filters of document. Used
            for project specific settings.
        versioned_doc
    """
    # Trigger check of versions
    check_version_order(collection, version_str)

    doc_filters = {
        "type": {"$in": [key, legacy_key]}
    }
    if additional_filters:
        doc_filters.update(additional_filters)

    # Query base data of each settings doc
    other_versions = collection.find(
        doc_filters,
        {
            "_id": True,
            "version": True,
            "type": True
        }
    )
    # Query doc with list of sorted versions
    if versioned_doc is None:
        versioned_doc = get_versions_order_doc(collection)

    # Separate queried docs
    legacy_settings_doc = None
    versioned_settings_by_version = {}
    for doc in other_versions:
        if doc["type"] == legacy_key:
            legacy_settings_doc = doc
        elif doc["type"] == key:
            if doc["version"] == version_str:
                return doc["_id"]
            versioned_settings_by_version[doc["version"]] = doc

    versions_in_doc = versioned_doc.get(DATABASE_ALL_VERSIONS_KEY) or []
    # Cases when only legacy settings can be used
    if (
        # There are not versioned documents yet
        not versioned_settings_by_version
        # Versioned document is not available at all
        # - this can happen only if old build of QuadPype was used
        or not versioned_doc
        # Current QuadPype version is not available
        # - something went really wrong when this happens
        or version_str not in versions_in_doc
    ):
        if not legacy_settings_doc:
            return None
        return legacy_settings_doc["_id"]

    # Separate versions to lower and higher and keep their order
    lower_versions = []
    higher_versions = []
    before = True
    for curr_version_str in versions_in_doc:
        if curr_version_str == version_str:
            before = False
        elif before:
            lower_versions.append(curr_version_str)
        else:
            higher_versions.append(curr_version_str)

    # Use legacy settings doc as source document
    src_doc_id = None
    if legacy_settings_doc:
        src_doc_id = legacy_settings_doc["_id"]

    # Find the highest version which has available settings
    if lower_versions:
        for curr_version_str in reversed(lower_versions):
            doc = versioned_settings_by_version.get(curr_version_str)
            if doc:
                src_doc_id = doc["_id"]
                break

    # Use versions with higher version only if there are no legacy
    #   settings and there are not any versions before
    if src_doc_id is None and higher_versions:
        for curr_version_str in higher_versions:
            doc = versioned_settings_by_version.get(curr_version_str)
            if doc:
                src_doc_id = doc["_id"]
                break

    return src_doc_id


def find_closest_settings(collection, version_str, key, legacy_key, additional_filters=None, versioned_doc=None):
    doc_id = find_closest_settings_id(
        collection,
        version_str,
        key,
        legacy_key,
        additional_filters,
        versioned_doc
    )
    if doc_id is None:
        return None
    return collection.find_one({"_id": doc_id})


def find_closest_global_settings(collection, version_str):
    return find_closest_settings(
        collection,
        version_str,
        DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY,
        GLOBAL_SETTINGS_KEY
    )


def get_global_settings_overrides_doc(collection, version_str):
    document = get_global_settings_overrides_for_version_doc(collection, version_str)
    if document is None:
        document = find_closest_global_settings(collection, version_str)

    version = None
    if document and document["type"] == DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY:
            version = document["version"]

    return document, version


def merge_overrides(source_dict, override_dict):
    """Merge data from override_dict to source_dict."""

    if M_OVERRIDDEN_KEY in override_dict:
        overridden_keys = set(override_dict.pop(M_OVERRIDDEN_KEY))
    else:
        overridden_keys = set()

    for key, value in override_dict.items():
        if key in overridden_keys or key not in source_dict:
            source_dict[key] = value

        elif isinstance(value, dict) and isinstance(source_dict[key], dict):
            source_dict[key] = merge_overrides(source_dict[key], value)

        else:
            source_dict[key] = value
    return source_dict


def apply_overrides(source_data, override_data):
    if not override_data:
        return source_data
    _source_data = copy.deepcopy(source_data)
    return merge_overrides(_source_data, override_data)


def apply_core_settings(global_settings_document, core_document):
    """Apply core settings data to global settings.

    Application is skipped if document with core settings is not
    available or does not have set data in.

    Global settings document is "faked" like it exists if core document
    has set values.

    Args:
        global_settings_document (dict): Global settings document from
            MongoDB.
        core_document (dict): Core settings document from MongoDB.

    Returns:
        Merged document which has applied global settings data.
    """
    # Skip if core document is not available
    if (
        not core_document
        or "data" not in core_document
        or not core_document["data"]
    ):
        return global_settings_document

    core_data = core_document["data"]
    # Check if data contain any key from predefined keys
    any_key_found = False
    if core_data:
        for key in CORE_KEYS:
            if key in core_data:
                any_key_found = True
                break

    # Skip if any key from predefined key was not found in globals
    if not any_key_found:
        return global_settings_document

    # "Fake" global settings document if document does not exist
    # - global settings document may exist but global settings not yet
    if not global_settings_document:
        global_settings_document = {}

    if "data" in global_settings_document:
        global_settings_data = global_settings_document["data"]
    else:
        global_settings_data = {}
        global_settings_document["data"] = global_settings_data

    if CORE_SETTINGS_KEY in global_settings_data:
        global_core_data = global_settings_data[CORE_SETTINGS_KEY]
    else:
        global_core_data = {}
        global_settings_data[CORE_SETTINGS_KEY] = global_core_data

    overridden_keys = global_core_data.get(M_OVERRIDDEN_KEY) or []
    for key in CORE_KEYS:
        if key not in core_data:
            continue

        global_core_data[key] = core_data[key]
        if key not in overridden_keys:
            overridden_keys.append(key)

    if overridden_keys:
        global_core_data[M_OVERRIDDEN_KEY] = overridden_keys

    return global_settings_document


def get_core_settings_doc(collection):
    core_document = collection.find_one({
        "type": CORE_SETTINGS_DOC_KEY
    }) or {}
    return core_document


def get_global_settings_overrides_no_handler(collection, version_str):
    core_document = get_core_settings_doc(collection)

    document, version = get_global_settings_overrides_doc(
        collection,
        version_str
    )

    merged_doc = apply_core_settings(document, core_document)

    if merged_doc and "data" in merged_doc:
        return merged_doc["data"]
    return {}


def get_expected_studio_version_str(staging=False, collection=None):
    """Expected QuadPype version that should be used at the moment.

    If version is not defined in settings the latest found version is
    used.

    Using precached global settings is needed for usage inside QuadPype.

    Args:
        staging (bool): Staging version or production version.
        collection: Database collection.

    Returns:
        PackageVersion: Version that should be used.
    """
    database_url = os.getenv("QUADPYPE_MONGO")

    if not collection:
        kwargs = {}
        if should_add_certificate_path_to_mongo_url(database_url):
            kwargs["tlsCAFile"] = certifi.where()
        client = MongoClient(database_url, **kwargs)
        # Access settings collection
        quadpype_db_name = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
        collection = client[quadpype_db_name]["settings"]

    core_document = collection.find_one({"type": CORE_SETTINGS_DOC_KEY}) or {}

    key = "staging_version" if staging else "production_version"

    return core_document.get("data", {}).get(key, "")


def get_global_settings_and_version_no_handler(url: str, version_str: str) -> dict:
    """Load global settings from Mongo database.

    We are loading data from database `quadpype` and collection `settings`.
    There we expect document type `global_settings`.

    Args:
        url (str): MongoDB url.
        version_str (str): QuadPype version string.

    Returns:
        dict: With settings data. Empty dictionary is returned if not found.
        str: version string.
    """
    kwargs = {}
    if should_add_certificate_path_to_mongo_url(url):
        kwargs["tlsCAFile"] = certifi.where()

    # Create mongo connection
    client = MongoClient(url, **kwargs)
    # Access settings collection
    quadpype_db_name = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
    collection = client[quadpype_db_name]["settings"]

    default_values = load_quadpype_default_settings()[GLOBAL_SETTINGS_KEY]
    overrides_values = get_global_settings_overrides_no_handler(
        collection,
        version_str
    )

    result = apply_overrides(default_values, overrides_values)

    # Clear overrides metadata from settings
    clear_metadata_from_settings(result)
    # Close Mongo connection
    client.close()

    return result


def get_core_settings_no_handler(url: str) -> dict:
    kwargs = {}
    if should_add_certificate_path_to_mongo_url(url):
        kwargs["tlsCAFile"] = certifi.where()

    # Create mongo connection
    client = MongoClient(url, **kwargs)
    # Access settings collection
    quadpype_db_name = os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"
    collection = client[quadpype_db_name]["settings"]

    core_settings_doc = get_core_settings_doc(collection)

    # Close Mongo connection
    client.close()

    return core_settings_doc["data"] if "data" in core_settings_doc else {}


def get_quadpype_local_dir_path(settings: dict) -> Union[Path, None]:
    """Get QuadPype local path from global settings.

    Used to download and unzip QuadPype versions.
    Args:
        settings (dict): settings from DB.

    Returns:
        path to QuadPype or None if not found
    """
    path = (
        settings
        .get("local_versions_dir", {})
        .get(platform.system().lower())
    ) or None

    if path and isinstance(path, str):
        path = Path(path)

    return path if path else Path(user_data_dir("quadpype", "quad"))


def get_quadpype_remote_dir_paths(settings: dict) -> List[str]:
    """Get QuadPype path from global settings.

    Args:
        settings (dict): mongodb url.

    Returns:
        path to QuadPype or None if not found
    """
    paths = (
        settings
        .get("remote_versions_dirs", {})
        .get(platform.system().lower())
    ) or []
    # For cases when it's a single path
    if paths and isinstance(paths, str):
        paths = [paths]

    return paths if paths else []
