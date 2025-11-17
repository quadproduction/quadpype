"""Create an animation asset."""
import logging
import bpy

from quadpype.lib import (
    EnumDef,
    BoolDef,
    UISeparatorDef
)

from quadpype.hosts.blender.api import plugin, lib, pipeline
from quadpype.client.mongo.entities import get_asset_by_name
from quadpype.pipeline.create import (
    subset_name,
    NamespaceNotSetError
)
from quadpype.client import get_representation_by_id


class CreateAnimation(plugin.BlenderCreator):
    """Animation output for character rigs."""

    identifier = "io.quadpype.creators.blender.animation"
    label = "Animation"
    family = "animation"
    icon = "male"

    variant = "Main"
    task_name = ""
    include_variant_in_name = False

    animatable_families = ["model", "rig", "pointcache"]

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        self.include_variant_in_name = pre_create_data.get("include_variant_in_name")

        containers_to_treat = []
        if pre_create_data.get("use_selection"):
            containers_to_treat = lib.get_containers_from_selected()

        if pre_create_data.get("animatable_container"):
            containers_to_treat = [bpy.data.collections.get(container_name) for container_name in
                                   pre_create_data.get("animatable_container")
                                   if bpy.data.collections.get(container_name)]

        if not containers_to_treat:
            return self._create_one(instance_data, subset_name, pre_create_data)

        for container in containers_to_treat:
            self._create_one(instance_data, subset_name, pre_create_data, container)
        return

    def _create_one(
        self, instance_data: dict, subset_name: str, pre_create_data: dict,
        containers_to_treat: bpy.types.Collection = None
    ):
        avalon_data = {}
        if containers_to_treat:
            avalon_data = pipeline.get_avalon_node(containers_to_treat)

            dynamic_data = {
                "namespace": avalon_data["namespace"],
                "asset": avalon_data["asset"],
                "family": avalon_data["family"],
            }

            asset_doc = get_asset_by_name(self.project_name, avalon_data["asset"])
            subset_name = self.get_subset_name(
                self.variant,
                self.task_name,
                asset_doc,
                self.project_name,
                instance=None,
                host_name=None,
                dynamic_data=dynamic_data,
                use_variant=self.include_variant_in_name
            )

            logging.info("Adding namespace data to instance")
            instance_data["namespace"] = avalon_data["namespace"]

        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )
        if not collection:
            return

        if pre_create_data.get("use_selection"):
            objects_selected = lib.get_selection()
            if avalon_data:
                objects_selected = pipeline.get_container_content(containers_to_treat)
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
        host_name=None,
        dynamic_data=None,
        containers_to_treat=None,
        use_variant=True
        ):
        """
        Generate a subset name based on container.
        """

        if not use_variant:
            variant = None

        self.variant = variant
        self.task_name = task_name

        data = {}

        if not containers_to_treat:
            containers_to_treat = lib.get_containers_from_selected()

        if not containers_to_treat:
            logging.info("No loaded container detected, will use selected element instead")

        else:
            data = pipeline.get_avalon_node(containers_to_treat[0])

        if not dynamic_data and data:
            dynamic_data = {
                "namespace": data.get("namespace", None),
                "asset": data["asset"],
                "family": data["family"],
            }


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

    def get_all_loaded_animatable_asset(self):
        avalon_container = bpy.data.collections.get(pipeline.AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=pipeline.AVALON_CONTAINERS)

        animatable_container = [
            col for col in avalon_container.children[:] if (
                    pipeline.has_avalon_node(col)and
                    pipeline.get_avalon_node(col).get("family") in self.animatable_families
            )
        ]

        return animatable_container

    def get_collection_enum_items(self, container):
        items = []
        collections_data = [pipeline.get_avalon_node(col) for col in container]
        for data in collections_data:
            representation = get_representation_by_id(
                self.project_name, data["representation"]
            )
            repre_name = ''
            if representation:
                repre_name = representation.get('name','')

            items.append((
                data["objectName"],
                f"{data.get('namespace', '')}-{data.get('task', '')} ({repre_name})"
            ))

        return items

    def get_pre_create_attr_defs(self):
        defs = super().get_pre_create_attr_defs()
        items = self.get_collection_enum_items(self.get_all_loaded_animatable_asset())
        items_defaults = [] if not items else [i[0] for i in items]
        if not items:
            items = [('', '')]

        defs.extend(
            [
                UISeparatorDef(),
                BoolDef(
                    "include_variant_in_name",
                    label="Include Variant in Instance Name",
                    default=self.include_variant_in_name
                ),
                EnumDef(
                    "animatable_container",
                    items=items,
                    default=items_defaults,
                    label="Assets to Publish",
                    multiselection=True
                )
            ]
        )
        return defs
