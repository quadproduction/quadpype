from .module_importer import load_quadpype_module


settings_module = load_quadpype_module("quadpype/settings/lib.py", "quadpype.settings.lib")

should_add_certificate_path_to_mongo_url = settings_module.should_add_certificate_path_to_mongo_url
get_expected_studio_version_str = settings_module.get_expected_studio_version_str
#
# get_global_settings_and_version_no_handler = settings_module.get_global_settings_and_version_no_handler
get_quadpype_local_dir_path = settings_module.get_quadpype_local_dir_path
#
#
__all__ = [
    "should_add_certificate_path_to_mongo_url",

    "get_expected_studio_version_str",
    "get_quadpype_local_dir_path"
]
