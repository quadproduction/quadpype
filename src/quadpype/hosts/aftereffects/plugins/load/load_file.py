import json
import re
import threading
from pathlib import Path

from quadpype.lib import BoolDef, filter_profiles, StringTemplate
from quadpype.hosts.aftereffects.api.json_loader import load_content, apply_intervals

from quadpype.lib import get_user_settings
from quadpype.settings import get_project_settings
from quadpype.pipeline.anatomy import Anatomy
from quadpype.hosts.aftereffects import api
from quadpype.hosts.aftereffects.api.lib import get_unique_number
from quadpype.hosts.aftereffects.api.automate import import_file_dialog_clic
from quadpype.widgets.message_window import Window

from quadpype.widgets.message_notification import notify_message

from quadpype.hosts.aftereffects.api.folder_hierarchy import (
    create_folders_from_hierarchy,
    get_last_folder_from_first_template,
    find_folder
)

from quadpype.pipeline.publish.lib import get_template_name_profiles

from quadpype.pipeline import (
    get_task_hierarchy_templates,
    get_representation_path,
    get_current_context,
    get_current_host_name,
    get_resolved_name,
    format_data,
    split_hierarchy
)


class FileLoader(api.AfterEffectsLoader):
    """Load images

    Stores the imported asset in a container named after the asset.
    """
    label = "Load file"
    icon = "file-image-o"
    color = "green"

    families = ["image",
                "plate",
                "render",
                "prerender",
                "review",
                "audio",
                "workfile"]
    representations = ["*", "-json"]
    apply_interval_default = True

    @classmethod
    def get_options(cls, contexts):
        return [
            BoolDef("apply_interval", label="Apply interval", default=cls.apply_interval_default)
        ]

    def load(self, context, name=None, namespace=None, data=None):
        path = self.filepath_from_context(context)
        if not path:
            repr_id = context["representation"]["_id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return

        stub = self.get_stub()
        project_name = context['project']['name']
        repr_cont = context["representation"]["context"]
        repre_task_name = repr_cont.get('task', {}).get('name', None)
        frame = repr_cont.get("frame", None)
        version_data = context["version"]["data"]
        frame_start = version_data.get("frameStart", None)
        frame_end = version_data.get("frameEnd", None)

        # Determine if the imported file is a PSD file (Special case)
        path = Path(path)
        is_psd = path.suffix == '.psd'
        path = str(path.resolve())

        layers = stub.get_items(comps=True, folders=True, footages=True)
        existing_layers = [layer.name for layer in layers]

        name = "{}_{}".format(context["asset"]["name"], name)
        unique_number = get_unique_number(
            existing_layers, name, is_psd=is_psd)
        comp_name = f"{name}_{unique_number}"

        import_options = {}
        try:
            import_options['fps'] = context['asset']['data']['fps']
        except KeyError:
            self.log.warning(f"Can't retrieve fps information for asset {name}. Will try to load data from project.")
            try:
                import_options['fps'] = Anatomy(project_name)['attributes']['fps']
            except KeyError:
                self.log.warning(
                    f"Can't retrieve fps information for project {project_name}. "
                    f"Frame rate will not be set at import."
                )

        if len(context["representation"]["files"]) > 1:
            import_options['sequence'] = True

        self.log.info("Loading asset...")
        if is_psd:
            import_options['ImportAsType'] = 'ImportAsType.COMP'
            user_override_auto_clic = get_user_settings().get('general', {}).get('enable_auto_clic_scripts', True)
            load_settings = get_project_settings(project_name).get(get_current_host_name(), {}).get('load', {})
            auto_clic = load_settings.get('auto_clic_import_dialog')
            if auto_clic and user_override_auto_clic:
                auto_clic_thread = self.trigger_auto_clic_thread(
                    load_settings.get('attempts_number', 3),
                    data.get("display_window", True)
                )
                comp = stub.import_file_with_dialog(
                    path,
                    stub.LOADED_ICON + comp_name,
                    import_options
                )
                auto_clic_thread.join()

                if comp and data.get("display_window", True):
                    notify_message(
                        "AE Import File Succeed",
                        "Import has ended with success !"
                    )

            else:
                comp = stub.import_file_with_dialog(
                    path,
                    stub.LOADED_ICON + comp_name,
                    import_options
                )
            stub.set_comp_properties(comp_id=comp.id,
                                     start=frame_start,
                                     duration=frame_end,
                                     frame_rate=import_options['fps'],
                                     width=None,
                                     height=None
                                     )
            stub.stretch_layers_in_comp(comp_id=comp.id,
                                        duration=frame_end,
                                        frame_rate=import_options['fps']
                                        )

        else:
            if frame:
                import_options['sequence'] = True

            comp = stub.import_file(path, stub.LOADED_ICON + comp_name, import_options)

        if not comp:
            if frame:
                padding = len(frame)
                path = path.replace(frame, "#" * padding)

            self.log.warning(
                "Representation `{}` is failing to load".format(path))
            self.log.warning("Check host app for alert error.")
            return

        self.log.info("Asset has been loaded with success.")

        template_data, template_folder = self.get_folder_and_data_template(
            context['representation'],
            data.get("asset_name_override", None)
        )
        if template_folder:
            folders_hierarchy = self.get_folder_hierarchy(template_data, template_folder, unique_number)
            self.create_folders(stub, folders_hierarchy, comp, stub.LOADED_ICON + comp_name, parent_item=is_psd)

            self.log.info("Hierarchy has been created.")

        if self.apply_interval_asked(data, frame, is_psd):
            self.apply_intervals(stub, template_data, project_name, comp.id, repre_task_name)

        self[:] = [comp]
        namespace = namespace or comp_name

        return api.containerise(
            name,
            namespace,
            comp,
            context,
            self.__class__.__name__,
            options=data
        )

    @staticmethod
    def get_folder_and_data_template(representation, asset_name_override):
        template_data = format_data(
            original_data=representation,
            filter_variant=True,
            app=get_current_host_name(),
            asset_name_override=asset_name_override
        )
        return template_data, get_task_hierarchy_templates(
            template_data,
            task=representation["context"]["task"]['name']
        )

    @staticmethod
    def get_folder_hierarchy(template_data, folder_templates, unique_number):
        return [
            get_resolved_name(
                data=template_data,
                template=template,
                numbering=unique_number
            )
            for template in folder_templates
        ]

    @staticmethod
    def create_folders(stub, folders_hierarchy, comp, parent_folder_name, parent_item=False):
        create_folders_from_hierarchy(folders_hierarchy)
        last_folder = find_folder(get_last_folder_from_first_template(folders_hierarchy))
        stub.parent_items(comp.id, last_folder.id)

        if not parent_item:
            return

        psd_folder = find_folder(parent_folder_name)
        stub.parent_items(psd_folder.id, last_folder.id)

    def apply_interval_asked(self, data, frame, is_psd):
        return data.get('apply_interval', self.apply_interval_default) and frame and is_psd

    def apply_intervals(self, stub, template_data, project_name, comp_id, repre_task_name):
        self.log.info("Applying intervals from json file...")
        profiles = get_template_name_profiles(
            project_name, get_project_settings(project_name), self.log
        )

        template_data.update(
            {
                'families': 'render',
                'task_types': repre_task_name,
                'ext': 'json'
            }
        )
        del template_data['frame']
        profile = filter_profiles(profiles, template_data)

        anatomy = Anatomy()
        templates = anatomy.templates.get(profile['template_name'])
        json_path = StringTemplate.format_template(templates['path'], template_data)
        if not json_path:
            self.log.warning("There is no json file to apply for this asset. Abort applying intervals.")
            return

        json_content = load_content(json_path, self.log)
        if not json_content:
            self.log.error("Can not load content from retrieved json. Abort applying intervals.")
            return

        apply_intervals(json_content, comp_id, stub, self.log)

    def trigger_auto_clic_thread(self, attempts_number, display_window=True):
        if display_window:
            Window(
                parent=None,
                title='Import File',
                message='<p>File will be automatically imported with mouse automation.<br/>'
                        '<b>Please do not touch your mouse or your keyboard !</b></p>'
                        '<p><i>Process should ends in less than 10 seconds. If nothing happens, '
                        'it means that something has gone wrong, and you will need to end '
                        'process by yourself.</i></p>'
                        '<p><i>Check your os notifications to monitor process results.</p></i>',
                level="warning"
            )

        auto_clic_thread = threading.Thread(
            target=self.launch_auto_click,
            args=(attempts_number,)
        )
        auto_clic_thread.start()
        return auto_clic_thread

    def launch_auto_click(self, tries):
        import time
        time.sleep(.5)
        for _ in range(tries):
            success = import_file_dialog_clic(self.log)
            if success:
                return

        self.log.warning(f"Maximum tries value {tries} reached.")
        notify_message(
            "AE Import File Failed",
            "Auto clic has failed. You will need to end import file process by yourself."
        )

    def update(self, container, representation):
        """ Switch asset or change version """
        stub = self.get_stub()
        layer = container.pop("layer")
        unique_number = container.get('version')

        context = representation.get("context", {})

        namespace_from_container = re.sub(r'_\d{3}$', '',
                                          container["namespace"])
        layer_name = "{}_{}".format(context["asset"], context["subset"])
        project_name = context.get('project', {}).get('name', None)

        # switching assets
        if namespace_from_container != layer_name:
            layers = stub.get_items(comps=True)
            existing_layers = [layer.name for layer in layers]
            name = "{}_{}".format(context["asset"], context["subset"])
            unique_number = get_unique_number(
                existing_layers, name)
            layer_name = f"{name}_{unique_number}"

        else:  # switching version - keep same name
            layer_name = container["namespace"]
        path = get_representation_path(representation)
        # with aftereffects.maintained_selection():  # TODO

        # Convert into a Path object
        path = Path(path)
        is_psd = path.suffix == '.psd'
        path = str(path.resolve())
        parent_folder = stub.get_item_parent(layer.id)

        if is_psd:
            load_settings = get_project_settings(project_name).get(get_current_host_name(), {}).get('load', {})
            auto_clic = load_settings.get('auto_clic_import_dialog')

            if auto_clic:
                auto_clic_thread = self.trigger_auto_clic_thread(load_settings.get('attempts_number', 3))

                result = stub.replace_item(layer.id, path, stub.LOADED_ICON + layer_name)

                auto_clic_thread.join()

                # If result is an empty string, it means that everything went well
                if result == '':
                    self.notify_import_result("Import has ended with success !")

        else:
            stub.replace_item(layer.id, path, stub.LOADED_ICON + layer_name)

        stub.imprint(
            layer.id,
            {
                "representation": str(representation["_id"]),
                "name": context["subset"],
                "namespace": layer_name
            }
        )

        template_data, template_folder = self.get_folder_and_data_template(representation)
        if template_folder:
            folders_hierarchy = self.get_folder_hierarchy(template_data, template_folder, unique_number)
            self.create_folders(stub, folders_hierarchy, layer, stub.LOADED_ICON + layer_name, parent_item=is_psd)

            if not parent_folder:
                return

            stub.delete_hierarchy(parent_folder.id)

        if self.apply_interval_asked(
                data=json.loads(container.get('options', '{}')),
                frame=representation["context"].get("frame", None),
                is_psd=is_psd
        ):
            self.apply_intervals(
                stub=stub,
                template_data=template_data,
                project_name=project_name,
                comp_id=layer.id,
                repre_task_name=representation["context"].get('task', {}).get('name', None)
            )

    def remove(self, container):
        """
            Removes element from scene: deletes layer + removes from Headline
        Args:
            container (dict): container to be removed - used to get layer_id
        """
        stub = self.get_stub()
        layer = container.pop("layer")
        namespace = container.pop("namespace")

        stub.imprint(layer.id, {})
        stub.delete_item(layer.id)

        psd_folder = find_folder(stub.LOADED_ICON + namespace)
        if psd_folder:
            stub.delete_item_with_hierarchy(psd_folder.id)

    def switch(self, container, representation):
        self.update(container, representation)
