import pyblish.api
from quadpype.pipeline.publish import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.tvpaint.api.lib import execute_george

class ValidateLayersNameLengthSelect(pyblish.api.Action):
    """Select the layers that have more than configured characters numbers allowed"""

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

    def process(self, context, plugin, max_number_characters):
        select_dict = context.data['transientData'][plugin.__name__]

        for layer_name, layer_id in select_dict.items():
            layer_name = layer_name[:max_number_characters]
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

        project_settings = instance.context.data.get("project_settings", {})
        validate_layers_name_length_settings = project_settings.get("global", {}).get("publish", {}).get("ValidateLayersNameLength", {})
        active = validate_layers_name_length_settings.get("active", True)

        if not active:
            return

        if not instance.data["creator_attributes"].get("extract_psd", False):
            return

        max_number_characters = validate_layers_name_length_settings.get("max_number_characters", 31)

        layers_by_name = instance.context.data.get("layersByName", [])

        return_dict = {layer_name: layer_data[0]["layer_id"] for layer_name, layer_data in layers_by_name.items() if len(layer_name) > max_number_characters}

        if not return_dict:
            return

        msg = "\n\nThe layers names are too long:"

        for layer_name in return_dict.keys():
            msg += f"\n- {layer_name} ({len(layer_name)} characters)."

        if not instance.context.data.get('transientData'):
            instance.context.data['transientData'] = dict()
        instance.context.data['transientData'][self.__class__.__name__] = return_dict
        detail_lines = [f"- {layer_name}" for layer_name in return_dict.keys()]
        formatting_data = {
            "layer_names": "<br/>".join(detail_lines),
            "max_number_characters": max_number_characters
        }
        raise PublishXmlValidationError(self, msg, formatting_data=formatting_data)
