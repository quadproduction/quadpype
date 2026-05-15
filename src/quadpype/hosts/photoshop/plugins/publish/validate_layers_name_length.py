import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


class ValidateLayersNameLengthSelect(pyblish.api.Action):
    """Select the layers that have more than 31 characters"""

    label = "Select Layers"
    icon = "mouse-pointer"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        stub.select_layers(context.data['transientData'][plugin.__name__])

        return True

class ValidateLayersNameLengthCutName(pyblish.api.Action):
    """Automatically rename the layer"""

    label = "Cut Layer Name"
    icon = "scissors"
    on = "failed"

    def process(self, context, plugin):

        stub = photoshop.stub()
        layers = context.data['transientData'][plugin.__name__]

        for layer in layers:
            new_name = layer.name[:31]
            stub.rename_layer(layer.id, new_name)



class ValidateLayersNameLength(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate that layer names do not exceed 31 characters"""

    label = "Validate Layers Name Length"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    optional = True
    active = True

    def process(self, context):
        project_settings = context.data.get("project_settings", {})
        active = project_settings.get("global", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("active", True)

        if not active:
            return

        return_list = list()
        msg = f"\n\nThe layers name are too long:"

        stub = photoshop.stub()
        layers = stub.get_layers()

        for layer in layers:
            if len(layer.name) <= 31:
                continue

            return_list.append(layer)
            msg += f"\n- {layer.name}"

        if return_list:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = return_list
            detail_lines = [f"- {layer.name}" for layer in return_list]
            raise PublishXmlValidationError(self, msg, formatting_data={"layer_names": "<br/>".join(detail_lines)})
