# -*- coding: utf-8 -*-
"""Extract rig as Maya Scene."""
import os

from maya import cmds

from quadpype.settings import PROJECT_SETTINGS_KEY
from quadpype.pipeline import publish
from quadpype.hosts.maya.api.lib import maintained_selection


class ExtractRig(publish.Extractor):
    """Extract rig as Maya Scene."""

    label = "Extract Rig (Maya Scene)"
    hosts = ["maya"]
    families = ["rig"]
    scene_type = "ma"

    def process(self, instance):
        """Plugin entry point."""
        ext_mapping = (
            instance.context.data[PROJECT_SETTINGS_KEY]["maya"]["ext_mapping"]
        )
        if ext_mapping:
            self.log.debug("Looking in settings for scene type ...")
            # use extension mapping for first family found
            for family in self.families:
                try:
                    self.scene_type = ext_mapping[family]
                    self.log.debug(
                        "Using '.{}' as scene type".format(self.scene_type))
                    break
                except AttributeError:
                    # no preset found
                    pass
        # Define extract output file path
        dir_path = self.staging_dir(instance)
        filename = "{0}.{1}".format(instance.name, self.scene_type)
        path = os.path.join(dir_path, filename)

        # Perform extraction
        self.log.debug("Performing extraction ...")
        with maintained_selection():
            cmds.select(instance, noExpand=True)
            cmds.file(path,
                      force=True,
                      typ="mayaAscii" if self.scene_type == "ma" else "mayaBinary",  # noqa: E501
                      exportSelected=True,
                      preserveReferences=False,
                      channels=True,
                      constraints=True,
                      expressions=True,
                      constructionHistory=True)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': self.scene_type,
            'ext': self.scene_type,
            'files': filename,
            "stagingDir": dir_path
        }
        instance.data["representations"].append(representation)

        self.log.debug("Extracted instance '%s' to: %s", instance.name, path)
