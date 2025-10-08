import os

import bpy

from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin, lib

NAME_SEPARATOR = ":"

class ExtractAnimationABC(
    plugin.BlenderExtractor,
    publish.OptionalPyblishPluginMixin,
):
    """Extract as ABC."""

    label = "Extract Animation ABC"
    hosts = ["blender"]
    families = ["animation"]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # Define extract output file path
        stagingdir = self.staging_dir(instance)
        creator_attributes = instance.data.get('creator_attributes', None)
        assert creator_attributes, "Can not retrieve creator attributes for instance. Abort process."
        apply_subdiv = creator_attributes.get("apply_subdiv", False)
        export_hidden = creator_attributes.get("export_hidden", False)

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
                if not child.visible_get() and not export_hidden:
                    continue
                if not child.visible_get() and export_hidden:
                    hidden_objects.append(child)
                    child.hide_set(False)
                    child.hide_viewport = False
                objects.append(child)

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
