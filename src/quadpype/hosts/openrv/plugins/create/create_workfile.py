import qtawesome

from quadpype.hosts.openrv.api.pipeline import (
    read, imprint
)
from quadpype.client import get_asset_by_name
from quadpype.pipeline import (
    AutoCreator,
    CreatedInstance,
    legacy_io
)


class OpenRVWorkfileCreator(AutoCreator):
    identifier = "workfile"
    family = "workfile"
    label = "Workfile"

    default_variant = "Main"
    create_allow_context_change = False
    data_store_node = "root"
    data_store_prefix = "quadpype_workfile."

    def collect_instances(self):

        data = read(node=self.data_store_node,
                    prefix=self.data_store_prefix)
        if not data:
            return

        instance = CreatedInstance(
            family=self.family,
            subset_name=data["subset"],
            data=data,
            creator=self
        )

        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        for created_inst, _changes in update_list:
            data = created_inst.data_to_store()
            imprint(node=self.data_store_node,
                    data=data,
                    prefix=self.data_store_prefix)

    def create(self, options=None):

        existing_instance = None
        for instance in self.create_context.instances:
            if instance.family == self.family:
                existing_instance = instance
                break

        project_name = legacy_io.Session["QUADPYPE_PROJECT_NAME"]
        asset_name = legacy_io.Session["QUADPYPE_ASSET_NAME"]
        task_name = legacy_io.Session["QUADPYPE_TASK_NAME"]
        host_name = legacy_io.Session["QUADPYPE_HOST_NAME"]

        if existing_instance is None:
            asset_doc = get_asset_by_name(project_name, asset_name)
            subset_name = self.get_subset_name(
                self.default_variant, task_name, asset_doc,
                project_name, host_name
            )
            data = {
                "asset": asset_name,
                "task": task_name,
                "variant": self.default_variant
            }
            data.update(self.get_dynamic_data(
                self.default_variant, task_name, asset_doc,
                project_name, host_name, None
            ))

            new_instance = CreatedInstance(
                self.family, subset_name, data, self
            )
            self._add_instance_to_context(new_instance)

        elif (
            existing_instance["asset"] != asset_name
            or existing_instance["task"] != task_name
        ):
            asset_doc = get_asset_by_name(project_name, asset_name)
            subset_name = self.get_subset_name(
                self.default_variant, task_name, asset_doc,
                project_name, host_name
            )
            existing_instance["asset"] = asset_name
            existing_instance["task"] = task_name
            existing_instance["subset"] = subset_name

    def get_icon(self):
        return qtawesome.icon("fa.file-o", color="white")
