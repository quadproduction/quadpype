from .template_resolving_utils import get_profiles_by_key
from quadpype.lib import filter_profiles

def get_task_hierarchy_templates(data, task=None):
    """Retrieve the template for the folders depending on the task type
    Args:
        data (Dict[str, Any]): Data to fill template_collections_naming.
        task (str): fill to bypass task in data dict
    Return:
        str: A template that can be solved later
    """
    profiles = get_profiles_by_key("working_hierarchy_templates_by_tasks", data)
    profile_key = {
        "task_types": data["task"] if not task else task,
        "families": data["family"]
    }

    profile = filter_profiles(profiles, profile_key)

    if not profile:
        return []

    return profile.get("templates", [])


def split_hierarchy(hierarchy):
    """Split a str hierarchy to a list of individual name

    Args:
        hierarchy (str): a string template like "{parent}-{asset}<-{numbering}>/{asset}-model<-{variant}><-{numbering}>"
    Return:
        list: a list of separated template like ["{parent}-{asset}<-{numbering}>",
        "{asset}-model<-{variant}><-{numbering}>"]
    """

    return hierarchy.replace('\\', '/').split('/')
