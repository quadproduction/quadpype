import pyblish.api
from quadpype.pipeline.publish import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.tvpaint.api.lib import execute_george

class ValidateLayersNameLengthSelect(pyblish.api.Action):
    """Select the layers that names are too long"""

    label = "Select Layers"
    icon = "mouse-pointer"
    on = "failed"


    def process(self, context, plugin):

        select_dict = context.data['transientData'][plugin.__name__]

        for layer_id in select_dict.values():
            self.log.debug(execute_george(f'tv_layerselection {layer_id} "true"'))
        return True

class ValidateLayersNameLengthCutName(pyblish.api.Action):
    """Automatically rename the layer"""

    label = "Cut Layer Name"
    icon = "scissors"
    on = "failed"

    def process(self, context, plugin):

        select_dict = context.data['transientData'][plugin.__name__]

        for layer_name, layer_id in select_dict.items():
            layer_name = layer_name[:31]
            execute_george(f"tv_layerrename {layer_id} \"{layer_name}\"")


class ValidateLayersNameLength(
        OptionalPyblishPluginMixin,
        pyblish.api.InstancePlugin
    ):

    label = "Validate Layers Name Length"
    hosts = ["tvpaint"]
    families = ["render"]
    order = pyblish.api.ValidatorOrder
    actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    optional = True
    active = True

    def process(self, instance):

        layers_by_name = instance.context.data.get("layersByName", [])

        return_dict = {layer_name: layer_data[0]["layer_id"] for layer_name, layer_data in layers_by_name.items() if len(layer_name) > 31}

        if not return_dict:
            self.log.info("good")
            return

        msg = "\n\nThe layers name are too long:"

        for layer_name in return_dict.keys():
            msg += f"\n- {layer_name} ({len(layer_name)} characters)."

        if not instance.context.data.get('transientData'):
            instance.context.data['transientData'] = dict()
        instance.context.data['transientData'][self.__class__.__name__] = return_dict
        raise PublishXmlValidationError(self, msg)
