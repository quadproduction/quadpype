import pyblish.api
from quadpype.pipeline import registered_host


class ExtractSaveScene(pyblish.api.ContextPlugin):
    order = pyblish.api.ExtractorOrder - 0.49
    hosts = ["tvpaint"]
    label = "Extract Save Scene"
    families = ["workfile", "renderLayer", "review", "render"]

    def process(self, context):
        current_file = context.data["currentFile"]
        registered_host().save_workfile(current_file)
        self.log.info(f"Scene saved at {current_file}")
