import re

from pathlib import Path


from quadpype.settings import get_project_settings
from quadpype.lib import BoolDef, filter_profiles, StringTemplate
from quadpype.pipeline.anatomy import Anatomy
from quadpype.hosts.aftereffects import api
from quadpype.hosts.aftereffects.api.lib import get_unique_number
from quadpype.hosts.aftereffects.api.json_loader import load_content, apply_intervals
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
    representations = ["*"]
    apply_interval_default=True

    @classmethod
    def get_options(cls, contexts):
        return [
            BoolDef("apply_interval", label="Apply interval", default=cls.apply_interval_default)
        ]

    def load(self, context, name=None, namespace=None, data=None):
        stub = self.get_stub()
        path = self.filepath_from_context(context)
        project_name = context['project']['name']
        repr_cont = context["representation"]["context"]
        repre_task_name = repr_cont.get('task', {}).get('name', None)
        frame = repr_cont.get("frame", None)
        template_data = format_data(
            original_data=context['representation'],
            filter_variant=True,
            app=get_current_host_name()
        )

        # Determine if the imported file is a PSD file (Special case)
        is_psd = Path(path).suffix == '.psd'

        layers = stub.get_items(comps=True, folders=True, footages=True)
        existing_layers = [layer.name for layer in layers]

        name = "{}_{}".format(context["asset"]["name"], name)
        unique_number = get_unique_number(
            existing_layers, name, is_psd=is_psd)
        comp_name = f"{name}_{unique_number}"
        comp = None

        if Path(path).suffix == '.json':
            try:
                comp = next(
                    iter(
                        comp for comp in stub.get_items(comps=True)
                        if comp.name == stub.LOADED_ICON + comp_name
                    )
                )
            except StopIteration:
                self.log.error(f"Can not retrieve comp named {comp_name} in scene.")

            self.load_json(stub, template_data, project_name, comp.id, repre_task_name)

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

        if not path:
            repr_id = context["representation"]["_id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return

        if is_psd:
            import_options['ImportAsType'] = 'ImportAsType.COMP'
            comp = stub.import_file_with_dialog(
                path,
                stub.LOADED_ICON + comp_name,
                import_options
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

        self[:] = [comp]
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

        if data.get(
            'apply_interval',
            self.apply_interval_default
        ) and frame:
            self.load_json(stub, template_data, project_name, comp.id, repre_task_name)

        return api.containerise(
            name,
            namespace,
            comp,
            context,
            self.__class__.__name__
        )

    def load_json(self, stub, template_data, project_name, comp_id, repre_task_name=None):
        if not repre_task_name:
            self.log.error("Can not retrieve task_name for representation context. Abort json loading.")

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

        json_content = load_content(json_path, self.log)
        apply_intervals(json_content, comp_id, stub, self.log)

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
