from quadpype.settings import get_project_settings
from quadpype.lib import filter_profiles
from quadpype.pipeline.context_tools import (
    get_current_project_name,
    get_current_host_name
)

def get_create_build_template():
    project_settings = get_project_settings(get_current_project_name())
    try:
        profiles = (
            project_settings
            [get_current_host_name()]
            ["create"]
            ["create_hierarchy_templates_by_family"]
            ["profiles"]
        )

    except Exception:
        raise KeyError("Project has no template set for create_hierarchy_templates_by_family")

    return profiles

def get_family_hierarchy_templates(data):
    """Retrieve the template for the folders depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
    Return:
        str: A template that can be solved later
    """
    profiles = get_create_build_template()
    profile_key = {
        "families": data.get("family")
    }

    profile = filter_profiles(profiles, profile_key)
    if not profile:
        raise KeyError("Project has no template set for {}".format(data.get("family")))

    return profile.get("templates", [])
