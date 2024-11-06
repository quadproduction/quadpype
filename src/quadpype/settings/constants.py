import re


# Metadata keys for work with studio and project overrides
M_OVERRIDDEN_KEY = "__overriden_keys__"
# Metadata key for storing dynamic created labels
M_DYNAMIC_KEY_LABEL = "__dynamic_keys_labels__"

METADATA_KEYS = frozenset([
    M_OVERRIDDEN_KEY,
    M_DYNAMIC_KEY_LABEL
])

# Keys where studio's system overrides are stored
GLOBAL_SETTINGS_KEY = "global_settings"
PROJECT_SETTINGS_KEY = "project_settings"
PROJECT_ANATOMY_KEY = "project_anatomy"

CORE_SETTINGS_KEY = "core"
GENERAL_SETTINGS_KEY = "general"
ENV_SETTINGS_KEY = "environments"
APPS_SETTINGS_KEY = "applications"
MODULES_SETTINGS_KEY = "modules"
PROJECTS_SETTINGS_KEY = "projects"

# Schema hub names
SCHEMA_KEY_GLOBAL_SETTINGS = "global_schema"
SCHEMA_KEY_PROJECT_SETTINGS = "project_schema"

DEFAULT_PROJECT_KEY = "__default_project__"

KEY_ALLOWED_SYMBOLS = "a-zA-Z0-9-_ "
KEY_REGEX = re.compile(r"^[{}]+$".format(KEY_ALLOWED_SYMBOLS))


__all__ = (
    "M_OVERRIDDEN_KEY",
    "M_DYNAMIC_KEY_LABEL",

    "METADATA_KEYS",

    "CORE_SETTINGS_KEY",
    "GLOBAL_SETTINGS_KEY",
    "PROJECT_SETTINGS_KEY",
    "PROJECT_ANATOMY_KEY",

    "GENERAL_SETTINGS_KEY",
    "ENV_SETTINGS_KEY",
    "APPS_SETTINGS_KEY",
    "MODULES_SETTINGS_KEY",
    "PROJECTS_SETTINGS_KEY",

    "SCHEMA_KEY_GLOBAL_SETTINGS",
    "SCHEMA_KEY_PROJECT_SETTINGS",

    "DEFAULT_PROJECT_KEY",

    "KEY_ALLOWED_SYMBOLS",
    "KEY_REGEX"
)
