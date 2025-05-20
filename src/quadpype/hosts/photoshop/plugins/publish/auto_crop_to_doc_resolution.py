import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


class autoCropToDocResolution(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Crop all the layers to fit the doc resolution
    """

    label = "AutoCrop To Canva"
    hosts = ["photoshop"]
    order = pyblish.api.ExtractorOrder - 0.49
    families = ["image"]
    optional = True
    active = False

    def process(self, context):

        if not self.is_active(context.data):
            return

        stub = photoshop.stub()

        docResolution = stub.get_activeDocument_format_resolution()
        if not docResolution:
            return
        stub.crop_document_to_coordinate(0, 0, docResolution["width"], docResolution['height'])
