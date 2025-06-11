import re
import threading
from pathlib import Path

from quadpype.pipeline import (
    get_representation_path,
    get_current_context,
    get_current_host_name,
)
from quadpype.settings import get_project_settings
from quadpype.pipeline.anatomy import Anatomy
from quadpype.hosts.aftereffects import api
from quadpype.hosts.aftereffects.api.lib import get_unique_number
from quadpype.hosts.aftereffects.api.automate import import_file_dialog_clic
from quadpype.widgets.message_window import Window
from quadpype.hosts.aftereffects.api.folder_hierarchy import (
    create_folders_from_hierarchy,
    get_last_folder_from_first_template,
    find_folder
)
from quadpype.pipeline import (
    get_task_hierarchy_templates,
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
    representations = ["*"]

    def load(self, context, name=None, namespace=None, data=None):
        host_name = get_current_host_name()
        project_name = context['project']['name']
        import_options = {}

        try:
            import_options['fps'] = context['asset']['data']['fps']
        except KeyError:
            self.log.warning(f"Can't retrieve fps information for asset {name}. Will try to load data from project.")
            try:
                import_options['fps'] = Anatomy(project_name)['attributes']['fps']
            except KeyError:
                self.log.warning(f"Can't retrieve fps information for project {project_name}. Frame rate will not be set at import.")

        stub = self.get_stub()
        layers = stub.get_items(comps=True, folders=True, footages=True)
        existing_layers = [layer.name for layer in layers]

        path = self.filepath_from_context(context)
        repr_cont = context["representation"]["context"]

        if len(context["representation"]["files"]) > 1:
            import_options['sequence'] = True

        if not path:
            repr_id = context["representation"]["_id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return

        # Convert into a Path object
        path = Path(path)

        # Resolve and then get a string
        path_str = str(path.resolve())

        frame = None

        # Determine if the imported file is a PSD file (Special case)
        is_psd = path.suffix == '.psd'
        name = "{}_{}".format(context["asset"]["name"], name)
        unique_number = get_unique_number(
            existing_layers, name, is_psd=is_psd)
        comp_name = f"{name}_{unique_number}"

        if is_psd:
            import_options['ImportAsType'] = 'ImportAsType.COMP'
            load_settings = get_project_settings(project_name).get(host_name, {}).get('load', {})
            auto_clic = load_settings.get('auto_clic_import_dialog')

            if auto_clic:
                Window(
                    parent=None,
                    title='Import File',
                    message='File will be automatically imported with mouse automation. '
                            'Please do not touch your mouse or your keyboard !',
                    level="warning"
                )

                auto_clic_thread = threading.Thread(
                    target=self.launch_auto_click,
                    args=(load_settings.get('attempts_number', 3),)
                )
                auto_clic_thread.start()

                comp = stub.import_file_with_dialog(
                    path_str,
                    stub.LOADED_ICON + comp_name,
                    import_options
                )

                auto_clic_thread.join()

                Window(
                    parent=None,
                    title='Import File',
                    message='File has been imported with success. You can now reuse your mouse and keyboard.',
                    level="warning"
                )

            else:
                self.log.warning('oupsi')
                comp = stub.import_file_with_dialog(
                    path_str,
                    stub.LOADED_ICON + comp_name,
                    import_options
                )

        else:
            frame = repr_cont.get("frame")
            if frame:
                import_options['sequence'] = True

            comp = stub.import_file(path_str, stub.LOADED_ICON + comp_name, import_options)

        if not comp:
            if frame:
                padding = len(frame)
                path_str = path_str.replace(frame, "#" * padding)

            self.log.warning(
                "Representation `{}` is failing to load".format(path_str))
            self.log.warning("Check host app for alert error.")
            return

        self[:] = [comp]
        namespace = namespace or comp_name
        template_data = format_data(
            original_data=context['representation'],
            filter_variant=True,
            app=host_name
        )
        folder_templates = get_task_hierarchy_templates(
            template_data,
            task=get_current_context()['task_name']
        )

        if folder_templates:
            folders_hierarchy = [
                get_resolved_name(
                    data=template_data,
                    template=template,
                    numbering=unique_number
                )
                for template in folder_templates
            ]
            create_folders_from_hierarchy(folders_hierarchy)
            last_folder = find_folder(get_last_folder_from_first_template(folders_hierarchy))
            stub.parent_items(comp.id, last_folder.id)
            # if psd, must retrieve the folder to parent it too
            if is_psd:
                psd_folder = find_folder(stub.LOADED_ICON + comp_name)
                stub.parent_items(psd_folder.id, last_folder.id)

        return api.containerise(
            name,
            namespace,
            comp,
            context,
            self.__class__.__name__
        )

    @staticmethod
    def launch_auto_click(tries):
        for _ in range(tries):
            import_file_dialog_clic()

    def update(self, container, representation):
        """ Switch asset or change version """
        stub = self.get_stub()
        layer = container.pop("layer")

        context = representation.get("context", {})

        namespace_from_container = re.sub(r'_\d{3}$', '',
                                          container["namespace"])
        layer_name = "{}_{}".format(context["asset"], context["subset"])
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

        # Resolve and then get a string
        path_str = str(path.resolve())

        stub.replace_item(layer.id, path_str, stub.LOADED_ICON + layer_name)
        stub.imprint(
            layer.id, {"representation": str(representation["_id"]),
                       "name": context["subset"],
                       "namespace": layer_name}
        )

    def remove(self, container):
        """
            Removes element from scene: deletes layer + removes from Headline
        Args:
            container (dict): container to be removed - used to get layer_id
        """
        stub = self.get_stub()
        layer = container.pop("layer")
        stub.imprint(layer.id, {})
        stub.delete_item(layer.id)

    def switch(self, container, representation):
        self.update(container, representation)
