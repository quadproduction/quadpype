import os
import json
import functools
import logging
import platform
import copy

from .exceptions import (
    SaveWarningExc
)
from .constants import (
    M_OVERRIDDEN_KEY,

    METADATA_KEYS,

    CORE_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY,
    PROJECT_SETTINGS_KEY,
    PROJECT_ANATOMY_KEY,
    DEFAULT_PROJECT_KEY,

    ENV_SETTINGS_KEY,
    APPS_SETTINGS_KEY,
    MODULES_SETTINGS_KEY,
    PROJECTS_SETTINGS_KEY
)


log = logging.getLogger(__name__)

# Py2 + Py3 json decode exception
JSON_EXC = getattr(json.decoder, "JSONDecodeError", ValueError)


# Path to default settings
DEFAULTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "defaults"
)

# Variable where cache of default settings are stored
_DEFAULT_SETTINGS = None

# Handler for studio overrides
_SETTINGS_HANDLER = None

# Handler for users
_USER_HANDLER = None


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
    # Handler can't be created in global space on initialization but only when
    # needed. Plus here may be logic: Which handler is used (in future).
    return MongoSettingsHandler()


def create_user_handler():
    from .handlers import MongoUserHandler
    return MongoUserHandler()


def require_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _SETTINGS_HANDLER
        if _SETTINGS_HANDLER is None:
            _SETTINGS_HANDLER = create_settings_handler()
        return func(*args, **kwargs)
    return wrapper


def require_user_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _USER_HANDLER
        if _USER_HANDLER is None:
            _USER_HANDLER = create_user_handler()
        return func(*args, **kwargs)
    return wrapper


@require_handler
def get_global_settings_last_saved_info():
    return _SETTINGS_HANDLER.get_global_settings_last_saved_info()


@require_handler
def get_project_settings_last_saved_info(project_name):
    return _SETTINGS_HANDLER.get_project_settings_last_saved_info(project_name)


@require_handler
def get_last_opened_info():
    return _SETTINGS_HANDLER.get_last_opened_info()


@require_handler
def opened_settings_ui():
    return _SETTINGS_HANDLER.opened_settings_ui()


@require_handler
def closed_settings_ui(info_obj):
    return _SETTINGS_HANDLER.closed_settings_ui(info_obj)


@require_handler
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
    # Notify Pype modules
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


@require_handler
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
    # Notify Pype modules
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


@require_handler
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
    # Notify Pype modules
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


@require_handler
def get_studio_global_settings_overrides(return_version=False):
    output = _SETTINGS_HANDLER.get_studio_global_settings_overrides(
        return_version
    )
    value = output
    if return_version:
        value, _ = output
    _global_settings_backwards_compatible_conversion(value)
    return output


@require_handler
def get_studio_project_settings_overrides(return_version=False):
    return _SETTINGS_HANDLER.get_studio_project_settings_overrides(
        return_version
    )


@require_handler
def get_studio_project_anatomy_overrides(return_version=False):
    return _SETTINGS_HANDLER.get_studio_project_anatomy_overrides(
        return_version
    )


@require_handler
def get_project_settings_overrides(project_name, return_version=False):
    return _SETTINGS_HANDLER.get_project_settings_overrides(
        project_name, return_version
    )


@require_handler
def get_project_anatomy_overrides(project_name):
    output = _SETTINGS_HANDLER.get_project_anatomy_overrides(project_name, return_version=False)
    _project_anatomy_backwards_compatible_conversion(output)
    return output


@require_handler
def get_studio_global_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_global_settings_overrides_for_version(version)
    )


@require_handler
def get_studio_project_anatomy_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_project_anatomy_overrides_for_version(version)
    )


@require_handler
def get_studio_project_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .get_studio_project_settings_overrides_for_version(version)
    )


@require_handler
def get_project_settings_overrides_for_version(
    project_name, version
):
    return (
        _SETTINGS_HANDLER
        .get_project_settings_overrides_for_version(project_name, version)
    )


@require_handler
def get_available_studio_global_settings_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_global_settings_overrides_versions(
            sorted=sorted
        )
    )


@require_handler
def get_available_studio_project_anatomy_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_project_anatomy_overrides_versions(
            sorted=sorted
        )
    )


@require_handler
def get_available_studio_project_settings_overrides_versions(sorted=None):
    return (
        _SETTINGS_HANDLER
        .get_available_studio_project_settings_overrides_versions(
            sorted=sorted
        )
    )


