from quadpype.settings import get_project_settings
from quadpype.lib import filter_profiles
from quadpype.pipeline.context_tools import get_current_project_name, get_current_host_name


def _get_template(category, name, setting):
    project_settings = get_project_settings(get_current_project_name())
    try:
        template = (
            project_settings
            [get_current_host_name()]
            [category]
            [name]
            [setting]
        )

    except Exception:
        raise KeyError("Project has no template set for {}".format(setting))

    return template


def get_load_naming_template(setting_key):
    return _get_template(
        category="load",
        name="NamingTemplate",
        setting=setting_key,
    )


def get_loaded_naming_finder_template(setting_key):
    return _get_template(
        category="publish",
        name="LoadedNamingFinder",
        setting=setting_key
    )


def get_workfile_build_template(template_name):
    return _get_template(
        category="templated_workfile_build",
        name=template_name,
        setting="profiles"
    )


def get_task_hierarchy_templates(data, task=None):
    """Retrieve the template for the folders depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        task (str): fill to bypass task in data dict
    Return:
        str: A template that can be solved later
    """
    profiles = get_workfile_build_template("working_hierarchy_templates_by_tasks")
    profile_key = {
        "task_types": data["task"] if not task else task,
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)

    if not profile:
        return []

    return profile.get("templates", [])
