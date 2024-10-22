from quadpype.hosts.fusion.api import (
    get_current_comp
)
from quadpype.client import get_asset_by_name
from quadpype.pipeline import (
    AutoCreator,
    CreatedInstance,
)


class FusionWorkfileCreator(AutoCreator):
    identifier = "workfile"
    family = "workfile"
    label = "Workfile"
    icon = "fa5.file"

    default_variant = "Main"

    create_allow_context_change = False

    data_key = "quadpype_workfile"

    def collect_instances(self):

        comp = get_current_comp()
        data = comp.GetData(self.data_key)
        if not data:
            return

        instance = CreatedInstance(
            family=self.family,
            subset_name=data["subset"],
            data=data,
            creator=self
        )
        instance.transient_data["comp"] = comp

        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        for created_inst, _changes in update_list:
            comp = created_inst.transient_data["comp"]
            if not hasattr(comp, "SetData"):
                # Comp is not alive anymore, likely closed by the user
                self.log.error("Workfile comp not found for existing instance."
                               " Comp might have been closed in the meantime.")
                continue

            # Imprint data into the comp
            data = created_inst.data_to_store()
            comp.SetData(self.data_key, data)

    def create(self, options=None):

        comp = get_current_comp()
        if not comp:
            self.log.error("Unable to find current comp")
            return

        existing_instance = None
        for instance in self.create_context.instances:
            if instance.family == self.family:
                existing_instance = instance
                break

        project_name = self.create_context.get_current_project_name()
        asset_name = self.create_context.get_current_asset_name()
        task_name = self.create_context.get_current_task_name()
        host_name = self.create_context.host_name

        if existing_instance is None:
            existing_instance_asset = None
        else:
            existing_instance_asset = existing_instance["asset"]

        if existing_instance is None:
            asset_doc = get_asset_by_name(project_name, asset_name)
            subset_name = self.get_subset_name(
                self.default_variant, task_name, asset_doc,
                project_name, host_name
            )
            data = {
                "task": task_name,
                "variant": self.default_variant
            }
            data["asset"] = asset_name
            data.update(self.get_dynamic_data(
                self.default_variant, task_name, asset_doc,
                project_name, host_name, None
            ))

            new_instance = CreatedInstance(
                self.family, subset_name, data, self
            )
            new_instance.transient_data["comp"] = comp
            self._add_instance_to_context(new_instance)

        elif (
            existing_instance_asset != asset_name
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
