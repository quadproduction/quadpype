import pyblish.api
from quadpype.pipeline import PublishXmlValidationError
from quadpype.hosts.tvpaint.api.lib import execute_george

class ValidateLayersGroupSelect(pyblish.api.Action):
    """Select the layers in fault.
    """

    label = "Select Layers"
    icon = "briefcase"
    on = "failed"

    def process(self, context, plugin):
        """Select the layers that haven't a unique name"""

        for layer_index in context.data['transientData'][ValidateLayersGroup.__name__]:
            self.log.debug(execute_george(f'tv_layerselection {layer_index} "true"'))
        return True


class ValidateLayersGroup(pyblish.api.InstancePlugin):
    """Validate layer names for publishing are unique for whole workfile."""

    label = "Validate Duplicated Layers Names"
    order = pyblish.api.ValidatorOrder
    families = ["renderPass", "renderScene"]
    actions = [ValidateLayersGroupSelect]

    def process(self, instance):

        return_set = set()

        # Prepare layers
        layers_by_name = instance.context.data["layersByName"]

        # Layers ids of an instance
        layer_names = instance.data.get("layer_names", [])

        # Get the names in case of renderScene
        if not layer_names:
            layer_names = [layer["name"] for layer in instance.data.get("layers")]

        # Check if all layers from render pass are in right group
        duplicated_layer_names = set()
        for layer_name in layer_names:
            layers = layers_by_name.get(layer_name)
            # It is not job of this validator to handle missing layers
            if layers is None:
                continue
            if len(layers) > 1:
                duplicated_layer_names.add(layer_name)
                for layer in layers:
                    return_set.add(layer["layer_id"])

        # Everything is OK and skip exception
        if not duplicated_layer_names:
            return

        layers_msg = ",\n ".join(duplicated_layer_names)
        detail_lines = [
            "- {}".format(layer_name)
            for layer_name in set(duplicated_layer_names)
        ]

        if not instance.context.data.get('transientData'):
                instance.context.data['transientData'] = dict()

        instance.context.data['transientData'][self.__class__.__name__] = list(return_set)

        raise PublishXmlValidationError(
            self,
            (
                "Layers have duplicated names for instance {}."
                # Description what's wrong
                " There are layers with same name and one of them is marked"
                " for publishing so it is not possible to know which should"
                " be published. Please look for layers with names: {}"
            ).format(instance.data["label"], layers_msg),
            formatting_data={
                "layer_names": "<br/>".join(detail_lines)
            }
        )
