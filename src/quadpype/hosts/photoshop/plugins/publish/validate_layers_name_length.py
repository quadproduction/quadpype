import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


class ValidateLayersNameLengthSelect(pyblish.api.Action):
    """Select the layers that have more than configured characters numbers allowed"""

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

        project_settings = context.data.get("project_settings", {})
        max_number_characters = project_settings.get("global", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("max_number_characters", 31)

        stub = photoshop.stub()
        layers = context.data['transientData'][plugin.__name__]

        for layer in layers:
            new_name = layer.name[:max_number_characters]
            stub.rename_layer(layer.id, new_name)

class ValidateLayersNameLength(
        OptionalPyblishPluginMixin,
        pyblish.api.InstancePlugin
    ):
    """Validate the layer that have more than configured characters numbers allowed"""

    label = "Validate Layers Name Length"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    optional = True
    active = True

    def process(self, instance):
        project_settings = instance.context.data.get("project_settings", {})
        active = project_settings.get("global", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("active", True)

        if not active:
            return

        if not instance.data["creator_attributes"].get("export_psd", False):
            self.log.debug("ValidateLayersNameLength: 'export_psd' is False. Skipping validation.")
            return

        return_list = list()
        msg = f"\n\nThe layers names are too long:"

        stub = photoshop.stub()
        layers = stub.get_layers()
        max_number_characters = project_settings.get("global", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("max_number_characters", 31)

        for layer in layers:
            if len(layer.name) <= max_number_characters:
                continue

            return_list.append(layer)
            msg += f"\n- {layer.name}"

        if return_list:
            if not instance.context.data.get('transientData'):
                instance.context.data['transientData'] = dict()

            instance.context.data['transientData'][self.__class__.__name__] = return_list
            detail_lines = [f"- {layer.name}" for layer in return_list]
            formatting_data = {
                "layer_names": "<br/>".join(detail_lines),
                "max_number_characters": max_number_characters
            }
            raise PublishXmlValidationError(self, msg, formatting_data=formatting_data)
