import pyblish.api


class CollectRenderLayersData(pyblish.api.ContextPlugin):
    """Collect Anatomy object into Context.

    Order offset could be changed to '-0.45'.
    """

    order = pyblish.api.CollectorOrder + 0.491
    label = "Collect Render Layers data"

    @staticmethod
    def _get_all_families(instance):
        return set([instance.data["family"]] + instance.data.get("families", []))

    def process(self, context):
        for instance in context:
            if "render" not in self._get_all_families(instance):
                continue

            instance.data['render_layers'] = [
                {
                    'name': browsed_instance.data['name'],
                    'version': browsed_instance.data['version']
                }
                for browsed_instance in context if (
                        "renderlayer" in self._get_all_families(browsed_instance)
                        and instance.data['asset'] == browsed_instance.data['asset']
                )
            ]

            self.log.debug(
                f"Render layers added to render instance {instance.data['name']} :\n- " +
                "\n- ".join(
                    [
                        f"{ins['name']} (v{ins['version']:03d})"
                        for ins in instance.data['render_layers']
                    ]
                )
            )
