from collections import OrderedDict

from quadpype.settings import get_project_settings
from quadpype.lib import (
    filter_profiles,
    Logger,
    StringTemplate,
)

def get_resolved_name(data, template):
    """Resolve template_collections_naming with entered data.
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        template (list): template to solve
    Returns:
        str: Resolved template
    """
    template_obj = StringTemplate(template)
    # Resolve the template
    output = template_obj.format_strict(data)
    if output:
        return output.normalized()
    return output

def _get_project_name_by_data(data):
    """
    Retrieve the project settings depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The project name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    is_from_anatomy = False
    if data.get("project"):
        return data["project"]["name"], is_from_anatomy
    if data.get("anatomyData"):
        is_from_anatomy = True
        return data["anatomyData"]["project"]["name"], is_from_anatomy

def _get_app_name_by_data(data):
    """
    Retrieve the project settings depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The app name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    is_from_anatomy = False
    if data.get("app"):
        return data["project"]["app"], is_from_anatomy
    if data.get("anatomyData"):
        is_from_anatomy = True
        return data["anatomyData"]["app"], is_from_anatomy

def _get_parent_by_data(data):
    """
    Retrieve the project settings depending on given data
    This can be given by an instance or an app, and they are not sorted the same way

    Return:
        str, bool: The parent name (str) and a bool to specify if this is from anatomy or project (bool)
    """
    is_from_anatomy = False
    if data.get("parent"):
        return data["parent"], is_from_anatomy
    if data.get("anatomyData"):
        is_from_anatomy = True
        return data["anatomyData"]["parent"], is_from_anatomy

def _get_profiles(setting_key, data, project_settings=None):

    if not project_settings:
        project_settings = get_project_settings(_get_project_name_by_data(data))

    # Get Entity Type Name Matcher Profiles
    try:
        profiles = (
            project_settings
            [_get_app_name_by_data(data)]
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
    # If a profile is found, return the prefix
    if profile.get("entity_prefix"):
        return profile["entity_prefix"], is_anatomy

    return None

def update_parent_data_with_entity_prefix(data):
    """
    Will update the input data dict to change the value of the ["parent"] key
    to become the corresponding prefix
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        dict: Data updated with new ["parent"] prefix
    """
    parent_prefix, is_anatomy = _get_entity_prefix(data)
    if parent_prefix and not is_anatomy:
        data["parent"] = parent_prefix
        return data

    if parent_prefix and is_anatomy:
        data["anatomyData"]["parent"] = parent_prefix
        return data

def get_entity_collection_template(data):
    """Retrieve the template for the collection depending on the entity type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        str: A template that can be solved later
    """

    # Get Entity Type Name Matcher Profiles
    profiles = _get_profiles("collections_templates_by_entity_type", data)
    parent, is_anatomy = _get_parent_by_data(data)
    profile_key = {"entity_types": parent}
    profile = filter_profiles(profiles, profile_key)
    # If a profile is found, return the template
    if profile.get("template"):
        return profile["template"]

    return None

def get_task_collection_template(data):
    """Retrieve the template for the collection depending on the entity type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        str: A template that can be solved later
    """

    # Get Entity Type Name Matcher Profiles
    profiles = _get_profiles("working_collections_templates_by_tasks", data)
    profile_key = {"task_types": data["task"]}
    profile = filter_profiles(profiles, profile_key)

    # If a profile is found, return the template
    if profile and data.get("variant", None) == "Main":
            return profile["main_template"]

    if profile and data.get("variant", None) != "Main":
            return profile["variant_template"]

    return None
