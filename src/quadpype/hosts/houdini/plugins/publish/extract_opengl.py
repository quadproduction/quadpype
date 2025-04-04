import os

import pyblish.api

from quadpype.pipeline import publish
from quadpype.hosts.houdini.api.lib import render_rop

import hou


class ExtractOpenGL(publish.Extractor):

    order = pyblish.api.ExtractorOrder - 0.01
    label = "Extract OpenGL"
    families = ["review"]
    hosts = ["houdini"]

    def process(self, instance):
        ropnode = hou.node(instance.data.get("instance_node"))

        output = ropnode.evalParm("picture")
        staging_dir = os.path.normpath(os.path.dirname(output))
        instance.data["stagingDir"] = staging_dir
        file_name = os.path.basename(output)

        self.log.info("Extracting '%s' to '%s'" % (file_name,
                                                   staging_dir))

        render_rop(ropnode)

        output = instance.data["frames"]

        tags = ["review"]
        if not instance.data.get("keepImages"):
            tags.append("delete")

        representation = {
            "name": instance.data["imageFormat"].lower(),
            "ext": instance.data["imageFormat"].lower(),
            "files": output,
            "stagingDir": staging_dir,
            "frameStart": instance.data["frameStartHandle"],
            "frameEnd": instance.data["frameEndHandle"],
            "tags": tags,
            "preview": True,
            "camera_name": instance.data.get("review_camera")
        }

        if "representations" not in instance.data:
            instance.data["representations"] = []
        instance.data["representations"].append(representation)

        # Use the first image as a thumbnail if it's not already set.
        if not instance.data.get("thumbnailSource") and output:
            instance.data["thumbnailSource"] = os.path.join(staging_dir, output[0])
