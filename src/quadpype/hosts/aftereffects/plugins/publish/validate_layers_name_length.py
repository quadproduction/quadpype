import pyblish.api

from quadpype.pipeline.publish import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)

from quadpype.hosts.aftereffects.api import get_stub


class ValidateLayersNameLengthSelect(pyblish.api.Action):

    """Select the layers that have more than configured characters numbers allowed"""

    label = "Select Layers"
    icon = "mouse-pointer"
    on = "failed"

    def process(self, context, plugin):
        data = context.data['transientData'][plugin.__name__]
        invalid_layers = data["layers"]
        self.log.warning(f"invalid_layers: {invalid_layers}")
        stub = get_stub()
        stub.select_layers([layer['id'] for layer in invalid_layers])

        return True

class ValidateLayersNameLengthCutName(pyblish.api.Action):

    """Automatically rename the layer"""

    label = "Cut Layer Name"
    icon = "scissors"
    on = "failed"

    def process(self, context, plugin):
        project_settings = context.data.get("project_settings", {})
        max_number_characters = project_settings.get("aftereffects", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("max_number_characters", 31)

        data = context.data['transientData'][plugin.__name__]
        invalid_layers = data["layers"]
        self.log.warning("Action triggered")
        stub = get_stub()

        for layer in invalid_layers:
            new_name = layer['name'][:max_number_characters]
            stub.rename_layer(layer['id'], new_name)


class ValidateLayersNameLength(pyblish.api.InstancePlugin):

    order = pyblish.api.ValidatorOrder
    label = "Validate Layers Name Length"
    families = ["render.farm", "render.local", "render"]
    hosts = ["aftereffects"]
    actions = [ValidateLayersNameLengthSelect, ValidateLayersNameLengthCutName]
    optional = True
    active = True
    extract_psd = True

    def collect_invalid_layers(self, layers, instance, parent_comp_id):
        project_settings = instance.context.data.get("project_settings", {})
        max_number_characters = project_settings.get("aftereffects", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("max_number_characters", 31)

        invalid = []

        for layer in layers:
            if len(layer['name']) > max_number_characters:
                layer['parent_comp_id'] = parent_comp_id
                invalid.append(layer)
            if layer.get('layers'):
                invalid += self.collect_invalid_layers(layer['layers'], instance, layer['id'])
        return invalid

    def process(self, instance):
        project_settings = instance.context.data.get("project_settings", {})
        active = project_settings.get("aftereffects", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("active", True)
        max_number_characters = project_settings.get("aftereffects", {}).get("publish", {}).get("ValidateLayersNameLength", {}).get("max_number_characters", 31)


        if not active:
            return

        if not instance.data["creator_attributes"].get("extract_psd", False):
            return

        stub = get_stub()
        result = stub.get_comp_with_inner_layers(instance.data["comp_id"])

        invalid_layers = self.collect_invalid_layers(result[0]['layers'], instance, instance.data["comp_id"])

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
            raise PublishXmlValidationError(self, msg, formatting_data={"layer_names": "<br/>".join(detail_lines), "max_number_characters": max_number_characters})
