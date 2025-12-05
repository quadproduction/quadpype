"""Create review."""

from quadpype.hosts.blender.api import plugin, lib
from quadpype.lib import EnumDef, BoolDef, UISeparatorDef


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
        defs.extend(
            [
                UISeparatorDef("render_pass_separator"),
                BoolDef(
                    "mark_for_review",
                    label="Review Publish on Tracker",
                    default=True
                ),
                UISeparatorDef(),
                EnumDef(
                    "render_view",
                    label="Render view",
                    items=["active camera", "camera in instance", "viewport"],
                    default="active camera"
                ),
                EnumDef(
                    "shader_mode",
                    label="Shader Mode",
                    items=["Viewport", "WIREFRAME", "SOLID", "MATERIAL"],
                    default="Viewport"
                ),
                BoolDef(
                    "render_overlay",
                    label="Render Overlay",
                    tooltip="Make image in background camera visible in review",
                    default=False
                ),
                BoolDef(
                    "render_floor_grid",
                    label="Render Floor Grid",
                    tooltip="Make the floor grid and axes visible in review",
                    default=False
                ),
                BoolDef(
                    "generate_image_sequence",
                    label="Generate Image Sequence",
                    tooltip="Generate image sequence",
                    default=True
                ),
                BoolDef(
                    "use_transparent_background",
                    label="Use transparent background",
                    default=True
                ),
            ]
        )

        return defs
