"""Load an asset in Blender from an Alembic file."""

from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional
import json
import os
import bpy

from quadpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
)
from quadpype.hosts.blender.api import plugin, lib
from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS,
    AVALON_PROPERTY,
)


class AbcCameraLoader(plugin.BlenderLoader):
    """Load a camera from Alembic file.

    Stores the imported asset in an empty named after the asset.
    """

    families = ["camera"]
    representations = ["abc"]

    label = "Load Camera (ABC)"
    icon = "code-fork"
    color = "orange"

    def _remove(self, asset_group):
        objects = list(asset_group.children)

        for obj in objects:
            if obj.type == "CAMERA":
                bpy.data.cameras.remove(obj.data)
            elif obj.type == "EMPTY":
                objects.extend(obj.children)
                bpy.data.objects.remove(obj)

    def _process(self, libpath, asset_group, group_name):
        plugin.deselect_all()

        # Force the creation of the transform cache even if the camera
        # doesn't have an animation. We use the cache to update the camera.
        bpy.ops.wm.alembic_import(
            filepath=libpath, always_add_cache_reader=True)

        objects = lib.get_selection()

        for obj in objects:
            obj.parent = asset_group

        for obj in objects:
            name = obj.name
            obj.name = f"{group_name}:{name}"
            if obj.type != "EMPTY":
                name_data = obj.data.name
                obj.data.name = f"{group_name}:{name_data}"

            if not obj.get(AVALON_PROPERTY):
                obj[AVALON_PROPERTY] = dict()

            avalon_info = obj[AVALON_PROPERTY]
            avalon_info.update({"container_name": group_name})

        plugin.deselect_all()

        return objects

    def process_asset(
        self,
        context: dict,
        name: str,
        namespace: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> Optional[List]:
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """

        libpath = self.filepath_from_context(context)

        asset = context["asset"]["name"]
        subset = context["subset"]["name"]

        asset_name = plugin.prepare_scene_name(asset, subset)
        unique_number = plugin.get_unique_number(asset, subset)
        group_name = plugin.prepare_scene_name(asset, subset, unique_number)
        namespace = namespace or f"{asset}_{unique_number}"

        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)

        asset_group = bpy.data.objects.new(group_name, object_data=None)
        avalon_container.objects.link(asset_group)

        self._process(libpath, asset_group, group_name)

        objects = []
        nodes = list(asset_group.children)

        for obj in nodes:
            if obj.type == 'CAMERA':
                camera = obj.data
                jsonpath_camera_data = (Path(str(libpath)).with_suffix('.json'))
                camera_data = {}
                if Path(jsonpath_camera_data).exists():
                    with open(jsonpath_camera_data) as my_file:
                        camera_data = json.loads(my_file.read())

                if camera_data:
                    for frame in camera_data["focal_data"].keys():
                        camera.lens = camera_data["focal_data"][frame]
                        camera.keyframe_insert(data_path="lens", frame=int(frame))

            objects.append(obj)
            nodes.extend(list(obj.children))

        bpy.context.scene.collection.objects.link(asset_group)

        asset_group[AVALON_PROPERTY] = {
            "schema": "quadpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or "",
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["_id"],
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": context["representation"]["parent"],
            "family": context["representation"]["context"]["family"],
            "objectName": group_name,
        }

        self[:] = objects
        return objects

    def exec_update(self, container: Dict, representation: Dict):
        """Update the loaded asset.

        This will remove all objects of the current collection, load the new
        ones and add them to the collection.
        If the objects of the collection are used in another collection they
        will not be removed, only unlinked. Normally this should not be the
        case though.

        Warning:
            No nested collections are supported at the moment!
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)
        libpath = Path(get_representation_path(representation))
        prev_filename = os.path.basename(container["libpath"])        
        extension = libpath.suffix.lower()

        self.log.info(
            "Container: %s\nRepresentation: %s",
            pformat(container, indent=2),
            pformat(representation, indent=2),
        )

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}")
        assert libpath, (
            f"No existing library file found for {container['objectName']}")
        assert libpath.is_file(), f"The file doesn't exist: {libpath}"
        assert extension in plugin.VALID_EXTENSIONS, (
            f"Unsupported file: {libpath}")

        metadata = asset_group.get(AVALON_PROPERTY)
        group_libpath = metadata["libpath"]

        normalized_group_libpath = str(
            Path(bpy.path.abspath(group_libpath)).resolve())
        normalized_libpath = str(
            Path(bpy.path.abspath(str(libpath))).resolve())
        self.log.info(
            "normalized_group_libpath:\n  %s\nnormalized_libpath:\n  %s",
            normalized_group_libpath,
            normalized_libpath,
        )
        if normalized_group_libpath == normalized_libpath:
            self.log.info("Library already loaded, not updating...")
            return

        bpy.ops.cachefile.open(filepath=libpath.as_posix())
        for obj in asset_group.children:
            asset_name = obj.name.rsplit(":", 1)[-1]
            names = [constraint.name for constraint in obj.constraints
                     if constraint.type == "TRANSFORM_CACHE"]
            file_list = [file for file in bpy.data.cache_files
                        if file.name.startswith(prev_filename)]
            if names:
                for name in names:
                    obj.constraints.remove(obj.constraints.get(name))
            if file_list:
                bpy.data.batch_remove(file_list)

            constraint = obj.constraints.new("TRANSFORM_CACHE")
            constraint.cache_file = bpy.data.cache_files[-1]
            constraint.cache_file.name = os.path.basename(libpath)
            constraint.cache_file.filepath = libpath.as_posix()
            constraint.cache_file.scale = 1.0
            bpy.context.evaluated_depsgraph_get()

            for object_path in constraint.cache_file.object_paths:
                base_object_name = os.path.basename(object_path.path)
                if base_object_name.startswith(asset_name):
                    constraint.object_path = object_path.path

        metadata["libpath"] = str(libpath)
        metadata["representation"] = representation["_id"]

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (quadpype:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted.

        Warning:
            No nested collections are supported at the moment!
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)

        if not asset_group:
            return False

        self._remove(asset_group)

        bpy.data.objects.remove(asset_group)

        return True