import json
import pyblish.api
from pathlib import Path
import tempfile

from quadpype.hosts.tvpaint.api.lib import (
    execute_george_through_file
)

class CollectWorkfile(pyblish.api.InstancePlugin):
    label = "Collect Workfile"
    order = pyblish.api.CollectorOrder - 0.4
    hosts = ["tvpaint"]
    families = ["workfile"]

    def process(self, instance):
        context = instance.context
        current_file = Path(context.data["currentFile"])

        self.log.info(
            "Workfile path used for workfile family: {}".format(str(current_file))
        )

        filename = current_file.name
        ext = current_file.suffix.lstrip(".")
        dirpath = self._create_temp_workfile(filename)

        instance.data["representations"].append({
            "name": ext.lstrip(".").lower(),
            "ext": ext.lstrip(".").lower(),
            "files": filename,
            "stagingDir": dirpath
        })

        instance.context.data["cleanupFullPaths"].append(dirpath)

        self.log.info("Collected workfile instance: {}".format(
            json.dumps(instance.data, indent=4)
        ))

    @staticmethod
    def _create_temp_workfile(filename):
        """Create a temporary saved workfile.
        It is important in case the user doesn't save before publish to have
        the exact same file in the published workfile and the working workfile

        Return: the new staging_dir"""

        staging_dir = (
            tempfile.mkdtemp(prefix="tvpaint_render_")
        ).replace("\\", "/")

        temp_wofkfile_path = Path(staging_dir) / filename
        george_script = u"tv_SaveProject '{}'".format(str(temp_wofkfile_path))

        execute_george_through_file(george_script)
        return staging_dir
