from pyblish import api
from quadpype.settings import (
    get_current_project_settings,
    get_global_settings,
    PROJECT_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY
)


class CollectSettings(api.ContextPlugin):
    """Collect Settings and store in the context."""

    order = api.CollectorOrder - 0.491
    label = "Collect Settings"

    def process(self, context):
        context.data[PROJECT_SETTINGS_KEY] = get_current_project_settings()
        context.data[GLOBAL_SETTINGS_KEY] = get_global_settings()
