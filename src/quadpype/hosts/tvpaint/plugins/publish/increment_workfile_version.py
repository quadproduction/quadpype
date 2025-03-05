from pathlib import Path

import pyblish.api
import pyblish.plugin
from quadpype.lib import version_up
from quadpype.pipeline import registered_host


class IncrementWorkfileVersion(pyblish.api.ContextPlugin):
    """Increment current workfile version."""

    order = pyblish.api.ExtractorOrder + 0.495
    label = "Increment Workfile Version"
    optional = True
    hosts = ["tvpaint"]
    families = ["workfile"]

    def process(self, context):

        assert all(result["success"] for result in context.data["results"]), (
            "Publishing not successful so version is not increased.")

        host = registered_host()
        self.path = version_up(context.data["currentFile"])
        host.save_workfile(self.path)
        self.log.info('Incrementing workfile version')

        workfile_instance = self.filter_instances(context)
        if isinstance(workfile_instance, pyblish.plugin.Instance):
            self.update_path_data(context, workfile_instance)
            self.log.info('Update Context and Instance data')

    def filter_instances(self, context):
        """Retrieve only workfile instance"""
        workfile_instance = None
        for instance in context:
            # Validate instance by family to keep only workfile
            if instance.data["family"] not in self.families:
                continue
            workfile_instance = instance
        return workfile_instance

    def update_path_data(self, context, instance):
        """Update file path data in both Context and Instance"""
        #First the context
        context.data["currentFile"] = self.path

        # Then the instance
        repres = instance.data.get("representations")
        # Validate type of stored representations
        if not isinstance(repres, (list, tuple)):
            raise TypeError(
                "Instance 'files' must be a list, got: {0} {1}".format(
                    str(type(repres)), str(repres)
                )
            )

        for repre in repres:
            repre["files"] = Path(self.path).name
