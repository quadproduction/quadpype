from quadpype.settings import get_project_settings
from quadpype.pipeline import context_tools

#---------------------------------------------------------------------------
#Load naming template
#---------------------------------------------------------------------------

def get_load_naming_template(setting_key, data):
    project_settings = get_project_settings(context_tools.get_current_project_name())

    # Get Entity Type Name Matcher Profiles
    try:
        template = (
            project_settings
            [context_tools.get_current_host_name()]
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
    project_settings = get_project_settings(context_tools.get_current_project_name())

    # Get Entity Type Name Matcher Profiles
    try:
        template = (
            project_settings
            [context_tools.get_current_host_name()]
            ["publish"]
            ["LoadedNamingFinder"]
            [setting_key]
        )

    except Exception:
        raise KeyError("Project has no template set for {}".format(setting_key))

    return template
