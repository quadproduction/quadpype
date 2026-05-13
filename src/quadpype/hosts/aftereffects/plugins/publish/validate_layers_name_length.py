import pyblish.api

from quadpype.pipeline.publish import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)

from quadpype.hosts.aftereffects.api import get_stub


class ValidateLayersNameLengthSelect(pyblish.api.Action):

    """Select the layers that have more than 31 characters"""

    label = "Select Layers"
    icon = "mouse-pointer"
    on = "failed"

    def process(self, context, plugin):
        data = context.data['transientData'][plugin.__name__]
        invalid_layers = data["layers"]
        comp_id = data["comp_id"]
        self.log.warning("Action triggered")
        stub = get_stub()
        stub.select_layers([layer['id'] for layer in invalid_layers], comp_id)
        self.log.warning("select_items called !")

        return True

class ValidateLayersNameLengthCutName(pyblish.api.Action):

    """Automatically rename the layer"""

    label = "Cut Layer Name"
    icon = "scissors"
    on = "failed"

    def process(self, context, plugin):
        data = context.data['transientData'][plugin.__name__]
        invalid_layers = data["layers"]
        comp_id = data["comp_id"]
        self.log.warning("Action triggered")
        stub = get_stub()

        for layer in invalid_layers:
            new_name = layer['name'][:31]
            layer_id = layer['id']
            stub.rename_layer(layer_id, comp_id, new_name)


class ValidateLayersNameLength(pyblish.api.InstancePlugin):


    order = pyblish.api.ValidatorOrder
    label = "Validate Layers Name Length"
    families = ["render.farm", "render.local", "render"]
    hosts = ["aftereffects"]
    actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    optional = True
    active = True

    def collect_invalid_layers(self, layers):
        invalid = []

        for layer in layers:
            if len(layer['name']) > 31:
                invalid.append(layer)
            if layer.get('layers'):
                invalid += self.collect_invalid_layers(layer['layers'])
        return invalid

    def process(self, instance):
        #if not self.is_active(instance.data):
            #return

        stub = get_stub()
        result = stub.get_comp_with_inner_layers(instance.data["comp_id"])
        self.log.warning(f"Result: {result}")

        invalid_layers = self.collect_invalid_layers(result[0]['layers'])
        self.log.warning(f"Invalid layers: {invalid_layers}")

        msg = "\n\nThe layers name are too long:"

        for layer in invalid_layers:
            msg += f"\n {layer['name']} ({len(layer['name'])}) characters."

        if invalid_layers:
            if not instance.context.data.get('transientData'):
                instance.context.data['transientData'] = dict()
            instance.context.data['transientData'][self.__class__.__name__] = {
                "layers": invalid_layers,
                "comp_id": instance.data["comp_id"]
            }
            detail_lines = [f"- {layer['name']}" for layer in invalid_layers]
            raise PublishXmlValidationError(self, msg, formatting_data={"layer_names": "<br/>".join(detail_lines)})
