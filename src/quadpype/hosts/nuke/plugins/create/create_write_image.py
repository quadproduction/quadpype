import nuke

from quadpype.pipeline import (
    CreatedInstance
)
from quadpype.lib import (
    BoolDef,
    NumberDef,
    UISeparatorDef,
    EnumDef
)
from quadpype.pipeline import get_current_project_name
from quadpype.settings import get_project_settings
from quadpype.hosts.nuke import api as napi
from quadpype.hosts.nuke.api.plugin import exposed_write_knobs
from quadpype.hosts.nuke.api.backdrops import (
    pre_organize_by_backdrop,
    organize_by_backdrop
)


class CreateWriteImage(napi.NukeWriteCreator):
    identifier = "create_write_image"
    label = "Image (write)"
    family = "image"
    icon = "sign-out"

    instance_attributes = [
        "use_range_limit"
    ]
    default_variants = [
        "StillFrame",
        "MPFrame",
        "LayoutFrame"
    ]
    temp_rendering_path_template = (
        "{work}/renders/nuke/{subset}/{subset}.{frame}.{ext}")

    def get_pre_create_attr_defs(self):
        attr_defs = [
            BoolDef(
                "use_selection",
                default=not self.create_context.headless,
                label="Use selection"
            ),
            self._get_render_target_enum(),
            UISeparatorDef(),
            self._get_frame_source_number()
        ]
        return attr_defs

    def _get_render_target_enum(self):
        rendering_targets = {
            "local": "Local machine rendering",
            "frames": "Use existing frames"
        }

        return EnumDef(
            "render_target",
            items=rendering_targets,
            label="Render target"
        )

    def _get_frame_source_number(self):
        return NumberDef(
            "active_frame",
            label="Active frame",
            default=nuke.frame()
        )

    def create_instance_node(self, subset_name, instance_data):

        # add fpath_template
        write_data = {
            "creator": self.__class__.__name__,
            "subset": subset_name,
            "fpath_template": self.temp_rendering_path_template
        }
        write_data.update(instance_data)

        created_node = napi.create_write_node(
            subset_name,
            write_data,
            input=self.selected_node,
            prenodes=self.prenodes,
            linked_knobs=self.get_linked_knobs(),
            **{
                "frame": nuke.frame()
            }
        )

        self._add_frame_range_limit(created_node, instance_data)

        self.integrate_links(created_node, outputs=True)

        return created_node

    def create(self, subset_name, instance_data, pre_create_data):
        settings = get_project_settings(get_current_project_name()).get("nuke")
        use_backdrop_general = settings["general"].get("use_backdrop_loader_creator", True)
        use_backdrop = settings["create"]["CreateWriteImage"].get("use_backdrop_loader_creator", True)
        backdrop_padding = settings["create"]["CreateWriteImage"].get("backdrop_padding", 150)

        if use_backdrop and use_backdrop_general:
            nodes_in_main_backdrops = pre_organize_by_backdrop()
        subset_name = subset_name.format(**pre_create_data)

        # pass values from precreate to instance
        self.pass_pre_attributes_to_instance(
            instance_data,
            pre_create_data,
            [
                "active_frame",
                "render_target"
            ]
        )

        # make sure selected nodes are added
        self.set_selected_nodes(pre_create_data)

        # make sure subset name is unique
        self.check_existing_subset(subset_name)

        instance_node = self.create_instance_node(
            subset_name,
            instance_data,
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
            if use_backdrop and use_backdrop_general:
                main_backdrop, storage_backdrop, nodes = organize_by_backdrop(
                    data=dict(instance.data),
                    node=instance_node,
                    nodes_in_main_backdrops=nodes_in_main_backdrops,
                    options=dict(),
                    padding=backdrop_padding
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

    def _add_frame_range_limit(self, write_node, instance_data):
        if "use_range_limit" not in self.instance_attributes:
            return

        active_frame = (
            instance_data["creator_attributes"].get("active_frame"))

        write_node.begin()
        for n in nuke.allNodes():
            # get write node
            if n.Class() in "Write":
                w_node = n
        write_node.end()

        w_node["use_limit"].setValue(True)
        w_node["first"].setValue(active_frame or nuke.frame())
        w_node["last"].setExpression("first")

        return write_node
