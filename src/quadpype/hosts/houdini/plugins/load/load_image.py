import os

from quadpype.pipeline import (
    load,
    get_representation_path,
    QUADPYPE_CONTAINER_ID,
)
from quadpype.hosts.houdini.api import lib, pipeline

import hou


def get_image_database_containers():
    """The COP2 files must be in a COP2 network.

    So we maintain a single entry point within QUADPYPE_CONTAINERS,
    just for ease of use.

    """

    path = pipeline.QUADPYPE_CONTAINERS
    database_containers = hou.node(path)
    if not database_containers:
        # Let's create quadype container secretly
        # but make sure the pipeline still is built the
        # way we anticipate it was built, asserting it.
        assert path == "/obj/QUADPYPE_CONTAINERS"

        parent = hou.node("/obj")
        database_containers = parent.createNode(
            "subnet", node_name="QUADPYPE_CONTAINERS"
        )

    image_container = hou.node(path + "/IMAGES")
    if not image_container:
        image_container = database_containers.createNode(
            "cop2net", node_name="IMAGES"
        )
        image_container.moveToGoodPosition()

    return image_container


class ImageLoader(load.LoaderPlugin):
    """Load images into COP2"""

    families = ["imagesequence"]
    label = "Load Image (COP2)"
    representations = ["*"]
    order = -10

    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        # Format file name, Houdini only wants forward slashes
        file_path = self.filepath_from_context(context)
        file_path = os.path.normpath(file_path)
        file_path = file_path.replace("\\", "/")
        file_path = self._get_file_sequence(file_path)

        # Get the root node
        parent = get_image_database_containers()

        # Define node name
        namespace = namespace if namespace else context["asset"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        node = parent.createNode("file", node_name=node_name)
        node.moveToGoodPosition()

        node.setParms({"filename1": file_path})

        # Imprint it manually
        data = {
            "schema": "quadpype:container-2.0",
            "id": QUADPYPE_CONTAINER_ID,
            "name": node_name,
            "namespace": namespace,
            "loader": str(self.__class__.__name__),
            "representation": str(context["representation"]["_id"]),
        }

        # todo: add folder="QuadPype"
        lib.imprint(node, data)

        return node

    def update(self, container, representation):

        node = container["node"]

        # Update the file path
        file_path = get_representation_path(representation)
        file_path = file_path.replace("\\", "/")
        file_path = self._get_file_sequence(file_path)

        # Update attributes
        node.setParms(
            {
                "filename1": file_path,
                "representation": str(representation["_id"]),
            }
        )

    def remove(self, container):

        node = container["node"]

        # Let's clean up the IMAGES COP2 network
        # if it ends up being empty and we deleted
        # the last file node. Store the parent
        # before we delete the node.
        parent = node.parent()

        node.destroy()

        if not parent.children():
            parent.destroy()

    def _get_file_sequence(self, file_path):
        root = os.path.dirname(file_path)
        files = sorted(os.listdir(root))

        first_fname = files[0]
        prefix, padding, suffix = first_fname.rsplit(".", 2)
        fname = ".".join([prefix, "$F{}".format(len(padding)), suffix])
        return os.path.join(root, fname).replace("\\", "/")

    def switch(self, container, representation):
        self.update(container, representation)
