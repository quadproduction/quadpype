from quadpype.settings import get_project_settings
from copy import deepcopy
from quadpype.lib import (
    filter_profiles,
    StringTemplate,
)
import warnings
from quadpype.hosts.blender.api import lib, pipeline

def get_resolved_name(data, template, **additional_data):
    """Resolve template_collections_naming with entered data.
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        template (str): template to solve
    Returns:
        str: Resolved template
    """
    template_obj = StringTemplate(template)

    if additional_data:
        data = dict(data, **additional_data)
    return template_obj.format_strict(data).normalized()

def set_data_for_template_from_original_data(original_data, filter_variant=True):
    """Format incoming data for template resolving"""
    data = deepcopy(original_data)

    if original_data.get("context"):
        data = deepcopy(original_data["context"])

    parent = pipeline.get_parent_data(data)
    if not parent:
        warnings.warn(f"Can not retrieve parent short from {data.get('parent', None)}", UserWarning)
    data["parent"] = parent
    data["app"] = "blender"

    update_parent_data_with_entity_prefix(data)

    if lib.is_shot():
        data['sequence'], data['shot'] = lib.extract_sequence_and_shot()
    if filter_variant:
        _filter_variant_data(data)
    return data

def _filter_variant_data(data):
    """Remove the variant from data if equel to DEFAULT_VARIANT_NAME"""
    if data.get("variant") == pipeline.DEFAULT_VARIANT_NAME:
        data.pop("variant")

def _get_project_name_by_data(data):
    """
    Retrieve the project name depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The project name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    project_name = None
    is_from_anatomy = False

    if data.get("project"):
        project_name = data["project"]["name"]
    elif data.get("anatomyData"):
        is_from_anatomy = True
        project_name = data["anatomyData"]["project"]["name"]

    return project_name, is_from_anatomy


def _get_app_name_by_data(data):
    """
    Retrieve the app name depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The app name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    app_name = None
    is_from_anatomy = False

    if data.get("app"):
        app_name = data["app"]
    elif data.get("anatomyData"):
        is_from_anatomy = True
        app_name = data["anatomyData"]["app"]

    return app_name, is_from_anatomy


def _get_parent_by_data(data):
    """
    Retrieve the parent asset name depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The parent name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    parent_name = None
    is_from_anatomy = False

    if data.get("parent"):
        parent_name = data["parent"]
    elif data.get("anatomyData"):
        is_from_anatomy = True
        parent_name = data["anatomyData"]["parent"]

    return parent_name, is_from_anatomy


def _get_profiles(setting_key, data, project_settings=None):

    project_name, is_anatomy_data = _get_project_name_by_data(data)
    app_name, is_anatomy_data = _get_app_name_by_data(data)

    if not project_settings:
        project_settings = get_project_settings(project_name)

    # Get Entity Type Name Matcher Profiles
    try:
        profiles = (
            project_settings
            [app_name]
            ["templated_workfile_build"]
            [setting_key]
            ["profiles"]
        )

    except Exception:
        raise KeyError("Project has no profiles set for {}".format(setting_key))

    # By default, profiles = [], so we must stop if there's no profiles set
    if not profiles:
        raise KeyError("Project has no profiles set for {}".format(setting_key))

    return profiles


def _get_entity_prefix(data):
    """Retrieve the asset_type (entity_type) short name for proper blender naming
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        str: A string corresponding to the short name for entered entity type
        bool: bool to specify if this is from anatomy or project (bool)
    """

    # Get Entity Type Name Matcher Profiles
    profiles = _get_profiles("entity_type_name_matcher", data)
    parent, is_anatomy = _get_parent_by_data(data)

    profile_key = {"entity_types": parent}
    profile = filter_profiles(profiles, profile_key)
    if not profile:
        return None, is_anatomy
    # If a profile is found, return the prefix
    return profile.get("entity_prefix"), is_anatomy


def update_parent_data_with_entity_prefix(data):
    """
    Will update the input data dict to change the value of the ["parent"] key
    to become the corresponding prefix
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    """
    parent_prefix, is_anatomy = _get_entity_prefix(data)

    if not parent_prefix:
        return None

    if is_anatomy:
        data["anatomyData"]["parent"] = parent_prefix
    else:
        data["parent"] = parent_prefix


def get_task_collection_templates(data, task=None):
    """Retrieve the template for the collection depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        task (str): fill to bypass task in data dict
    Return:
        str: A template that can be solved later
    """
    profiles = _get_profiles("working_collections_templates_by_tasks", data)
    profile_key = {
        "task_types": data["task"] if not task else task,
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)

    if not profile:
        return []

    return profile.get("templates", [])


#---------------------------------------------------------------------------
#Load naming template
#---------------------------------------------------------------------------

def get_load_naming_template(setting_key, data):
    project_name, is_anatomy_data = _get_project_name_by_data(data)
    app_name, is_anatomy_data = _get_app_name_by_data(data)
    project_settings = get_project_settings(project_name)

    # Get Entity Type Name Matcher Profiles
    try:
        template = (
            project_settings
            [app_name]
            ["load"]
            ["NamingTemplate"]
            [setting_key]
        )

    except Exception:
        raise KeyError("Project has no template set for {}".format(setting_key))

    return template

#---------------------------------------------------------------------------
#Publish loaded re-naming template
#---------------------------------------------------------------------------

def get_loaded_naming_finder_template(setting_key, data):
    project_name, is_anatomy_data = _get_project_name_by_data(data)
    app_name, is_anatomy_data = _get_app_name_by_data(data)
    project_settings = get_project_settings(project_name)

    # Get Entity Type Name Matcher Profiles
    try:
        template = (
            project_settings
            [app_name]
            ["publish"]
            ["LoadedNamingFinder"]
            [setting_key]
        )

    except Exception:
        raise KeyError("Project has no template set for {}".format(setting_key))

    return template
