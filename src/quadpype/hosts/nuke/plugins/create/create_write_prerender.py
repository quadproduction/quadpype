import nuke

from quadpype.pipeline import (
    CreatedInstance
)
from quadpype.lib import (
    BoolDef
)
from quadpype.hosts.nuke import api as napi
from quadpype.hosts.nuke.api.plugin import exposed_write_knobs
from quadpype.hosts.nuke.api.backdrops import (
    pre_organize_by_backdrop,
    organize_by_backdrop
)

class CreateWritePrerender(napi.NukeWriteCreator):
    identifier = "create_write_prerender"
    label = "Prerender (write)"
    family = "prerender"
    icon = "sign-out"

    instance_attributes = [
        "use_range_limit"
    ]
    default_variants = [
        "Key01",
        "Bg01",
        "Fg01",
        "Branch01",
        "Part01"
    ]
    temp_rendering_path_template = (
        "{work}/renders/nuke/{subset}/{subset}.{frame}.{ext}")

    # Before write node render.
    order = 90

    def get_pre_create_attr_defs(self):
        attr_defs = [
            BoolDef(
                "use_selection",
                default=not self.create_context.headless,
                label="Use selection"
            ),
            self._get_render_target_enum()
        ]
        return attr_defs

    def create_instance_node(self, subset_name, instance_data):
        # add fpath_template
        write_data = {
            "creator": self.__class__.__name__,
            "subset": subset_name,
            "fpath_template": self.temp_rendering_path_template
        }

        write_data.update(instance_data)

        # get width and height
        if self.selected_node:
            width, height = (
                self.selected_node.width(), self.selected_node.height())
        else:
            actual_format = nuke.root().knob('format').value()
            width, height = (actual_format.width(), actual_format.height())

        created_node = napi.create_write_node(
            subset_name,
            write_data,
            input=self.selected_node,
            prenodes=self.prenodes,
            linked_knobs=self.get_linked_knobs(),
            **{
                "width": width,
                "height": height
            }
        )

        self._add_frame_range_limit(created_node)

        self.integrate_links(created_node, outputs=True)

        return created_node

    def create(self, subset_name, instance_data, pre_create_data):
        nodes_in_main_backdrops = pre_organize_by_backdrop()
        # pass values from precreate to instance
        self.pass_pre_attributes_to_instance(
            instance_data,
            pre_create_data,
            [
                "render_target"
            ]
        )

        # make sure selected nodes are added
        self.set_selected_nodes(pre_create_data)

        # make sure subset name is unique
        self.check_existing_subset(subset_name)

        instance_node = self.create_instance_node(
            subset_name,
            instance_data
        )

        try:
            instance = CreatedInstance(
                self.family,
                subset_name,
                instance_data,
                self
            )

            instance.transient_data["node"] = instance_node

            self._add_instance_to_context(instance)

            imprint_data = instance.data_to_store()

            main_backdrop, storage_backdrop, nodes = organize_by_backdrop(
                data=dict(instance.data),
                node=instance_node,
                nodes_in_main_backdrops=nodes_in_main_backdrops,
                options=dict()
            )
            imprint_data["main_backdrop"] = main_backdrop.name()
            imprint_data["storage_backdrop"] = storage_backdrop.name()

            napi.set_node_data(
                instance_node,
                napi.INSTANCE_DATA_KNOB,
                imprint_data
            )

            exposed_write_knobs(
                self.project_settings, self.__class__.__name__, instance_node
            )

            return instance

        except Exception as e:
            raise napi.NukeCreatorError("Creator error: {}".format(e))

    def _add_frame_range_limit(self, write_node):
        if "use_range_limit" not in self.instance_attributes:
            return

        write_node.begin()
        for n in nuke.allNodes():
            # get write node
            if n.Class() in "Write":
                w_node = n
        write_node.end()

        w_node["use_limit"].setValue(True)
        w_node["first"].setValue(nuke.root()["first_frame"].value())
        w_node["last"].setValue(nuke.root()["last_frame"].value())

        return write_node
