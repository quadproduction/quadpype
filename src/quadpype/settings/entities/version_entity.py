from quadpype.lib.version import (
    PackageHandler,
)
from .input_entities import TextEntity
from .lib import (
    NOT_SET
)
from .exceptions import BaseInvalidValue

class PackageVersionEntity(TextEntity):
    """Entity to store Package version to use.

    Settings created on another machine may affect available versions
    on current user's machine. Text input element is provided to explicitly
    set version not yet showing up the user's machine.

    It is possible to enter empty string. In that case is used any latest
    version. Any other string must match regex of Package version semantic.
    """
    schema_types = ["package-version"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value_hints = []

    def _item_initialization(self):
        super(PackageVersionEntity, self)._item_initialization()
        self.multiline = False
        self.placeholder_text = "Latest"

    def set_override_state(self, state, *args, **kwargs):
        """Update value hints for UI purposes."""
        self.value_hints = []

        super(PackageVersionEntity, self).set_override_state(
            state, *args, **kwargs
        )

    def convert_to_valid_type(self, value):
        """Add validation of version regex."""
        if value and value is not NOT_SET:
            if not PackageHandler.get_version_from_str(value):
                raise BaseInvalidValue(
                    "Value \"{}\"is not valid version format.".format(
                        value
                    ),
                    self.path
                )
        return super(PackageVersionEntity, self).convert_to_valid_type(value)
