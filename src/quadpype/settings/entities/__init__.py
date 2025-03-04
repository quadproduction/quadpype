"""QuadPype Settings

Settings define how QuadPype and it's modules behave. They became main
component of dynamism.

QuadPype settings (ATM) have 3 layers:
1.) Defaults - defined in code
2.) Studio overrides - values that are applied on default that may modify only
    some values or None, result can be called "studio settings"
3.) Project overrides - values that are applied on studio settings, may modify
    some values or None and may modify values that are not modified in studio
    overrides

To be able do these overrides it is required to store metadata defying which
data are applied and how. Because of that it is not possible to modify
overrides manually and expect it would work right.

Structure of settings is defined with schemas. Schemas have defined structure
and possible types with possible attributes (Schemas and their description
can be found in "./schemas/README.md").

To modify settings it's recommended to use UI settings tool which can easily
visuallise how values are applied.

With help of setting entities it is possible to modify settings from code.

QuadPype has (ATM) 2 types of settings:
1.) Global settings - global settings, don't have project overrides
2.) Project settings - project specific settings

Startpoint is root entity that cares about access to other setting entities
in their scope. To be able work with entities it is required to understand
setting schemas and their structure. It is possible to work with dictionary
and list entities as with standard python objects.
"""

from .exceptions import (
    SchemaError,
    DefaultsNotDefined,
    StudioDefaultsNotDefined,
    BaseInvalidValue,
    InvalidValueType,
    InvalidKeySymbols,
    SchemaMissingFileInfo,
    SchemeGroupHierarchyBug,
    SchemaDuplicatedKeys,
    SchemaDuplicatedEnvGroupKeys,
    SchemaTemplateMissingKeys
)
from .lib import (
    NOT_SET,
    OverrideState
)
from .base_entity import (
    BaseEntity,
    GUIEntity,
    BaseItemEntity,
    ItemEntity
)

from .root_entities import (
    GlobalSettingsEntity,
    ProjectSettingsEntity
)

from .item_entities import (
    PathEntity,
    ListStrictEntity
)

from .input_entities import (
    EndpointEntity,
    InputEntity,

    NumberEntity,
    BoolEntity,
    TextEntity,
    PasswordEntity,
    PathInput,
    RawJsonEntity
)
from .color_entity import ColorEntity
from .enum_entity import (
    BaseEnumEntity,
    EnumEntity,
    HostsEnumEntity,
    AppsEnumEntity,
    ToolsEnumEntity,
    TaskTypeEnumEntity,
    DeadlineUrlEnumEntity,
    DeadlineLimitsPluginEnumEntity,
    DeadlinePoolsEnumEntity,
    AnatomyTemplatesEnumEntity,
    ShotgridUrlEnumEntity,
    FtrackTaskStatusesEnumEntity
)

from .list_entity import ListEntity
from .dict_immutable_keys_entity import (
    DictImmutableKeysEntity,
    RootsDictEntity,
    SyncServerSites
)
from .dict_mutable_keys_entity import DictMutableKeysEntity
from .dict_conditional import (
    DictConditionalEntity,
    SyncServerProviders
)

from .anatomy_entities import AnatomyEntity
from .version_entity import PackageVersionEntity

__all__ = (
    "DefaultsNotDefined",
    "StudioDefaultsNotDefined",
    "BaseInvalidValue",
    "InvalidValueType",
    "InvalidKeySymbols",
    "SchemaMissingFileInfo",
    "SchemeGroupHierarchyBug",
    "SchemaDuplicatedKeys",
    "SchemaDuplicatedEnvGroupKeys",
    "SchemaTemplateMissingKeys",

    "NOT_SET",
    "OverrideState",

    "BaseEntity",
    "GUIEntity",
    "BaseItemEntity",
    "ItemEntity",

    "GlobalSettingsEntity",
    "ProjectSettingsEntity",

    "PathEntity",
    "ListStrictEntity",

    "EndpointEntity",
    "InputEntity",

    "NumberEntity",
    "BoolEntity",
    "TextEntity",
    "PasswordEntity",
    "PathInput",
    "RawJsonEntity",

    "ColorEntity",

    "BaseEnumEntity",
    "EnumEntity",
    "HostsEnumEntity",
    "AppsEnumEntity",
    "ToolsEnumEntity",
    "TaskTypeEnumEntity",
    "DeadlineUrlEnumEntity",
    "DeadlineLimitsPluginEnumEntity",
    "DeadlinePoolsEnumEntity",
    "ShotgridUrlEnumEntity",
    "FtrackTaskStatusesEnumEntity",
    "AnatomyTemplatesEnumEntity",

    "ListEntity",

    "DictImmutableKeysEntity",
    "RootsDictEntity",
    "SyncServerSites",

    "DictMutableKeysEntity",

    "DictConditionalEntity",
    "SyncServerProviders",

    "AnatomyEntity",

    "PackageVersionEntity",
)
