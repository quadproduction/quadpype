import re
import os
import unicodedata

import pyblish.api
from quadpype.hosts.tvpaint.api.lib import execute_george_through_file
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.settings import get_project_settings


CONVERSION_TABLE = {
    'Ã ': 'à',
    'Ã¡': 'á',
    'Ã¢': 'â',
    'Ã£': 'ã',
    'Ã¤': 'ä',
    'Ã¥': 'å',
    'Ã¦': 'æ',
    'Ã§': 'ç',
    'Ã¨': 'è',
    'Ã©': 'é',
    'Ãª': 'ê',
    'Ã«': 'ë',
    'Ã¬': 'ì',
    'Ã­': 'í',
    'Ã®': 'î',
    'Ã¯': 'ï',
    'Ã±': 'ñ',
    'Ã²': 'ò',
    'Ã³': 'ó',
    'Ã´': 'ô',
    'Ãµ': 'õ',
    'Ã¶': 'ö',
    'Ã¸': 'ø',
    'Å“': 'œ',
    'Ã¹': 'ù',
    'Ãº': 'ú',
    'Ã»': 'û',
    'Ã¼': 'ü',
    'Ã½': 'ý',
    'Ã¿': 'ÿ',
    'Ã€': 'À',
    'Ã,': 'Â',
    'Ãƒ': 'Ã',
    'Ã„': 'Ä',
    'Ã…': 'Å',
    'Ã†': 'Æ',
    'Ã‡': 'Ç',
    'Ãˆ': 'È',
    'Ã‰': 'É',
    'ÃŠ': 'Ê',
    'Ã‹': 'Ë',
    'ÃŒ': 'Ì',
    'ÃŽ': 'Î',
    'Ã‘': 'Ñ',
    'Ã’': 'Ò',
    'Ã“': 'Ó',
    'Ã”': 'Ô',
    'Ã•': 'Õ',
    'Ã–': 'Ö',
    'Ã˜': 'Ø',
    'Å’': 'Œ',
    'Ã™': 'Ù',
    'Ãš': 'Ú',
    'Ã›': 'Û',
    'Ãœ': 'Ü',
    'Å¸': 'Ÿ',
}


class ValidateNoSpecialCharRepair(pyblish.api.Action):
    """Rename layers with errors by adding legal character in front of names"""

    label = "Rename"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):
        layers_by_name = context.data.get("layersByName", None)
        assert layers_by_name, "Can not get layers in scene."

        george_script_lines = list()
        for layer_couple in context.data['transientData'][ValidateNoSpecialChar.__name__]:
            base_layer, renamed_layer_name = layer_couple

            old_layer_name = base_layer['name']
            base_layer['name'] = renamed_layer_name

            layers_by_name[renamed_layer_name] = [base_layer]
            del layers_by_name[old_layer_name]

            george_script_lines.append(
                "tv_layerrename {layer_id} '{layer_name}'".format(
                    layer_id=base_layer['layer_id'],
                    layer_name=renamed_layer_name
                )
            )

        george_script = "\n".join(george_script_lines)
        execute_george_through_file(george_script)

        return True


class ValidateNoSpecialChar(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin):
    """Validate if all the layers starts with a legal character"""

    label = "Validate No Special Character"
    order = pyblish.api.ValidatorOrder
    actions = [ValidateNoSpecialCharRepair]
    active = True

    def process(self, context):

        project_name = os.environ['AVALON_PROJECT']
        project_settings = get_project_settings(project_name)

        plugin_settings = project_settings['tvpaint']['publish'][self.__class__.__name__]

        enabled = plugin_settings['enabled']
        if not enabled:
            return

        convert_accents = plugin_settings['convert_accents']
        replace_chars = plugin_settings['replace_chars']

        if not convert_accents and not replace_chars:
            self.log.warning("At least one option needs to be enabled in order to validate layers names.")
            return

        if replace_chars:
            replace_chars = {
                target_char: replace_value['replace_by'] for target_char, replace_value in replace_chars.items()
            }

        layers_by_name = context.data.get("layersByName", None)
        assert layers_by_name, "Can not get layers in scene."

        layers_with_errors = list()
        for layer_name, layer_data in layers_by_name.items():
            layer_data = next(iter(layer_data))
            base_layer_name = layer_data['name']
            renamed_layer = base_layer_name

            if convert_accents:
                renamed_layer = re.sub(
                    '|'.join(re.escape(key) for key in CONVERSION_TABLE.keys()),
                    lambda c: CONVERSION_TABLE[c.group(0)], base_layer_name
                )

                layer_data['with_accents'] = renamed_layer
                renamed_layer = unicodedata.normalize('NFD', renamed_layer)
                renamed_layer = ''.join(char for char in renamed_layer if unicodedata.category(char) != 'Mn')

            if replace_chars:
                pattern = '[' + ''.join(re.escape(char) for char in replace_chars   .keys()) + ']'
                renamed_layer = re.sub(pattern, lambda m: replace_chars[m.group(0)], renamed_layer)

            if renamed_layer == base_layer_name:
                continue

            layers_with_errors.append((layer_data, renamed_layer))

        if layers_with_errors:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = layers_with_errors
            raise PublishXmlValidationError(
                self,
                "Groups and layers names can not have special characters in name :\n- {}.".format(
                    '\n- '.join([layer[0].get('with_accents', layer[0]['name']) for layer in layers_with_errors])
                )
            )
