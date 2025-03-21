"""Create a pointcache asset."""

from quadpype.hosts.blender.api import plugin, lib


class CreatePointcache(plugin.BlenderCreator):
    """Polygonal static geometry."""

    identifier = "io.quadpype.creators.blender.pointcache"
    label = "Point Cache"
    family = "pointcache"
    icon = "gears"

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )

        if pre_create_data.get("use_selection"):
            objects = lib.get_selection()
            for obj in objects:
                collection.objects.link(obj)
                if obj.type == 'EMPTY':
                    objects.extend(obj.children)

        return collection

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs(step=False)

        return defs
