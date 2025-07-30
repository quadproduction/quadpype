import pyblish.api

from quadpype.hosts.photoshop import api as photoshop
from quadpype.tools.utils import host_tools

from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)


class ValidateSaveWorkfileRepair(pyblish.api.Action):
    """Save Workfile."""
    label = "Save Workfile"
    on = "failed"
    icon = "save"

    def process(self, context, plugin):
        host_tools.show_workfiles()
        return True


class ValidateSaveWorkfile(OptionalPyblishPluginMixin,
                           pyblish.api.ContextPlugin):
    """Validate if the file is saved before publishing
    """

    label = "Saved Workfile"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    optional = False
    actions = [ValidateSaveWorkfileRepair]

    def process(self, context):
        stub = photoshop.stub()
        msg = "The workfile has unsaved changes."

        if not self.is_active(context.data):
            return

        if not context.data["currentFile"]:
            msg = "The workfile has not been saved yet.\n Save the workfile before continuing."

            # File has not been saved at all and has no filename
            raise PublishXmlValidationError(self, msg,
                                            formatting_data={"msg": msg})

        if not stub.is_saved():
            raise PublishXmlValidationError(self, msg,
                                            formatting_data={"msg": msg})
