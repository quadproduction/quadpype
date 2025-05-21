import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


class ValidateLayersNameUniquenessRepair(pyblish.api.Action):
    """Select the layers that haven't a unique name"""

    label = "Select Layers"
    icon = "briefcase"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        stub.select_layers(layer for layer in context.data['transientData'][ValidateLayersNameUniqueness.__name__])

        return True


class ValidateLayersNameUniqueness(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate if all the layers have unique names"""

    label = "Validate Layers Name Uniqueness"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateLayersNameUniquenessRepair]
    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        return_list = list()
        msg = ""

        stub = photoshop.stub()
        layers = stub.get_layers()

        layer_list = [layer.name for layer in layers]
        duplicates = set()

        for layer in layers:
            if layer_list.count(layer.name) == 1:
                continue

            return_list.append(layer)
            if layer.name not in duplicates:
                duplicates.add(layer.name)
                msg = "{}\n\n The name {} is not unique.".format(msg, layer.name)

        if return_list:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = return_list
            raise PublishXmlValidationError(self, msg)
