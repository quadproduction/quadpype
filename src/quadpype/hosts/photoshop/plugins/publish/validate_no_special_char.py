import re
import os
import unicodedata

import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.hosts.photoshop import api as photoshop
from quadpype.settings import get_project_settings


class ValidateNoSpecialCharRepair(pyblish.api.Action):
    """Rename layers with errors by adding legal character in front of names"""

    label = "Rename"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):
        stub = photoshop.stub()
        for layer_couple in context.data['transientData'][ValidateNoSpecialChar.__name__]:
            base_layer, renamed_layer_name = layer_couple
            stub.rename_layer(base_layer.id, renamed_layer_name)

        return True


class ValidateNoSpecialChar(
        OptionalPyblishPluginMixin,
        pyblish.api.ContextPlugin
    ):
    """Validate if no layer name contains special character"""

    label = "Validate No Special Character"
    hosts = ["photoshop"]
    order = ValidateContentsOrder
    families = ["image"]
    actions = [ValidateNoSpecialCharRepair]
    active = True

    def process(self, context):

        project_name = os.environ['AVALON_PROJECT']
        project_settings = get_project_settings(project_name)

        plugin_settings = project_settings['photoshop']['publish'][self.__class__.__name__]

        enabled = plugin_settings['enabled']
        if not enabled:
            return

        convert_accents = plugin_settings['convert_accents']
        replace_chars = plugin_settings['replace_chars']

        layers_with_errors = list()

        if not convert_accents and not replace_chars:
            self.log.warning("At least one option needs to be enabled in order to validate layers names.")

        if replace_chars:
            replace_chars = {
                target_char: replace_value['replace_by'] for target_char, replace_value in replace_chars.items()
            }

        for layer in photoshop.stub().get_layers():
            renamed_layer = layer.name
            if convert_accents:
                renamed_layer = unicodedata.normalize('NFD', layer.name)
                renamed_layer = ''.join(char for char in renamed_layer if unicodedata.category(char) != 'Mn')

            if replace_chars:
                pattern = '[' + ''.join(re.escape(char) for char in replace_chars.keys()) + ']'
                renamed_layer = re.sub(pattern, lambda m: replace_chars[m.group(0)], renamed_layer)

            if renamed_layer == layer.name:
                continue

            layers_with_errors.append((layer, renamed_layer))

        if layers_with_errors:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = layers_with_errors
            raise PublishXmlValidationError(
                self,
                "Groups and layers names can not have special characters in name :\n- {}.".format(
                    '\n- '.join([layer[0].name for layer in layers_with_errors])
                )
            )
