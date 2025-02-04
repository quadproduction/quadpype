import bpy
import inspect
from pathlib import Path
import pyblish.api

from quadpype.pipeline import (
    OptionalPyblishPluginMixin,
    Anatomy
)

from quadpype.hosts.blender.api import (
    get_resolved_name
)
from quadpype.pipeline.publish import (
    RepairContextAction,
    ValidateContentsOrder,
    PublishValidationError
)

class ValidateImagesPaths(pyblish.api.ContextPlugin,
                                     OptionalPyblishPluginMixin):
    """Validates Absolute Data Block Paths

    This validator checks if all external data paths are absolute
    to ensure the links would not be broken when publishing
    """

    label = "Validate Image Paths Location"
    order = ValidateContentsOrder
    hosts = ["blender"]
    exclude_families = []
    optional = True
    actions = [RepairContextAction]
    root_paths = list()

    @classmethod
    def get_invalid(cls, context):
        """Get all invalid image path if not in any root paths"""
        invalid = []
        for image in bpy.data.images:
            if not hasattr(image, "filepath"):
                continue

            path = Path(bpy.path.abspath(image.filepath))
            path_full = path.resolve()

            if any(path_full.is_relative_to(root_path) for root_path in cls.root_paths):
                continue

            cls.log.error(f"Image filepath {path.as_posix()} "
                          "is not in any root path")
            invalid.append(image)

        return invalid

    def get_root_paths(self, context):
        """Retrieve and solve all roots from Anatomy() with context data
        Will create a list of pathlib.Path"""
        anatomy = Anatomy()
        for root in anatomy.roots:
            template = str(anatomy.roots.get(root))
            resolved_path = get_resolved_name(context.data.get('anatomyData', {}), template)
            self.root_paths.append(Path(resolved_path).resolve())

    def process(self, context):
        if not self.is_active(context.data):
            self.log.debug("Skipping Validate Images Paths in Project Location...")
            return

        # Generate the root Paths
        self.get_root_paths(context)

        invalid = self.get_invalid(context)

        if invalid:
            invalid_msg = f"\n-\n".join(bpy.path.abspath(image.filepath) for image in invalid)
            root_path_msg = "\n".join(path.as_posix() for path in self.root_paths)
            raise PublishValidationError(
                f"Images filepath are not in project or ressources:\n"
                f"{invalid_msg}\n"
                f"--------------------------------------\n"
                f"Validate roots paths are:\n"
                f"{root_path_msg}",
                title="Invalid Image Path",
                description=self.get_description()
            )

    @classmethod
    def get_description(cls):
        return inspect.cleandoc("""
            ### Images filepaths are invalid
            Images filepaths must be in a root path:

            Click on the repair button will only:
            ### Select the objects that have a material which use an invalid file.
        """)

    @classmethod
    def repair(cls, context):
        """Will search if any selectable object is related to a material using
            an invalid image path and then, select them"""

        invalid = cls.get_invalid(context)

        if not invalid:
            return

        invalid = set(invalid)

        invalid_materials= list()

        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if not isinstance(node, bpy.types.ShaderNodeTexImage):
                    continue
                if any(node.image == img for img in invalid):
                    invalid_materials.append(mat)

        if not  invalid_materials:
            return

        bpy.ops.object.select_all(action='DESELECT')

        for obj in bpy.context.scene.objects:
            if not hasattr(obj.data, "materials"):
                continue
            if any(mat in invalid_materials for mat in obj.data.materials):
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
