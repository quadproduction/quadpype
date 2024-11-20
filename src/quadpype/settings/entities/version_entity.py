import os
from quadpype.lib.version import (
    QuadPypeVersion
)
from quadpype.lib.settings import (
    get_local_quadpype_path
)
from .input_entities import TextEntity
from .lib import (
    OverrideState,
    NOT_SET
)
from .exceptions import BaseInvalidValue

class QuadPypeVersionInput(TextEntity):
    """Entity to store QuadPype version to use.

    Settings created on another machine may affect available versions
    on current user's machine. Text input element is provided to explicitly
    set version not yet showing up the user's machine.

    It is possible to enter empty string. In that case is used any latest
    version. Any other string must match regex of QuadPype version semantic.
    """
    def _item_initialization(self):
        super(QuadPypeVersionInput, self)._item_initialization()
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
            value_hints = list(self._get_quadpype_versions())

        self.value_hints = value_hints

        super(QuadPypeVersionInput, self).set_override_state(
            state, *args, **kwargs
        )

    def convert_to_valid_type(self, value):
        """Add validation of version regex."""
        if value and value is not NOT_SET:
            if not QuadPypeVersion().version_in_str(value):
                raise BaseInvalidValue(
                    "Value \"{}\"is not valid version format.".format(
                        value
                    ),
                    self.path
                )
        return super(QuadPypeVersionInput, self).convert_to_valid_type(value)


class VersionsInputEntity(QuadPypeVersionInput):
    """Entity meant only for global settings to define production version."""
    schema_types = ["versions-text"]

    def _get_quadpype_versions(self):
        root_path = os.getenv("QUADPYPE_ROOT")
        local_path = get_local_quadpype_path()
        remote_path = os.getenv("QUADPYPE_PATH")
        temp_version = QuadPypeVersion(path=root_path, local_path=local_path, remote_path=remote_path)

        versions = []

        installed_version = temp_version.get_installed_version()
        remote_versions = temp_version.get_remote_versions(excluded_str_versions=[str(installed_version)])
        versions.append(str(installed_version))
        for version in remote_versions:
            versions.append(str(version))

        return sorted(versions)
