"""Load an animation in Blender."""

from typing import Dict, List, Optional

import bpy

from quadpype.hosts.blender.api import plugin, pipeline, lib
from quadpype.hosts.blender.api.pipeline import get_avalon_node


class BlendAnimationLoader(plugin.BlenderLoader):
    """Load animations from a .blend file.

    Warning:
        Loading the same asset more then once is not properly supported at the
        moment.
    """

    families = ["animation"]
    representations = ["blend"]

    label = "Link Animation"
    icon = "code-fork"
    color = "orange"

    def process_asset(
        self, context: dict, name: str, namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[List]:
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        libpath = self.filepath_from_context(context)
        previous_libraries = [library.name for library in bpy.data.libraries]
        previous_actions = [action.name for action in bpy.data.actions]

        with bpy.data.libraries.load(
            libpath, link=True, relative=False
        ) as (data_from, data_to):
            data_to.collections = data_from.collections
            data_to.actions = data_from.actions

        container = pipeline.get_container(collections=data_to.collections)
        correspondance = get_avalon_node(container).get("correspondance")
        target_namespace = get_avalon_node(container).get('namespace')
        assert container, "No asset group found"

        actions = data_to.actions
        assert actions, "No action found"

        for action in actions:
            if action.name in previous_actions:
                bpy.data.actions.remove(bpy.data.actions.get(action.name))
            action.make_local().copy()

        avalon_container_coll = bpy.data.collections.get(pipeline.AVALON_CONTAINERS)
        loaded_containers = (pipeline.get_container_content(avalon_container_coll)
                            if avalon_container_coll else []
        )

        for loaded_container in loaded_containers:
            if not get_avalon_node(loaded_container).get('namespace') == target_namespace:
                continue
            for obj in pipeline.get_container_content(loaded_container):
                if not obj.name in correspondance.keys():
                    continue
                if not obj.animation_data:
                    obj.animation_data_create()
                obj.animation_data.action = bpy.data.actions.get(
                    correspondance.get(obj.name), f"{obj.name}Action"
                )

        for library in bpy.data.libraries:
            if library.name in previous_libraries:
                continue
            bpy.data.libraries.remove(library)
