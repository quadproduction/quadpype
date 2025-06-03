import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop

class ValidateBlendModeSelect(pyblish.api.Action):
    """Select the layers that have incorrect blendmode"""

    label = "Select Layers"
    icon = "briefcase"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        failed = context.data['transientData'][ValidateBlendMode.__name__]
        stub.select_layers(info["layer_data"] for layer, info in failed.items())

        return True

class ValidateBlendModeRepair(pyblish.api.Action):
    """Repair the layers blendmode."""

    label = "Repair"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):

        stub = photoshop.stub()
        failed = context.data['transientData'][ValidateBlendMode.__name__]
        for layer, info in failed.items():
            stub.set_blendmode(layer_name=layer, blendMode_name=info["defaultBlendMode"])


class ValidateBlendMode(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate if the blendMode is set properly on Layers, NORMAL, and Groups, PASSTHROUGH
    """

    label = "Validate BlendMode"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateBlendModeRepair, ValidateBlendModeSelect]
    optional = True
    active = False

    def process(self, context):
        if not self.is_active(context.data):
            return

        PASSTHROUGH = "passThrough"
        NORMAL = "normal"
        returnDict =  {}
        msg = ""

        stub = photoshop.stub()
        layers = stub.get_layers()

        for layer in layers:
            layerDict = {}
            if (layer.group and layer.blendMode != PASSTHROUGH) or (not layer.group and layer.blendMode != NORMAL):
                layerDict["actualBlendMode"] = layer.blendMode
                layerDict["defaultBlendMode"] = PASSTHROUGH if layer.group else NORMAL
                layerDict["layer_data"] = layer
                returnDict[layer.name] = layerDict

                typeStr = "Group" if layer.group else "Layer"
                msg = "{}\n\n The {} {} is set to {}.".format(msg, typeStr, layer.name, layer.blendMode)

            else:
                continue

        if returnDict:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = returnDict

            raise PublishXmlValidationError(self, msg)
