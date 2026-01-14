"""Create review."""
import bpy

from quadpype.hosts.blender.api import plugin, lib
from quadpype.lib import EnumDef, BoolDef, UISeparatorDef
from quadpype.pipeline import get_current_project_name
from quadpype.settings import get_project_settings
from quadpype.pipeline.settings import get_available_resolutions, RES_SEPARATOR


class CreateReview(plugin.BlenderCreator):
    """Single baked camera."""

    identifier = "io.quadpype.creators.blender.review"
    label = "Review"
    family = "review"
    icon = "video-camera"

    resolution = None
    resolutions = []

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        if pre_create_data.get("resolution"):
            self.resolution = pre_create_data.get("resolution")

        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )

        if pre_create_data.get("use_selection"):
            selected = lib.get_selection()
            for obj in selected:
                collection.objects.link(obj)

        return collection

    def get_pre_create_attr_defs(self):
        output = []

        project_name = get_current_project_name()
        project_settings = get_project_settings(project_name)
        resolutions = get_available_resolutions(
            project_name=project_name,
            project_settings=project_settings
        )

        scene_resolution = (
            f"{bpy.context.scene.render.resolution_x}"
            f"{RES_SEPARATOR}"
            f"{bpy.context.scene.render.resolution_y}"
        )
        if scene_resolution not in resolutions:
            resolutions.append(scene_resolution)

        if resolutions:
            self.resolutions = resolutions
            output.append(
                EnumDef(
                    "resolution",
                    items=self.resolutions,
                    default=scene_resolution,
                    label="Resolution",
                )
            )

        return output

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
            ]
        )

        if self.resolutions:
            defs.append(
                EnumDef(
                    "resolution",
                    items=self.resolutions,
                    default=self.resolution,
                    label="Resolution",
                )
            )

        defs.extend(
            [
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
