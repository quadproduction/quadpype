import os
import re


DEFAULTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "defaults"
)

# Metadata keys for work with studio and project overrides
M_OVERRIDDEN_KEY = "__overriden_keys__"
# Metadata key for storing dynamic created labels
M_DYNAMIC_KEY_LABEL = "__dynamic_keys_labels__"

METADATA_KEYS = frozenset([
    M_OVERRIDDEN_KEY,
    M_DYNAMIC_KEY_LABEL
])

# Keys where studio's system overrides are stored
CORE_SETTINGS_DOC_KEY = "core_settings"
GLOBAL_SETTINGS_KEY = "global_settings"
PROJECT_SETTINGS_KEY = "project_settings"
PROJECT_ANATOMY_KEY = "project_anatomy"

CORE_SETTINGS_KEY = "core"
GENERAL_SETTINGS_KEY = "general"
ENV_SETTINGS_KEY = "environments"
APPS_SETTINGS_KEY = "applications"
ADDONS_SETTINGS_KEY = "addons"
PROJECTS_SETTINGS_KEY = "projects"

# Schema hub names
SCHEMA_KEY_GLOBAL_SETTINGS = "global_schema"
SCHEMA_KEY_PROJECT_SETTINGS = "project_schema"

DEFAULT_PROJECT_KEY = "__default_project__"

KEY_ALLOWED_SYMBOLS = "a-zA-Z0-9-_ "
KEY_REGEX = re.compile(r"^[{}]+$".format(KEY_ALLOWED_SYMBOLS))

# Database settings documents related constants
_DATABASE_SUFFIX = "_versioned"

DATABASE_ALL_VERSIONS_KEY = "all_versions"
DATABASE_VERSIONS_ORDER = "versions_order"
DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY = GLOBAL_SETTINGS_KEY + _DATABASE_SUFFIX
DATABASE_PROJECT_SETTINGS_VERSIONED_KEY = PROJECT_SETTINGS_KEY + _DATABASE_SUFFIX
DATABASE_PROJECT_ANATOMY_VERSIONED_KEY = PROJECT_ANATOMY_KEY + _DATABASE_SUFFIX


CORE_KEYS = {
    "remote_versions_dir",
    "local_versions_dir",
    "log_to_server",
    "disk_mapping",
    "production_version",
    "staging_version"
}

__all__ = (
    "DEFAULTS_DIR",
    "M_OVERRIDDEN_KEY",
    "M_DYNAMIC_KEY_LABEL",

    "METADATA_KEYS",

    "CORE_SETTINGS_DOC_KEY",
    "CORE_SETTINGS_KEY",
    "GLOBAL_SETTINGS_KEY",
    "PROJECT_SETTINGS_KEY",
    "PROJECT_ANATOMY_KEY",

    "GENERAL_SETTINGS_KEY",
    "ENV_SETTINGS_KEY",
    "APPS_SETTINGS_KEY",
    "ADDONS_SETTINGS_KEY",
    "PROJECTS_SETTINGS_KEY",

    "SCHEMA_KEY_GLOBAL_SETTINGS",
    "SCHEMA_KEY_PROJECT_SETTINGS",

    "DEFAULT_PROJECT_KEY",

    "KEY_ALLOWED_SYMBOLS",
    "KEY_REGEX",

    "DATABASE_ALL_VERSIONS_KEY",
    "DATABASE_VERSIONS_ORDER",
    "DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY",
    "DATABASE_PROJECT_SETTINGS_VERSIONED_KEY",
    "DATABASE_PROJECT_ANATOMY_VERSIONED_KEY",

    "CORE_KEYS"
)
