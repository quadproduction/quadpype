from quadpype.pipeline import CreatedInstance

from quadpype.lib import BoolDef
import quadpype.hosts.photoshop.api as api
from quadpype.hosts.photoshop.lib import PSAutoCreator, clean_subset_name
from quadpype.pipeline.create import get_subset_name
from quadpype.lib import prepare_template_data
from quadpype.client import get_asset_by_name


class AutoImageCreator(PSAutoCreator):
    """Creates flatten image from all visible layers.

    Used in simplified publishing as auto created instance.
    Must be enabled in Setting and template for subset name provided
    """
    identifier = "auto_image"
    family = "image"

    # Settings
    default_variant = ""
    # - Mark by default instance for review
    mark_for_review = True
    export_psd = False
    active_on_create = True

    def create(self, options=None):
        existing_instance = None
        for instance in self.create_context.instances:
            if instance.creator_identifier == self.identifier:
                existing_instance = instance
                break

        context = self.create_context
        project_name = context.get_current_project_name()
        asset_name = context.get_current_asset_name()
        task_name = context.get_current_task_name()
        host_name = context.host_name
        asset_doc = get_asset_by_name(project_name, asset_name)

        if existing_instance is None:
            existing_instance_asset = None
        else:
            existing_instance_asset = existing_instance["asset"]

        if existing_instance is None:
            subset_name = self.get_subset_name(
                self.default_variant, task_name, asset_doc,
                project_name, host_name
            )

            data = {
                "task": task_name,
            }
            data["asset"] = asset_name

            if not self.active_on_create:
                data["active"] = False

            creator_attributes = {"mark_for_review": self.mark_for_review,
                                  "export_psd": self.export_psd}
            data.update({"creator_attributes": creator_attributes})

            new_instance = CreatedInstance(
                self.family, subset_name, data, self
            )
            self._add_instance_to_context(new_instance)
            api.stub().imprint(new_instance.get("instance_id"),
                               new_instance.data_to_store())

        elif (  # existing instance from different context
            existing_instance_asset != asset_name
            or existing_instance["task"] != task_name
        ):
            subset_name = self.get_subset_name(
                self.default_variant, task_name, asset_doc,
                project_name, host_name
            )
            existing_instance["asset"] = asset_name
            existing_instance["task"] = task_name
            existing_instance["subset"] = subset_name

            api.stub().imprint(existing_instance.get("instance_id"),
                               existing_instance.data_to_store())

    def get_pre_create_attr_defs(self):
        return [
            BoolDef(
                "mark_for_review",
                label="Review",
                default=self.mark_for_review
            ),
            BoolDef(
                "export_psd",
                label="Export PSD",
                default=self.export_psd
            )
        ]

    def get_instance_attr_defs(self):
        return [
            BoolDef(
                "mark_for_review",
                label="Review"
            ),
            BoolDef(
                "export_psd",
                label="Export PSD"
            )
        ]

    def apply_settings(self, project_settings):
        plugin_settings = (
            project_settings["photoshop"]["create"]["AutoImageCreator"]
        )

        self.active_on_create = plugin_settings["active_on_create"]
        self.default_variant = plugin_settings["default_variant"]
        self.mark_for_review = plugin_settings["mark_for_review"]
        self.enabled = plugin_settings["enabled"]

    def get_detail_description(self):
        return """Creator for flatten image.

        Studio might configure simple publishing workflow. In that case
        `image` instance is automatically created which will publish flat
        image from all visible layers.

        Artist might disable this instance from publishing or from creating
        review for it though.
        """

    def get_subset_name(
            self,
            variant,
            task_name,
            asset_doc,
            project_name,
            host_name=None,
            instance=None
    ):
        dynamic_data = prepare_template_data({"layer": "{layer}"})
        subset_name = get_subset_name(
            self.family, variant, task_name, asset_doc,
            project_name, host_name, dynamic_data=dynamic_data
        )
        return clean_subset_name(subset_name)
