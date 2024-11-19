from quadpype.lib.version import (
    get_BaseVersionClass,
    get_quadpype_remote_versions,
    get_quadpype_installed_version,
    get_custom_addon_remote_versions,
    get_custom_addon_installed_version
)
from .input_entities import TextEntity
from .lib import (
    OverrideState,
    NOT_SET
)
from .exceptions import BaseInvalidValue


class VersionInput(TextEntity):
    """Entity to store the version to use.

    Settings created on another machine may affect available versions
    on current user's machine. Text input element is provided to explicitly
    set version not yet showing up the user's machine.

    It is possible to enter empty string. In that case is used any latest
    version. Any other string must match the regex version semantic.
    """
    def _item_initialization(self):
        super(VersionInput, self)._item_initialization()
        self.multiline = False
        self.placeholder_text = "Latest"
        self.value_hints = []

    def _get_quadpype_versions(self):
        """This is abstract method returning version hints for UI purposes."""
        raise NotImplementedError((
            "{} does not have implemented '_get_quadpype_versions'"
        ).format(self.__class__.__name__))

    def set_override_state(self, state, *args, **kwargs):
        """Update value hints for UI purposes."""
        value_hints = []
        if state is OverrideState.STUDIO:
            versions = self._get_quadpype_versions()
            for version in versions:
                version_str = str(version)
                if version_str not in value_hints:
                    value_hints.append(version_str)

        self.value_hints = value_hints

        super(VersionInput, self).set_override_state(
            state, *args, **kwargs
        )

    def convert_to_valid_type(self, value):
        """Add validation of version regex."""
        if value and value is not NOT_SET:
            # Check value again the version regex
            base_version_class = get_BaseVersionClass()
            if base_version_class is not None:
                if not base_version_class.version_in_str(value):
                    exception_msg = "Value \"{}\" doesn't follow the version format.".format(value)
                    raise BaseInvalidValue(exception_msg, self.path)
        return super(VersionInput, self).convert_to_valid_type(value)


class VersionsInputEntity(VersionInput):
    """Entity meant only for global settings to define production version."""
    schema_types = ["versions-text"]

    def _get_quadpype_versions(self):
        versions = get_quadpype_remote_versions()
        if versions is None:
            return []
        versions.append(get_quadpype_installed_version())
        return sorted(versions)


class AddOnInputEntity(VersionInput):
    """Entity meant only for global settings to define production version."""
    schema_types = ["custom-addon-versions-text"]

    def _get_quadpype_versions(self):
        versions = get_custom_addon_remote_versions()
        if versions is None:
            return []
        versions.append(get_custom_addon_installed_version())
        return sorted(versions)
