import pyblish.api


class CollectRenderLayersData(pyblish.api.ContextPlugin):
    """Collect render layers from Context and add them to render instance.
    """

    order = pyblish.api.CollectorOrder + 0.491
    label = "Collect Render Layers data"
    families = ["render"]
    hosts = ["blender"]

    @staticmethod
    def _get_all_families(instance):
        return set([instance.data["family"]] + instance.data.get("families", []))

    @staticmethod
    def has_render_layers_data(instance):
        return instance.data.get("render_layers", False)

    def is_render_family(self, instance):
        return "render" in self._get_all_families(instance)

    def process(self, context):
        for instance in context:
            instance_name = instance.data['name']

            if not self.is_render_family(instance):
                self.log.warning(f"Given instance named '{instance_name}' does not have 'render' family.")
                continue

            if self.has_render_layers_data(instance):
                self.log.warning(f"Given instance named '{instance_name}' already has render layers : {instance.data['render_layers']}")
                continue

            render_layers = [
                {
                    'name': browsed_instance.data['name'],
                    'version': browsed_instance.data['version']
                }
                for browsed_instance in context if (
                        "renderlayer" in self._get_all_families(browsed_instance)
                        and instance.data['asset'] == browsed_instance.data['asset']
                )
            ]

            if not render_layers:
                continue

            instance.data['render_layers'] = render_layers

            self.log.debug(
                f"Render layers added to render instance {instance_name} :\n- " +
                "\n- ".join(
                    [
                        f"{render_layer['name']} (v{render_layer['version']:03d})"
                        for render_layer in render_layers
                    ]
                )
            )
