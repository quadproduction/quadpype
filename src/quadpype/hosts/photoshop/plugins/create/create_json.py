from quadpype.hosts.photoshop.lib import PSAutoCreator


class JsonCreator(PSAutoCreator):
    """Creates review instance which might be disabled from publishing."""
    identifier = "imagesequence"
    family = "imagesequence"
    icon = "fa.file-o"

    default_variant = "Main"

    def get_detail_description(self):
        return """Auto creator for json.

        Export all visible layers in separated files and single json file which describes Photoshop scene.
        """

    def apply_settings(self, project_settings):
        plugin_settings = (
            project_settings["photoshop"]["create"]["JsonCreator"]
        )

        self.default_variant = plugin_settings["default_variant"]
        self.active_on_create = plugin_settings["active_on_create"]
        self.enabled = plugin_settings["enabled"]
