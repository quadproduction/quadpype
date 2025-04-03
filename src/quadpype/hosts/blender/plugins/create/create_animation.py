"""Create an animation asset."""
import logging

from quadpype.hosts.blender.api import plugin, lib, pipeline
from quadpype.pipeline.create import (
    subset_name,
    NamespaceNotSetError
)

class CreateAnimation(plugin.BlenderCreator):
    """Animation output for character rigs."""

    identifier = "io.quadpype.creators.blender.animation"
    label = "Animation"
    family = "animation"
    icon = "male"

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        container_selected = lib.get_selection(include_collections=True)
        data = pipeline.get_avalon_node(container_selected[0])
        if data:
            logging.info("Adding namespace data to instance")
            instance_data["namespace"] = data["namespace"]

        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )
        if pre_create_data.get("use_selection"):
            objects_selected = lib.get_selection()
            if data:
                objects_selected = pipeline.get_container_content(container_selected[0])
            for obj in objects_selected:
                collection.objects.link(obj)

        elif pre_create_data.get("asset_group"):
            # Use for Load Blend automated creation of animation instances
            # upon loading rig files
            obj = pre_create_data.get("asset_group")
            collection.objects.link(obj)

        return collection

    def get_subset_name(self,
        variant,
        task_name,
        asset_doc,
        project_name,
        instance=None,
        host_name=None
        ):
        """
        Get the selected avalon_instance loaded to retrieve the corresponding namespace
        Block the creation if something is not right
        """
        selected = lib.get_selection(include_collections=True)

        if not selected or len(selected) != 1:
            logging.info("No collection selected !\nOr more than one is selected")
            raise NamespaceNotSetError
        data = pipeline.get_avalon_node(selected[0])
        if not data:
            logging.info("The selected collection is not a loaded instance")
            raise NamespaceNotSetError

        dynamic_data = {"namespace":data["namespace"]}
        return subset_name.get_subset_name(
            self.family,
            variant,
            task_name,
            asset_doc,
            project_name,
            host_name,
            dynamic_data=dynamic_data,
            project_settings=self.project_settings
        )

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs(step=False)
        return defs
