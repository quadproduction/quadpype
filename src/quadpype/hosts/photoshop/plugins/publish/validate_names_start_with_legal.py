import re

import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop


START_NUMBER_PATTERN = r'^(\d+.+)$'
REPLACE_PATTERN = r'_\1'


class ValidateNamesStartWithLegalRepair(pyblish.api.Action):
    """Rename layers with errors by adding legal character in front of names"""

    label = "Repair"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        for layer in context.data['transientData'][ValidateNamesStartWithLegal.__name__]:
            layer_name = re.sub(
                pattern=START_NUMBER_PATTERN,
                repl=REPLACE_PATTERN,
                string=layer.name
            )

            stub.rename_layer(layer.id, layer_name)

        return True


class ValidateNamesStartWithLegal(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate if all the layers starts with a legal character"""

    label = "Validate Names Start With Legal"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateNamesStartWithLegalRepair]
    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        msg = ""

        layers_with_errors = list()

        for layer in photoshop.stub().get_layers():
            if re.search(START_NUMBER_PATTERN, layer.name):
                layers_with_errors.append(layer)

        if layers_with_errors:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = layers_with_errors
            raise PublishXmlValidationError(
                self,
                "Groups and layers names can not start with a number : {}.".format(
                    ', '.join([layer.name for layer in layers_with_errors])
                )
            )
