import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


class ValidateNoEmptyLayersRepair(pyblish.api.Action):
    """Select the layers that are empty"""

    label = "Select Layers"
    icon = "briefcase"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        stub.select_layers(layer for layer in context.data['transientData'][ValidateNoEmptyLayers.__name__])

        return True


class ValidateNoEmptyLayers(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate if no layers are empty"""

    label = "Validate No Empty Layers"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateNoEmptyLayersRepair]
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        return_list = list()
        msg = ""

        stub = photoshop.stub()
        layers = stub.get_layers()

        layers_ids = [layer.id for layer in layers if not layer.group]
        layers_by_ids = {layer.id: layer for layer in layers}

        empty_layers_dict = stub.are_layers_empty_by_ids(layers_ids)
        for layer_id in empty_layers_dict.keys():
            layer_by_id = layers_by_ids.get(layer_id)
            return_list.append(layer_by_id)
            msg = "{}\n\n The layer {} is not empty.".format(msg, layer_by_id.name)

        if return_list:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = return_list
            raise PublishXmlValidationError(self, msg)
