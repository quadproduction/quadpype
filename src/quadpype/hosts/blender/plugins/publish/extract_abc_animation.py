import os

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

class ExtractAnimationABC(
    plugin.BlenderExtractor,
    publish.OptionalPyblishPluginMixin,
):
    """Extract as ABC."""

    label = "Extract Animation ABC"
    hosts = ["blender"]
    families = ["animation"]
    order = pyblish.api.ExtractorOrder + 0.001
    optional = True
    applySubdiv = False
    visibleOnly = False

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # Define extract output file path
        stagingdir = self.staging_dir(instance)

        attribute_values = self.get_attr_values_from_data(
            instance.data
        )

        apply_subdiv = attribute_values.get("applySubdiv", 1)
        visible_only = attribute_values.get("visibleOnly", 1)

        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        filename = f"{instance_name}.abc"

        filepath = os.path.join(stagingdir, filename)

        # Perform extraction
        self.log.info("Performing extraction..")

        plugin.deselect_all()

        selected = []
        asset_group = instance.data["transientData"]["instance_node"]

        objects = []
        hidden_objects = []
        for obj in instance:
            if isinstance(obj, bpy.types.Collection):
                for child in obj.all_objects:
                    objects.append(child)
        for obj in objects:
            children = [o for o in bpy.data.objects if o.parent == obj]
            for child in children:
                if not child.visible_get() and visible_only:
                    continue
                if not child.visible_get() and not visible_only:
                    hidden_objects.append(child)
                    child.hide_set(False)
                    child.hide_viewport = False
                objects.append(child)

        objects = list(set(objects))
        renaming_object = dict()
        for obj in objects:
            obj.select_set(True)
            selected.append(obj)

            old_name = obj.name
            new_name = obj.name.split(NAME_SEPARATOR)[-1]
            renaming_object[new_name] = old_name
            obj.name = new_name

            if apply_subdiv:
                continue

            modifiers = lib.get_cache_modifiers(obj, modifier_type="SUBSURF")
            for asset_name, modifier_list in modifiers.items():
                for modifier in modifier_list:
                    if modifier.type == "SUBSURF":
                        modifier.show_viewport = False
                        modifier.show_render = False

        context = plugin.create_blender_context(
            active=asset_group, selected=selected)

        with bpy.context.temp_override(**context):
            # We export the abc
            bpy.ops.wm.alembic_export(
                filepath=filepath,
                selected=True,
                flatten=False,
                apply_subdiv=apply_subdiv,
                start=instance.data["frameStartHandle"],
                end=instance.data["frameEndHandle"]
            )

        for obj in hidden_objects:
            obj.hide_set(True)
            obj.hide_viewport = True

        plugin.deselect_all()

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'abc',
            'ext': 'abc',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        for new_name, old_name in renaming_object.items():
            self.log.info(f"{new_name} renamed to {old_name}")
            obj = bpy.data.objects.get(new_name)
            obj.name = old_name
            if apply_subdiv:
                continue
            modifiers = lib.get_cache_modifiers(obj, modifier_type="SUBSURF")
            for asset_name, modifier_list in modifiers.items():
                for modifier in modifier_list:
                    if modifier.type == "SUBSURF":
                        modifier.show_viewport = True
                        modifier.show_render = True


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
            },
            "applySubdiv": {
                "def": BoolDef,
                "kwargs": {
                    "label": "Apply Subdiv",
                }
            },
            "visibleOnly": {
                "def": BoolDef,
                "kwargs": {
                    "label": "Visible Only",
                }
            }
        }
        defs = super(plugin.BlenderExtractor, cls).get_attribute_defs()

        defs.extend([
            UISeparatorDef("sep_alembic_options"),
            UILabelDef("Alembic Options"),
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
