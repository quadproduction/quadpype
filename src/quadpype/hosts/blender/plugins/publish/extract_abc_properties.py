import os
import json

import bpy
import pyblish.api
from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin, lib
from quadpype.lib import (
    BoolDef,
    TextDef,
    UISeparatorDef,
    UILabelDef,
)

NAME_SEPARATOR = ":"

class ExtractABCProperties(
    plugin.BlenderExtractor,
    publish.OptionalPyblishPluginMixin
):
    """Extract ABC properties in an json."""

    label = "Extract ABC properties"
    hosts = ["blender"]
    families = ["animation", "model"]
    order = pyblish.api.ExtractorOrder + 0.001
    applySubdiv = False
    visibleOnly = False

    attr = "id;"

    def process(self, instance):

        attr_values = self.get_attr_values_from_data(instance.data)
        properties_to_save = [
            attr.strip()
            for attr in attr_values.get("attr", "").split(";")
            if attr.strip()
        ]

        # Define extract output file path
        stagingdir = self.staging_dir(instance)
        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        filename = f"{instance_name}.json"
        filepath = os.path.join(stagingdir, filename)

        # Perform extraction
        self.log.info("Performing properties extraction..")

        props_data = {}
        renaming_object = dict()
        for obj in instance:
            if not isinstance(obj, bpy.types.Object):
                continue
            old_name = obj.name
            new_name = obj.name.split(NAME_SEPARATOR)[-1]
            renaming_object[new_name] = old_name
            obj.name = new_name
            props_data[obj.name] = {k: v for k, v in obj.items() if not k.startswith("_") and k in properties_to_save}


        with open(filepath, "w") as f:
            json.dump(props_data, f, indent=2)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'json',
            'ext': 'json',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        for new_name, old_name in renaming_object.items():
            self.log.info(f"{new_name} renamed to {old_name}")
            obj = bpy.data.objects.get(new_name)
            if not obj:
                continue
            obj.name = old_name

        self.log.info("Extracted instance '%s' to: %s",
                       instance.name, representation)

    @classmethod
    def get_attribute_defs(cls):

        override_defs = {
            "attr": {
                "def": TextDef,
                "kwargs": {
                    "label": "Custom Attributes",
                    "placeholder": "attr1; attr2; ...",
                }
            },
            "attrPrefix": {
                "def": TextDef,
                "kwargs": {
                    "label": "Custom Attributes Prefix",
                    "placeholder": "prefix1; prefix2; ...",
                }
            }
        }

        defs = super().get_attribute_defs()

        defs.extend([
            UISeparatorDef("sep_alembic_options"),
            UILabelDef("Alembic Properties Export")
        ])
        for key, value in override_defs.items():
            kwargs = value["kwargs"]
            kwargs["default"] = getattr(cls, key, None)
            defs.append(
                value["def"](key, **value["kwargs"])
            )
        defs.append(
            UISeparatorDef()
        )
        return defs
