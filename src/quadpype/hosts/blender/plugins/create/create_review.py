"""Create review."""

from quadpype.hosts.blender.api import plugin, lib


class CreateReview(plugin.BlenderCreator):
    """Single baked camera."""

    identifier = "io.quadpype.creators.blender.review"
    label = "Review"
    family = "review"
    icon = "video-camera"

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )

        if pre_create_data.get("use_selection"):
            selected = lib.get_selection()
            for obj in selected:
                collection.objects.link(obj)

        return collection

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs()

        return defs
