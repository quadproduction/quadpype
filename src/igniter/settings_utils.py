from .module_importer import load_quadpype_module


settings_module = load_quadpype_module("quadpype/lib/settings.py", "quadpype.lib.settings")

get_expected_studio_version_str = settings_module.get_expected_studio_version_str
get_quadpype_global_settings = settings_module.get_quadpype_global_settings
get_local_quadpype_path = settings_module.get_local_quadpype_path
should_add_certificate_path_to_mongo_url = settings_module.should_add_certificate_path_to_mongo_url

__all__ = [
    "get_expected_studio_version_str",
    "get_quadpype_global_settings",
    "get_local_quadpype_path",
    "should_add_certificate_path_to_mongo_url"
]
