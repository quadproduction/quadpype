import maya.cmds as cmds

from quadpype.pipeline import (
    load,
    remove_container
)

from quadpype.hosts.maya.api.pipeline import containerise
from quadpype.hosts.maya.api.lib import unique_namespace
from quadpype.hosts.maya.api import setdress


class AssemblyLoader(load.LoaderPlugin):

    families = ["assembly"]
    representations = ["json"]

    label = "Load Set Dress"
    order = -9
    icon = "code-fork"
    color = "orange"

    def load(self, context, name, namespace, data):

        asset = context['asset']['name']
        namespace = namespace or unique_namespace(
            asset + "_",
            prefix="_" if asset[0].isdigit() else "",
            suffix="_",
        )

        containers = setdress.load_package(
            filepath=self.filepath_from_context(context),
            name=name,
            namespace=namespace
        )

        self[:] = containers

        # Only containerize if any nodes were loaded by the Loader
        nodes = self[:]
        if not nodes:
            return

        return containerise(
            name=name,
            namespace=namespace,
            nodes=nodes,
            context=context,
            loader=self.__class__.__name__)

    def update(self, container, representation):

        return setdress.update_package(container, representation)

    def remove(self, container):
        """Remove all sub containers"""

        # Remove all members
        member_containers = setdress.get_contained_containers(container)
        for member_container in member_containers:
            self.log.info("Removing container %s",
                          member_container['objectName'])
            remove_container(member_container)

        # Remove alembic hierarchy reference
        # TODO: Check whether removing all contained references is safe enough
        members = cmds.sets(container['objectName'], query=True) or []
        references = cmds.ls(members, type="reference")
        for reference in references:
            self.log.info("Removing %s", reference)
            fname = cmds.referenceQuery(reference, filename=True)
            cmds.file(fname, removeReference=True)

        # Delete container and its contents
        if cmds.objExists(container['objectName']):
            members = cmds.sets(container['objectName'], query=True) or []
            cmds.delete([container['objectName']] + members)

        # TODO: Ensure namespace is gone
