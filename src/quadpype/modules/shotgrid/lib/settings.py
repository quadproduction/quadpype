from quadpype.settings import get_global_settings, get_project_settings, MODULES_SETTINGS_KEY
from quadpype.modules.shotgrid.lib.const import MODULE_NAME


def get_shotgrid_project_settings(project):
    return get_project_settings(project).get(MODULE_NAME, {})


def get_shotgrid_settings():
    return get_global_settings().get(MODULES_SETTINGS_KEY, {}).get(MODULE_NAME, {})


def get_shotgrid_servers():
    return get_shotgrid_settings().get("shotgrid_settings", {})


def get_leecher_backend_url():
    return get_shotgrid_settings().get("leecher_backend_url")
