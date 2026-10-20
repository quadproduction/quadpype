import bpy
import inspect
from pathlib import Path
import pyblish.api

from quadpype.pipeline import (
    OptionalPyblishPluginMixin,
    Anatomy
)

from quadpype.pipeline import (
    get_resolved_name
)
from quadpype.pipeline.publish import (
    RepairContextAction,
    ValidateContentsOrder,
    PublishValidationError
)

class ValidateDataBlockRootPathError(PublishValidationError):
    """Custom error for invalid data block root paths."""
    label = "Save Workfile"
    on = "failed"
    icon = "wrench"

    def process(self, context, plugin):
        bpy.ops.wm.avalon_workfiles()

class ValidateDataBlockRootPaths(
    pyblish.api.ContextPlugin,
    OptionalPyblishPluginMixin
    ):
    """Validates Data Block Paths are in any given root path

    This validator checks if all external data paths are from
    one of the given root path in settings
    """

    label = "Validate Data Block Paths Location"
    order = ValidateContentsOrder
    hosts = ["blender"]
    exclude_families = []
    optional = True
    root_paths = list()
    actions = [RepairContextAction]

    @classmethod
    def get_invalid(cls, context):
        """Get all invalid data block path if not in any root paths"""
        invalid = []
        object_type = type(bpy.data.objects)
        for attr in dir(bpy.data):
            collections = getattr(bpy.data, attr)
            if not isinstance(collections, object_type):
                continue
            for data_block in collections:
                if not hasattr(data_block, "filepath"):
                    continue
                if not data_block.filepath:
                    continue

                path = Path(bpy.path.abspath(data_block.filepath))
                path_full = path.resolve()

                if any(path_full.is_relative_to(root_path) for root_path in cls.root_paths):
                    continue

                cls.log.warning(f"Data Block {attr} filepath {data_block.filepath} "
                              "is not in a root path")
                invalid.append(data_block)
        return invalid

    @classmethod
    def get_root_paths(cls, context):
        """Retrieve and solve all roots from Anatomy() with context data
        Will create a list of pathlib.Path"""
        anatomy = Anatomy()
        for root_name, root_val in anatomy.roots.items():
            resolved_path = get_resolved_name(context.data.get('anatomyData', {}), str(root_val))
            cls.root_paths.append(Path(resolved_path).resolve())

    def process(self, context):
        if not self.is_active(context.data):
            self.log.debug("Skipping Validate Data Block Paths Location...")
            return

        # Generate the root Paths
        self.get_root_paths(context)

        invalid = self.get_invalid(context)

        if invalid:
            invalid_msg = f"\n-\n".join(bpy.path.abspath(image.filepath) for image in invalid)
            root_path_msg = "\n".join(path.as_posix() for path in self.root_paths)
            raise PublishValidationError(
                f"DataBlock filepath are not in any roots:\n"
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
            ### DataBlock filepaths are invalid
            Data Block filepaths must be in any of the root paths.

            Use the repair function to automatically:
            - move packed images to the correct root path and unpack them
            - remove linked-library datablocks
        """)

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid(instance)
        if not invalid:
            return

        for data_block in list(invalid):
            if isinstance(data_block, bpy.types.Library):
                bpy.data.batch_remove([data_block])
                continue

            if isinstance(data_block, bpy.types.Image) and data_block.packed_file:

                blend_dir = Path(bpy.data.filepath).parent
                texture_dir = blend_dir / "textures"
                texture_dir.mkdir(parents=True, exist_ok=True)

                filename = Path(data_block.name.replace("\\", "/")).name
                if not Path(filename).suffix:
                    suffix = Path(data_block.filepath).suffix if data_block.filepath else ""
                    filename += suffix or ".png"

                unpack_path = texture_dir / filename

                unpack_path.write_bytes(data_block.packed_file.data)

                data_block.unpack(method="REMOVE")

                data_block.filepath = str(unpack_path)
                data_block.source = "FILE"
                data_block.reload()
                continue
