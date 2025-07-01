import re

import pyblish.api
from quadpype.pipeline import PublishXmlValidationError, OptionalPyblishPluginMixin
from quadpype.hosts.tvpaint.api.lib import execute_george_through_file


START_NUMBER_PATTERN = r'^(\d+.+)$'
REPLACE_PATTERN = r'_\1'


class ValidateNamesStartWithLegalRepair(pyblish.api.Action):
    """Rename layers with errors by adding legal character in front of names"""

    label = "Repair"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):
        layers_with_errors = context.data['transientData'][ValidateNamesStartWithLegal.__name__]
        layers_by_name = context.data.get("layersByName", None)
        assert layers_by_name, "Can not get layers in scene."

        george_script_lines = list()
        for layer_data in layers_with_errors:
            if not layer_data:
                self.log.error(f"Can not retrieve layer named {layer_data['name']} from context data. Bypassing.")
                continue

            new_layer_name = re.sub(
                pattern=START_NUMBER_PATTERN,
                repl=REPLACE_PATTERN,
                string=layer_data['name']
            )

            old_layer_name = layer_data['name']
            layer_data['name'] = new_layer_name

            layers_by_name[new_layer_name] = [layer_data]
            del layers_by_name[old_layer_name]

            george_script_lines.append(
                "tv_layerrename {layer_id} '{layer_name}'".format(
                    layer_id=layer_data['layer_id'],
                    layer_name=new_layer_name
                )
            )

        george_script = "\n".join(george_script_lines)
        execute_george_through_file(george_script)


class ValidateNamesStartWithLegal(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin):
    """Validate if all the layers starts with a legal character"""

    label = "Validate Names Start With Legal"
    order = pyblish.api.ValidatorOrder
    families = ["renderPass", "renderScene"]
    actions = [ValidateNamesStartWithLegalRepair]
    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        layers_by_name = context.data.get("layersByName", None)
        assert layers_by_name, "Can not get layers in scene."

        layers_with_errors = list()
        for layer_name, layer_data in layers_by_name.items():
            layer_data = next(iter(layer_data))
            if re.search(START_NUMBER_PATTERN, layer_data["name"]):
                layers_with_errors.append(layer_data)

        if layers_with_errors:
            if not context.data.get('transientData'):
                context.data['transientData'] = dict()

            context.data['transientData'][self.__class__.__name__] = layers_with_errors

            raise PublishXmlValidationError(
                self,
                "Groups and layers names can not start with a number : {}.".format(
                    ', '.join([layer["name"] for layer in layers_with_errors])
                )
            )
