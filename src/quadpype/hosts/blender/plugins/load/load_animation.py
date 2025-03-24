"""Load an animation in Blender."""

from typing import Dict, List, Optional

import bpy

from quadpype.hosts.blender.api import plugin
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

        with bpy.data.libraries.load(
            libpath, link=True, relative=False
        ) as (data_from, data_to):
            data_to.objects = data_from.objects
            data_to.actions = data_from.actions

        container = data_to.objects[0]
        assert container, "No asset group found"

        action = data_to.actions[0]
        assert action, "No action found"

        action = action.make_local().copy()
        target_namespace = get_avalon_node(container).get('namespace')

        for obj in bpy.data.objects:
            if get_avalon_node(obj).get('namespace') == target_namespace:
                for armature in self.get_armatures_with_animation(obj.children):
                    if not armature.animation_data:
                        armature.animation_data_create()
                    armature.animation_data.action = action

        bpy.data.objects.remove(container)

        filename = bpy.path.basename(libpath)
        # Blender has a limit of 63 characters for any data name.
        # If the filename is longer, it will be truncated.
        if len(filename) > 63:
            filename = filename[:63]
        library = bpy.data.libraries.get(filename)
        bpy.data.libraries.remove(library)

    @staticmethod
    def get_armatures_with_animation(children):
        return [
            child for child in children if
            child and
            child.type == 'ARMATURE'
        ]
