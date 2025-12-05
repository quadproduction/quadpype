import nuke

from quadpype.pipeline import (
    CreatedInstance
)
from quadpype.settings import get_project_settings
from quadpype.pipeline import get_current_project_name
from quadpype.lib import (
    BoolDef,
    EnumDef,
)

from quadpype.hosts.nuke import api as napi
from quadpype.pipeline.settings import get_available_resolutions, extract_width_and_height
from quadpype.hosts.nuke.api.plugin import exposed_write_knobs
from quadpype.hosts.nuke.api.lib import (
    AUTORESIZE_LABEL,
    get_custom_res
)
from quadpype.hosts.nuke.api.backdrops import (
    pre_organize_by_backdrop,
    organize_by_backdrop
)

class CreateWriteRender(napi.NukeWriteCreator):
    identifier = "create_write_render"
    label = "Render (write)"
    family = "render"
    icon = "sign-out"

    instance_attributes = [
        "reviewable"
    ]
    default_variants = [
        "Main",
        "Mask"
    ]
    temp_rendering_path_template = (
        "{work}/renders/nuke/{subset}/{subset}.{frame}.{ext}")

    resolution = None
    resolutions = []
    autoresize = False

    def get_pre_create_attr_defs(self):
        attr_defs = [
            BoolDef(
                "use_selection",
                default=not self.create_context.headless,
                label="Use selection"
            ),
            self._get_render_target_enum(),
        ]

        project_name = get_current_project_name()
        project_settings = get_project_settings(project_name)
        self.autoresize = project_settings.get('nuke', {}).get('create', {}).get('CreateWriteRender', {}).get(
            'auto_resolution_resize', {})

        if not self.autoresize:
            self.log.warning(
                "Resolution auto resize hasn't been enabled in project config. Resolution can not be overridden."
            )
            return attr_defs

        resolutions = get_available_resolutions(
            project_name=project_name,
            project_settings=project_settings
        )
        if resolutions:
            self.resolutions = resolutions
            attr_defs.append(
                EnumDef(
                    "resolution",
                    items=resolutions,
                    default=resolutions[0],
                    label="Resolution",
                )
            )
        return attr_defs

    def get_instance_attr_defs(self):
        attrs = super().get_instance_attr_defs()
        return attrs + [
            EnumDef(
                "resolution",
                items=self.resolutions,
                default=self.resolution,
                label="Resolution",
            )
        ] if self.resolutions else []

    def create_instance_node(self, subset_name, instance_data):
        # add fpath_template
        write_data = {
            "creator": self.__class__.__name__,
            "subset": subset_name,
            "fpath_template": self.temp_rendering_path_template
        }

        write_data.update(instance_data)

        width, height = self._get_width_and_height()
        if self.autoresize:
            self.add_autoresize_prenodes(width, height)

        self.log.debug(">>>>>>> : {}".format(self.instance_attributes))
        self.log.debug(">>>>>>> : {}".format(self.get_linked_knobs()))
        self.log.debug(">>>>>>> : {}".format(self.prenodes))

        # TODO : giving width and height here doesn't seem to update any values later
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

        self.integrate_links(created_node, outputs=False)

        return created_node

    def _get_width_and_height(self):
        if self.selected_node and not self.resolution:
            width, height = (self.selected_node.width(), self.selected_node.height())
        elif self.resolution:
            width, height = extract_width_and_height(self.resolution)
            self.log.warning(width)
            self.log.warning(height)
        else:
            actual_format = nuke.root().knob('format').value()
            width, height = (actual_format.width(), actual_format.height())

        return width, height

    def add_autoresize_prenodes(self, width, height):
        custom_res = get_custom_res(width, height)
        self.prenodes[AUTORESIZE_LABEL] = {
            "nodeclass": "Reformat",
            "dependent": list(self.prenodes.keys())[0] if self.prenodes else [],
            "knobs": [
                {
                    "type": "Text",
                    "name": "format",
                    "value": custom_res
                }
            ]
        }

    def create(self, subset_name, instance_data, pre_create_data):
        settings = get_project_settings(get_current_project_name()).get("nuke")
        use_backdrop_general = settings["general"].get("use_backdrop_loader_creator", True)
        use_backdrop = settings["create"]["CreateWriteRender"].get("use_backdrop_loader_creator", True)
        backdrop_padding = settings["create"]["CreateWriteRender"].get("backdrop_padding", 150)
     
        nodes_in_main_backdrops = []
        if use_backdrop and use_backdrop_general:
            nodes_in_main_backdrops = pre_organize_by_backdrop()
        # pass values from precreate to instance
        self.pass_pre_attributes_to_instance(
            instance_data,
            pre_create_data,
            [
                "render_target"
            ]
        )

        self.resolution = pre_create_data.get('resolution')

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
            
            if use_backdrop and use_backdrop_general:
                main_backdrop, storage_backdrop, subset_group, nodes = organize_by_backdrop(
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
            self.set_group_attr(instance_node)

            return instance

        except Exception as e:
            raise napi.NukeCreatorError("Creator error: {}".format(e))
