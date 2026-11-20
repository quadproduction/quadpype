import pyblish.api
from quadpype.pipeline import (
    OptionalPyblishPluginMixin
)
from quadpype.pipeline.publish import PublishValidationError


class ValidateSyncServerModule(OptionalPyblishPluginMixin,
                         pyblish.api.ContextPlugin):

    """Containers are must be updated to latest version on publish."""

    label = "Validate Sync Server Module"
    order = pyblish.api.ValidatorOrder
    optional = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        self.log.info("Validating Sync Server Module")
        modules = context.data.get("quadpypeModules", {})
        sync_module = modules.get("sync_server")
        if not sync_module:
            raise PublishValidationError(self, "Sync Server Module is not available.")
        self.log.info("Sync Server Module is available at %s", sync_module)
