import pyblish.api
from quadpype.pipeline import (
    OptionalPyblishPluginMixin
)
from quadpype.pipeline.publish import PublishValidationError
from quadpype.settings import get_project_settings


class ValidateSyncServerModule(OptionalPyblishPluginMixin,
                         pyblish.api.ContextPlugin):

    """Containers are must be updated to latest version on publish."""

    label = "Validate Sync Server Module"
    order = pyblish.api.ValidatorOrder
    optional = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        project_name = context.data.get("projectName")
        project_settings = get_project_settings(project_name)

        sync_settings = project_settings["global"].get("sync_server", {})
        if not sync_settings["enabled"]:
            self.log.info("Sync Server is not enabled for this project.")
            return

        modules = context.data.get("quadpypeModules", {})
        sync_module = modules.get("sync_server")
        if not sync_module:
            raise PublishValidationError(self, "Sync Server Module is not available.")
        self.log.info("Sync Server Module is available at %s", sync_module)