@require_handler
def get_available_project_settings_overrides_versions(
    project_name, sorted=None
):
    return (
        _SETTINGS_HANDLER
        .get_available_project_settings_overrides_versions(
            project_name, sorted=sorted
        )
    )


@require_handler
def find_closest_version_for_projects(project_names):
    return (
        _SETTINGS_HANDLER
        .find_closest_version_for_projects(project_names)
    )


@require_handler
def clear_studio_global_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_global_settings_overrides_for_version(version)
    )


@require_handler
def clear_studio_project_settings_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_project_settings_overrides_for_version(version)
    )


@require_handler
def clear_studio_project_anatomy_overrides_for_version(version):
    return (
        _SETTINGS_HANDLER
        .clear_studio_project_anatomy_overrides_for_version(version)
    )


@require_handler
def clear_project_settings_overrides_for_version(
    version, project_name
):
    return _SETTINGS_HANDLER.clear_project_settings_overrides_for_version(
        version, project_name
    )


@require_user_handler
def save_user_settings(data):
    return _USER_HANDLER.save_user_settings(data)


@require_user_handler
def get_user_settings():
    return _USER_HANDLER.get_user_settings()


@require_user_handler
def get_user_profile():
    return _USER_HANDLER.get_user_profile()


@require_user_handler
def update_user_profile_on_startup():
    return _USER_HANDLER.update_user_profile_on_startup()


def load_quadpype_default_settings():
    """Load quadpype default settings."""
    return load_jsons_from_dir(DEFAULTS_DIR)


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

    Todo:
        Cache loaded defaults.

    Returns:
        dict: Loaded default settings.
    """
    global _DEFAULT_SETTINGS
    if _DEFAULT_SETTINGS is None:
        _DEFAULT_SETTINGS = _get_default_settings()
    return copy.deepcopy(_DEFAULT_SETTINGS)


def load_json_file(fpath):
    # Load json data
    try:
        with open(fpath, "r") as opened_file:
            return json.load(opened_file)

    except JSON_EXC:
        log.warning(
            "File has invalid json format \"{}\"".format(fpath),
            exc_info=True
        )
    return {}


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
    modules_settings = global_settings[MODULES_SETTINGS_KEY]
    for module_name, property in user_settings[MODULES_SETTINGS_KEY].items():
        modules_settings[module_name].update(property)


def apply_user_settings_on_global_settings(global_settings, user_settings):
    """Apply user settings on studio global settings.

    ATM user settings can modify only application executables. Executable
    values are not overridden but prepended.
    """
    if not user_settings:
        return

    if APPS_SETTINGS_KEY in user_settings:
        _apply_applications_settings_override(global_settings, user_settings)

    if MODULES_SETTINGS_KEY in user_settings:
        _apply_modules_settings_override(global_settings, user_settings)


def apply_user_settings_on_anatomy_settings(
    anatomy_settings, user_settings, project_name, site_name=None
):
    """Apply user settings on anatomy settings.

    ATM user settings can modify project roots. Project name is required as
    user settings have data stored data by project's name.

    User settings override root values in this order:
    1.) Check if user settings contain overrides for default project and
        apply it's values on roots if there are any.
    2.) If passed `project_name` is not None then check project specific
        overrides in user settings for the project and apply it's value on
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

    Currently is modifying active site and remote site in sync server.

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


def _get_global_settings(clear_metadata=True, exclude_locals=None):
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


@require_handler
def _get_core_settings():
    default_settings = load_quadpype_default_settings()
    default_values = default_settings[GLOBAL_SETTINGS_KEY][CORE_SETTINGS_KEY]
    studio_values = _SETTINGS_HANDLER.get_core_settings()
    return {
        key: studio_values.get(key, default_values.get(key))
        for key in _SETTINGS_HANDLER.core_keys
    }


def get_core_settings():
    return _get_core_settings()


def _get_general_environments():
    """Get general environments.

    Function is implemented to be able to load general environments without using
    `get_default_settings`.
    """
    # Use only quadpype defaults.
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
        user_settings = get_user_settings()
        local_envs = user_settings.get(ENV_SETTINGS_KEY) or {}
        for key, value in local_envs.items():
            if key in whitelist_envs and key in environments:
                environments[key] = value

    return environments


def get_general_environments():
    return _get_general_environments()


def get_global_settings(*args, **kwargs):
    return _get_global_settings(*args, **kwargs)


def get_project_settings(project_name, *args, **kwargs):
    return _get_project_settings(project_name, *args, **kwargs)
