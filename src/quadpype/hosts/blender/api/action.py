import bpy

import pyblish.api

from quadpype.client import get_project, get_asset_by_name
from quadpype.pipeline.publish import get_errored_instances_from_context
from quadpype.hosts.blender.api.lib import set_id, generate_ids


class SelectInvalidAction(pyblish.api.Action):
    """Select invalid objects in Blender when a publish plug-in failed."""
    label = "Select Invalid"
    on = "failed"
    icon = "search"

    def process(self, context, plugin):
        errored_instances = get_errored_instances_from_context(
            context,
            plugin=plugin
        )

        # Get the invalid nodes for the plug-ins
        self.log.info("Finding invalid nodes...")
        invalid = list()
        for instance in errored_instances:
            invalid_nodes = plugin.get_invalid(instance)
            if invalid_nodes:
                if isinstance(invalid_nodes, (list, tuple)):
                    invalid.extend(invalid_nodes)
                else:
                    self.log.warning(
                        "Failed plug-in doesn't have any selectable objects."
                    )

        bpy.ops.object.select_all(action='DESELECT')

        # Make sure every node is only processed once
        invalid = list(set(invalid))
        if not invalid:
            self.log.info("No invalid nodes found.")
            return

        invalid_names = [obj.name for obj in invalid]
        self.log.info(
            "Selecting invalid objects: %s", ", ".join(invalid_names)
        )
        # Select the objects and also make the last one the active object.
        for obj in invalid:
            obj.select_set(True)

        bpy.context.view_layer.objects.active = invalid[-1]


class GenerateUUIDsOnInvalidAction(pyblish.api.Action):
    """Generate UUIDs on the invalid entities in the instance.

    Invalid entities are those returned by the plugin's `get_invalid` method.
    As such it is the plug-in's responsibility to ensure the nodes that
    receive new UUIDs are actually invalid.

    Requires:
        - instance.data["asset"]

    """

    label = "Regenerate UUIDs"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        self.log.info("Finding bad entities..")

        errored_instances = get_errored_instances_from_context(context)

        # Apply pyblish logic to get the instances for the plug-in
        instances = pyblish.api.instances_by_plugin(errored_instances, plugin)

        # Get the nodes from the all instances that ran through this plug-in
        all_invalid = []
        for instance in instances:
            invalid = plugin.get_invalid(instance)

            if invalid:
                self.log.info("Fixing instance {}".format(instance.name))
                self._update_id_attribute(instance, invalid)

                all_invalid.extend(invalid)

        if not all_invalid:
            self.log.info("No invalid entity found.")
            return

        all_invalid = list(set(all_invalid))
        self.log.info("Generated ids on entities: {0}".format(all_invalid))

    def _update_id_attribute(self, instance, entities):
        """Update id attribute

        Args:
            instance: The instance we're fixing for
            entities (list): all entities to regenerate ids on
        """

        # Expecting this is called on validators in which case 'assetEntity'
        #   should be always available, but kept a way to query it by name.
        asset_doc = instance.data.get("assetEntity")
        if not asset_doc:
            asset_name = instance.data["asset"]
            project_name = instance.context.data["projectName"]
            self.log.info((
                "Asset is not stored on instance."
                " Querying by name \"{}\" from project \"{}\""
            ).format(asset_name, project_name))
            asset_doc = get_asset_by_name(
                project_name, asset_name, fields=["_id"]
            )

        for entity, _id in generate_ids(entities, asset_id=asset_doc["_id"]):
            set_id(entity, _id, overwrite=True)
