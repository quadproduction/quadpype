import pyblish.api

from quadpype.pipeline import registered_host


class SaveCurrentScene(pyblish.api.ContextPlugin):
    """Save current scene"""

    label = "Save current file"
    order = pyblish.api.ExtractorOrder - 0.49
    hosts = ["houdini"]

    def process(self, context):

        # Filename must not have changed since collecting
        host = registered_host()
        current_file = host.get_current_workfile()
        assert context.data['currentFile'] == current_file, (
            "Collected filename from current scene name."
        )

        if host.workfile_has_unsaved_changes():
            self.log.info("Saving current file: {}".format(current_file))
            host.save_workfile(current_file)
        else:
            self.log.debug("No unsaved changes, skipping file save..")
