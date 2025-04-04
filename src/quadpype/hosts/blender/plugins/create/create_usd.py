"""Create a USD Export."""

from quadpype.hosts.blender.api import plugin, lib

class CreateUSD(plugin.BlenderCreator):
    """Create USD Export"""

    identifier = "io.quadpype.creators.blender.usd"
    name = "usdMain"
    label = "USD"
    product_type = "usd"
    icon = "gears"

    def create(
        self, product_name: str, instance_data: dict, pre_create_data: dict
    ):
        # Run parent create method
        collection = super().create(
            product_name, instance_data, pre_create_data
        )

        if pre_create_data.get("use_selection"):
            objects = lib.get_selection()
            for obj in objects:
                collection.objects.link(obj)
                if obj.type == 'EMPTY':
                    objects.extend(obj.children)

        return collection
