import os

from quadpype import PACKAGE_DIR
from quadpype.style import get_default_entity_icon_color
from quadpype.lib import get_quadpype_execute_args, run_detached_process
from quadpype.pipeline import load
from quadpype.pipeline.load import LoadError


class PushToLibraryProject(load.SubsetLoaderPlugin):
    """Export selected versions to folder structure from Template"""

    is_multiple_contexts_compatible = True

    representations = ["*"]
    families = ["*"]

    label = "Push to Library project"
    order = 35
    icon = "send"
    color = get_default_entity_icon_color()

    def load(self, contexts, name=None, namespace=None, options=None):
        filtered_contexts = [
            context
            for context in contexts
            if context.get("project") and context.get("version")
        ]
        if not filtered_contexts:
            raise LoadError("Nothing to push for your selection")

        if len(filtered_contexts) > 1:
            raise LoadError("Please select only one item")

        context = tuple(filtered_contexts)[0]
        push_tool_script_path = os.path.join(
            PACKAGE_DIR,
            "tools",
            "push_to_project",
            "app.py"
        )

        project_doc = context["project"]
        version_doc = context["version"]
        project_name = project_doc["name"]
        version_id = str(version_doc["_id"])

        args = get_quadpype_execute_args(
            "run",
            push_tool_script_path,
            "--project", project_name,
            "--version", version_id
        )
        run_detached_process(args)
