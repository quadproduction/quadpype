import os

import maya.cmds as cmds

from quadpype.hosts.maya.api.pipeline import containerise
from quadpype.hosts.maya.api.lib import unique_namespace
from quadpype.pipeline import (
    load,
    get_representation_path
)
from quadpype.settings import get_project_settings


class GpuCacheLoader(load.LoaderPlugin):
    """Load Alembic as gpuCache"""

    families = ["model", "animation", "proxyAbc", "pointcache"]
    representations = ["abc", "gpu_cache"]

    label = "Load Gpu Cache"
    order = -5
    icon = "code-fork"
    color = "orange"

    def load(self, context, name, namespace, data):

        asset = context['asset']['name']
        namespace = namespace or unique_namespace(
            asset + "_",
            prefix="_" if asset[0].isdigit() else "",
            suffix="_",
        )

        cmds.loadPlugin("gpuCache", quiet=True)

        # Root group
        label = "{}:{}".format(namespace, name)
        root = cmds.group(name=label, empty=True)

        project_name = context["project"]["name"]
        settings = get_project_settings(project_name)
        colors = settings['maya']['load']['colors']
        c = colors.get('model')
        if c is not None:
            cmds.setAttr(root + ".useOutlinerColor", 1)
            cmds.setAttr(
                root + ".outlinerColor",
                (float(c[0]) / 255), (float(c[1]) / 255), (float(c[2]) / 255)
            )

        # Create transform with shape
        transform_name = label + "_GPU"
        transform = cmds.createNode("transform", name=transform_name,
                                    parent=root)
        cache = cmds.createNode("gpuCache",
                                parent=transform,
                                name="{0}Shape".format(transform_name))

        # Set the cache filepath
        path = self.filepath_from_context(context)
        cmds.setAttr(cache + '.cacheFileName', path, type="string")
        cmds.setAttr(cache + '.cacheGeomPath', "|", type="string")    # root

        # Lock parenting of the transform and cache
        cmds.lockNode([transform, cache], lock=True)

        nodes = [root, transform, cache]
        self[:] = nodes

        return containerise(
            name=name,
            namespace=namespace,
            nodes=nodes,
            context=context,
            loader=self.__class__.__name__)

    def update(self, container, representation):
        path = get_representation_path(representation)

        # Update the cache
        members = cmds.sets(container['objectName'], query=True)
        caches = cmds.ls(members, type="gpuCache", long=True)

        assert len(caches) == 1, "This is a bug"

        for cache in caches:
            cmds.setAttr(cache + ".cacheFileName", path, type="string")

        cmds.setAttr(container["objectName"] + ".representation",
                     str(representation["_id"]),
                     type="string")

    def switch(self, container, representation):
        self.update(container, representation)

    def remove(self, container):
        members = cmds.sets(container['objectName'], query=True)
        cmds.lockNode(members, lock=False)
        cmds.delete([container['objectName']] + members)

        # Clean up the namespace
        try:
            cmds.namespace(removeNamespace=container['namespace'],
                           deleteNamespaceContent=True)
        except RuntimeError:
            pass
