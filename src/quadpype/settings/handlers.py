import os
import json
import copy
import collections
import datetime
from abc import ABCMeta, abstractmethod
from copy import deepcopy

import six

import quadpype.version
from quadpype.client.mongo import (
    QuadPypeMongoConnection,
    get_project_connection,
)
from quadpype.client import get_project
from quadpype.lib.pype_info import get_workstation_info


from .constants import (
    CORE_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY,
    PROJECT_SETTINGS_KEY,
    PROJECT_ANATOMY_KEY,
    M_OVERRIDDEN_KEY,

    APPS_SETTINGS_KEY
)
from ..lib import get_user_id


class SettingsStateInfo:
    """Helper state information about some settings state.

    Is used to hold information about last saved and last opened UI. Keep
    information about the time when that happened and on which machine under
    which user and on which quadpype version.

    To create current machine and time information use 'create_new' method.
    """

    timestamp_format = "%Y-%m-%d %H:%M:%S.%f"

    def __init__(
        self,
        quadpype_version,
        settings_type,
        project_name,
        timestamp,
        workstation_name,
        host_ip,
        username,
        system_name,
        user_id
    ):
        self.quadpype_version = quadpype_version
        self.settings_type = settings_type
        self.project_name = project_name

        timestamp_obj = None
        if timestamp:
            timestamp_obj = datetime.datetime.strptime(
                timestamp, self.timestamp_format
            )
        self.timestamp = timestamp
        self.timestamp_obj = timestamp_obj
        self.workstation_name = workstation_name
        self.host_ip = host_ip
        self.username = username
        self.system_name = system_name
        self.user_id = user_id

    def copy(self):
        return self.from_data(self.to_data())

    @classmethod
    def create_new(
        cls, quadpype_version, settings_type=None, project_name=None
    ):
        """Create information about this machine for current time."""

        from quadpype.lib.pype_info import get_workstation_info

        now = datetime.datetime.now()
        workstation_info = get_workstation_info()

        return cls(
            quadpype_version,
            settings_type,
            project_name,
            now.strftime(cls.timestamp_format),
            workstation_info["workstation_name"],
            workstation_info["host_ip"],
            workstation_info["username"],
            workstation_info["system_name"],
            get_user_id()
        )

    @classmethod
    def from_data(cls, data):
        """Create object from data."""

        return cls(
            data["quadpype_version"],
            data["settings_type"],
            data["project_name"],
            data["timestamp"],
            data["workstation_name"],
            data["host_ip"],
            data["username"],
            data["system_name"],
            data["user_id"]
        )

    def to_data(self):
        data = self.to_document_data()
        data.update({
            "quadpype_version": self.quadpype_version,
            "settings_type": self.settings_type,
            "project_name": self.project_name
        })
        return data

    @classmethod
    def create_new_empty(cls, quadpype_version, settings_type=None):
        return cls(
            quadpype_version,
            settings_type,
            None,
            None,
            None,
            None,
            None,
            None,
            None
        )

    @classmethod
    def from_document(cls, quadpype_version, settings_type, document):
        document = document or {}
        project_name = document.get("project_name")
        last_saved_info = document.get("last_saved_info")
        if last_saved_info:
            copy_last_saved_info = copy.deepcopy(last_saved_info)
            copy_last_saved_info.update({
                "quadpype_version": quadpype_version,
                "settings_type": settings_type,
                "project_name": project_name,
            })
            return cls.from_data(copy_last_saved_info)
        return cls(
            quadpype_version,
            settings_type,
            project_name,
            None,
            None,
            None,
            None,
            None,
            None
        )

    def to_document_data(self):
        return {
            "timestamp": self.timestamp,
            "workstation_name": self.workstation_name,
            "host_ip": self.host_ip,
            "username": self.username,
            "system_name": self.system_name,
            "user_id": self.user_id,
        }

    def get(self, key, fallback=None):
        if key:
            return getattr(self, key, fallback)
        return fallback

    def __eq__(self, other):
        if not isinstance(other, SettingsStateInfo):
            return False

        if other.timestamp_obj != self.timestamp_obj:
            return False

        return (
            self.quadpype_version == other.quadpype_version
            and self.workstation_name == other.workstation_name
            and self.host_ip == other.host_ip
            and self.username == other.username
            and self.system_name == other.system_name
            and self.user_id == other.user_id
        )


@six.add_metaclass(ABCMeta)
class SettingsHandler(object):
    core_keys = {
        "quadpype_path",
        "local_quadpype_path",
        "log_to_server",
        "disk_mapping",
        "production_version",
        "staging_version"
    }

    @abstractmethod
    def save_studio_settings(self, data):
        """Save studio overrides of global settings.

        Do not use to store whole glboal settings data with defaults but only
        it's overrides with metadata defining how overrides should be applied
        in load function. For loading should be used function
        `studio_global_settings`.

        Args:
            data(dict): Data of studio overrides with override metadata.
        """
        pass

    @abstractmethod
    def save_project_settings(self, project_name, overrides):
        """Save studio overrides of project settings.

        Data are saved for specific project or as defaults for all projects.

        Do not use to store whole project settings data with defaults but only
        it's overrides with metadata defining how overrides should be applied
        in load function. For loading should be used function
        `get_studio_project_settings_overrides` for global project settings
        and `get_project_settings_overrides` for project specific settings.

        Args:
            project_name(str, null): Project name for which overrides are
                or None for global settings.
            overrides(dict): Data of project overrides with override metadata.
        """
        pass

    @abstractmethod
    def save_project_anatomy(self, project_name, anatomy_data):
        """Save studio overrides of project anatomy data.

        Args:
            project_name(str, null): Project name for which overrides are
                or None for global settings.
            anatomy_data(dict): Data of project overrides with override metadata.
        """
        pass

    @abstractmethod
    def save_change_log(self, project_name, changes, settings_type):
        """Stores changes to settings to separate logging collection.

        Args:
            project_name(str, null): Project name for which overrides are
                or None for global settings.
            changes(dict): Data of project overrides with override metadata.
            settings_type (str): global|project|anatomy
        """
        pass

    @abstractmethod
    def get_studio_global_settings_overrides(self, return_version):
        """Studio overrides of global settings."""
        pass

    @abstractmethod
    def get_studio_project_settings_overrides(self, return_version):
        """Studio overrides of default project settings."""
        pass

    @abstractmethod
    def get_studio_project_anatomy_overrides(self, return_version):
        """Studio overrides of default project anatomy data."""
        pass

    @abstractmethod
    def get_project_settings_overrides(self, project_name, return_version):
        """Studio overrides of project settings for specific project.

        Args:
            project_name(str): Name of project for which data should be loaded.
            return_version(bool): Version string will be added to output.

        Returns:
            dict: Only overrides for entered project, may be empty dictionary.
        """
        pass

    @abstractmethod
    def get_project_anatomy_overrides(self, project_name, return_version):
        """Studio overrides of project anatomy for specific project.

        Args:
            project_name(str): Name of project for which data should be loaded.
            return_version(bool): Version string will be added to output.

        Returns:
            dict: Only overrides for entered project, may be empty dictionary.
        """
        pass

    # Getters for specific version overrides
    @abstractmethod
    def get_studio_global_settings_overrides_for_version(self, version):
        """Studio global settings overrides for specific version.

        Args:
            version(str): QuadPype version for which settings should be
                returned.

        Returns:
            None: If the version does not have global settings overrides.
            dict: Document with overrides data.
        """
        pass

    @abstractmethod
    def get_studio_project_anatomy_overrides_for_version(self, version):
        """Studio project anatomy overrides for specific version.

        Args:
            version(str): QuadPype version for which settings should be
                returned.

        Returns:
            None: If the version does not have project anatomy overrides.
            dict: Document with overrides data.
        """
        pass

    @abstractmethod
    def get_studio_project_settings_overrides_for_version(self, version):
        """Studio project settings overrides for specific version.

        Args:
            version(str): QuadPype version for which settings should be
                returned.

        Returns:
            None: If the version does not have project settings overrides.
            dict: Document with overrides data.
        """
        pass

    @abstractmethod
    def get_project_settings_overrides_for_version(
        self, project_name, version
    ):
        """Studio project settings overrides for specific project and version.

        Args:
            project_name(str): Name of project for which the overrides should
                be loaded.
            version(str): QuadPype version for which settings should be
                returned.

        Returns:
            None: If the version does not have project settings overrides.
            dict: Document with overrides data.
        """
        pass

    @abstractmethod
    def get_core_settings(self):
        """Studio core settings available across versions.

        Output must contain all keys from 'core_keys'. If value is not set
        the output value should be 'None'.

        Returns:
            Dict[str, Any]: Global settings same across versions.
        """

        pass

    # Clear methods - per version
    # - clearing may be helpfully when a version settings were created for
    #   testing purposes
    @abstractmethod
    def clear_studio_global_settings_overrides_for_version(self, version):
        """Remove studio global settings overrides for specific version.

        If version is not available then skip processing.
        """
        pass

    @abstractmethod
    def clear_studio_project_settings_overrides_for_version(self, version):
        """Remove studio project settings overrides for specific version.

        If version is not available then skip processing.
        """
        pass

    @abstractmethod
    def clear_studio_project_anatomy_overrides_for_version(self, version):
        """Remove studio project anatomy overrides for specific version.

        If version is not available then skip processing.
        """
        pass

    @abstractmethod
    def clear_project_settings_overrides_for_version(
        self, version, project_name
    ):
        """Remove studio project settings overrides for project and version.

        If version is not available then skip processing.
        """
        pass

    # Get versions that are available for each type of settings
    @abstractmethod
    def get_available_studio_global_settings_overrides_versions(
        self, sorted=None
    ):
        """QuadPype versions that have any studio global settings overrides.

        Returns:
            list<str>: QuadPype versions strings.
        """
        pass

    @abstractmethod
    def get_available_studio_project_anatomy_overrides_versions(
        self, sorted=None
    ):
        """QuadPype versions that have any studio project anatomy overrides.

        Returns:
            List[str]: QuadPype versions strings.
        """
        pass

    @abstractmethod
    def get_available_studio_project_settings_overrides_versions(
        self, sorted=None
    ):
        """QuadPype versions that have any studio project settings overrides.

        Returns:
            List[str]: QuadPype versions strings.
        """
        pass

    @abstractmethod
    def get_available_project_settings_overrides_versions(
        self, project_name, sorted=None
    ):
        """QuadPype versions that have any project settings overrides.

        Args:
            project_name(str): Name of project.

        Returns:
            List[str]: QuadPype versions strings.
        """

        pass

    @abstractmethod
    def get_global_settings_last_saved_info(self):
        """State of last global settings overrides at the moment when called.

        This method must provide most recent data so using cached data is not
        the way.

        Returns:
            SettingsStateInfo: Information about global settings overrides.
        """

        pass

    @abstractmethod
    def get_project_settings_last_saved_info(self, project_name):
        """State of last project settings overrides at the moment when called.

        This method must provide most recent data so using cached data is not
        the way.

        Args:
            project_name (Union[None, str]): Project name for which state
                should be returned.

        Returns:
            SettingsStateInfo: Information about project settings overrides.
        """

        pass

    # UI related calls
    @abstractmethod
    def get_last_opened_info(self):
        """Get information about last opened UI.

        Last opened UI is empty if there is noone who would have opened UI at
        the moment when called.

        Returns:
            Union[None, SettingsStateInfo]: Information about machine who had
                opened Settings UI.
        """

        pass

    @abstractmethod
    def opened_settings_ui(self):
        """Callback called when settings UI is opened.

        Information about this machine must be available when
        'get_last_opened_info' is called from anywhere until
        'closed_settings_ui' is called again.

        Returns:
            SettingsStateInfo: Object representing information about this
                machine. Must be passed to 'closed_settings_ui' when finished.
        """

        pass

    @abstractmethod
    def closed_settings_ui(self, info_obj):
        """Callback called when settings UI is closed.

        From the moment this method is called the information about this
        machine is removed and no more available when 'get_last_opened_info'
        is called.

        Callback should validate if this machine is still stored as opened ui
        before changing any value.

        Args:
            info_obj (SettingsStateInfo): Object created when
                'opened_settings_ui' was called.
        """

        pass


@six.add_metaclass(ABCMeta)
class UserHandler:
    """Handler using to store and load user info & settings.

    User settings are specific modifications that modify how
    global and project settings look on the workstation and only there.
    """
    user_profile_template = {
        "user_id": "",
        "role": "user",
        "first_connection": datetime.datetime.now(),
        "last_connection": datetime.datetime.now(),
        "last_workstation_profile_index": 0,
        "workstation_profiles": [],
        "settings": {}
    }

    @abstractmethod
    def save_user_settings(self, data):
        """Save local data of user settings.

        Args:
            data(dict): Data of local data with override metadata.
        """
        pass

    @abstractmethod
    def get_user_settings(self):
        """User overrides of global settings."""
        pass

    @abstractmethod
    def create_user_profile(self):
        """Create a new entry in the database for this new user."""
        pass

    @abstractmethod
    def get_user_profile(self):
        """Profile of the user in the database, including settings overrides."""
        pass

    @abstractmethod
    def update_user_profile_on_startup(self):
        """Update the user profile on startup."""
        pass


class CacheValues:
    cache_lifetime = 10

    def __init__(self):
        self.data = None
        self.creation_time = None
        self.version = None
        self.last_saved_info = None

    def data_copy(self):
        if not self.data:
            return {}
        return copy.deepcopy(self.data)

    def update_data(self, data, version):
        self.data = data
        self.creation_time = datetime.datetime.now()
        self.version = version

    def update_last_saved_info(self, last_saved_info):
        self.last_saved_info = last_saved_info

    def update_from_document(self, document, version):
        data = {}
        if document:
            if "data" in document:
                data = document["data"]
            elif "value" in document:
                value = document["value"]
                if value:
                    data = json.loads(value)

        self.data = data
        self.version = version

    def to_json_string(self):
        return json.dumps(self.data or {})

    @property
    def is_outdated(self):
        if self.creation_time is None:
            return True
        delta = (datetime.datetime.now() - self.creation_time).seconds
        return delta > self.cache_lifetime

    def set_outdated(self):
        self.create_time = None


class MongoSettingsHandler(SettingsHandler):
    """Settings handler that use mongo for storing and loading of settings."""
    key_suffix = "_versioned"
    _version_order_key = "versions_order"
    _all_versions_keys = "all_versions"

    def __init__(self):
        self._anatomy_keys = None
        self._attribute_keys = None

        self._version_order_checked = False

        self._global_settings_key = GLOBAL_SETTINGS_KEY + self.key_suffix
        self._project_settings_key = PROJECT_SETTINGS_KEY + self.key_suffix
        self._project_anatomy_key = PROJECT_ANATOMY_KEY + self.key_suffix
        self._current_version = quadpype.version.__version__

        database_name = os.environ["QUADPYPE_DATABASE_NAME"]
        collection_name = "settings"

        # Get mongo connection
        self.mongo_client = QuadPypeMongoConnection.get_mongo_client()

        self.database_name = database_name
        self.collection_name = collection_name

        self.collection = self.mongo_client[database_name][collection_name]

        self.core_settings_cache = CacheValues()
        self.global_settings_cache = CacheValues()
        self.project_settings_cache = collections.defaultdict(CacheValues)
        self.project_anatomy_cache = collections.defaultdict(CacheValues)

    def _prepare_project_settings_keys(self):
        from .entities import ProjectSettingsEntity
        # Prepare anatomy keys and attribute keys
        # NOTE this is cached on first import
        # - keys may change only on schema change which should not happen
        #   during production
        project_settings_root = ProjectSettingsEntity(
            reset=False, change_state=False
        )
        anatomy_entity = project_settings_root[PROJECT_ANATOMY_KEY]
        anatomy_keys = set(anatomy_entity.keys())
        anatomy_keys.remove("attributes")
        attribute_keys = set(anatomy_entity["attributes"].keys())

        self._anatomy_keys = anatomy_keys
        self._attribute_keys = attribute_keys

    @property
    def anatomy_keys(self):
        if self._anatomy_keys is None:
            self._prepare_project_settings_keys()
        return self._anatomy_keys

    @property
    def attribute_keys(self):
        if self._attribute_keys is None:
            self._prepare_project_settings_keys()
        return self._attribute_keys

    def get_core_settings_doc(self):
        if self.core_settings_cache.is_outdated:
            global_settings_doc = self.collection.find_one({
                "type": GLOBAL_SETTINGS_KEY
            }) or {}
            self.core_settings_cache.update_data(global_settings_doc, None)
        return self.core_settings_cache.data_copy()

    def get_core_settings(self):
        global_settings_doc = self.get_core_settings_doc()
        global_settings = global_settings_doc.get("data", {})
        return {
            key: global_settings[key]
            for key in self.core_keys
            if key in global_settings
        }

    def _extract_core_settings(self, data):
        """Extract core settings data from global settings overrides.

        Returns:
            dict: Core settings extracted from global settings data.
        """
        output = {}
        if CORE_SETTINGS_KEY not in data:
            return output

        core_data = data[CORE_SETTINGS_KEY]

        # Add predefined keys to global settings if are set
        for key in self.core_keys:
            if key not in core_data:
                continue
            # Pop key from values
            output[key] = core_data.pop(key)
            # Pop key from overridden metadata
            if (
                M_OVERRIDDEN_KEY in core_data
                and key in core_data[M_OVERRIDDEN_KEY]
            ):
                core_data[M_OVERRIDDEN_KEY].remove(key)
        return output

    def _apply_core_settings(
        self, global_settings_document, core_document
    ):
        """Apply core settings data to global settings.

        Application is skipped if document with core settings is not
        available or does not have set data in.

        Global settings document is "faked" like it exists if core document
        has set values.

        Args:
            global_settings_document (dict): Global settings document from
                MongoDB.
            core_document (dict): Core settings document from MongoDB.

        Returns:
            Merged document which has applied global settings data.
        """
        # Skip if core document is not available
        if (
            not core_document
            or "data" not in core_document
            or not core_document["data"]
        ):
            return global_settings_document

        core_data = core_document["data"]
        # Check if data contain any key from predefined keys
        any_key_found = False
        if core_data:
            for key in self.core_keys:
                if key in core_data:
                    any_key_found = True
                    break

        # Skip if any key from predefined key was not found in globals
        if not any_key_found:
            return global_settings_document

        # "Fake" global settings document if document does not exist
        # - global settings document may exist but global settings not yet
        if not global_settings_document:
            global_settings_document = {}

        if "data" in global_settings_document:
            global_settings_data = global_settings_document["data"]
        else:
            global_settings_data = {}
            global_settings_document["data"] = global_settings_data

        if CORE_SETTINGS_KEY in global_settings_data:
            global_core_data = global_settings_data[CORE_SETTINGS_KEY]
        else:
            global_core_data = {}
            global_settings_data[CORE_SETTINGS_KEY] = global_core_data

        overridden_keys = global_core_data.get(M_OVERRIDDEN_KEY) or []
        for key in self.core_keys:
            if key not in core_data:
                continue

            global_core_data[key] = core_data[key]
            if key not in overridden_keys:
                overridden_keys.append(key)

        if overridden_keys:
            global_core_data[M_OVERRIDDEN_KEY] = overridden_keys

        return global_settings_document

    def save_studio_settings(self, data):
        """Save studio overrides of global settings.

        Do not use to store whole global settings data with defaults but only
        it's overrides with metadata defining how overrides should be applied
        in load function. For loading should be used function
        `studio_global_settings`.

        Args:
            data(dict): Data of studio overrides with override metadata.
        """
        # Update cache
        self.global_settings_cache.update_data(data, self._current_version)

        last_saved_info = SettingsStateInfo.create_new(
            self._current_version,
            GLOBAL_SETTINGS_KEY
        )
        self.global_settings_cache.update_last_saved_info(
            last_saved_info
        )

        # Get copy of just updated cache
        global_settings_data = self.global_settings_cache.data_copy()

        # Extract core settings from global settings
        core_settings = self._extract_core_settings(
            global_settings_data
        )
        self.core_settings_cache.update_data(
            core_settings,
            None
        )

        global_settings_doc = self.collection.find_one(
            {
                "type": self._global_settings_key,
                "version": self._current_version
            },
            {"_id": True}
        )

        # Store global settings
        new_global_settings_doc = {
            "type": self._global_settings_key,
            "version": self._current_version,
            "data": global_settings_data,
            "last_saved_info": last_saved_info.to_document_data()
        }
        if not global_settings_doc:
            self.collection.insert_one(new_global_settings_doc)
        else:
            self.collection.update_one(
                {"_id": global_settings_doc["_id"]},
                {"$set": new_global_settings_doc}
            )

        # Store core settings
        self.collection.replace_one(
            {
                "type": CORE_SETTINGS_KEY
            },
            {
                "type": CORE_SETTINGS_KEY,
                "data": core_settings
            },
            upsert=True
        )

    def save_project_settings(self, project_name, overrides):
        """Save studio overrides of project settings.

        Data are saved for specific project or as defaults for all projects.

        Do not use to store whole project settings data with defaults but only
        it's overrides with metadata defining how overrides should be applied
        in load function. For loading should be used function
        `get_studio_project_settings_overrides` for global project settings
        and `get_project_settings_overrides` for project specific settings.

        Args:
            project_name(str, null): Project name for which overrides are
                or None for global settings.
            overrides(dict): Data of project overrides with override metadata.
        """
        data_cache = self.project_settings_cache[project_name]
        data_cache.update_data(overrides, self._current_version)

        last_saved_info = SettingsStateInfo.create_new(
            self._current_version,
            PROJECT_SETTINGS_KEY,
            project_name
        )

        data_cache.update_last_saved_info(last_saved_info)

        self._save_project_data(
            project_name,
            self._project_settings_key,
            data_cache,
            last_saved_info
        )

    def save_project_anatomy(self, project_name, anatomy_data):
        """Save studio overrides of project anatomy data.

        Args:
            project_name(str, null): Project name for which overrides are
                or None for global settings.
            anatomy_data(dict): Data of project overrides with override metadata.
        """
        data_cache = self.project_anatomy_cache[project_name]
        data_cache.update_data(anatomy_data, self._current_version)

        if project_name is not None:
            self._save_project_anatomy_data(project_name, data_cache)

        else:
            last_saved_info = SettingsStateInfo.create_new(
                self._current_version,
                PROJECT_ANATOMY_KEY,
                project_name
            )
            self._save_project_data(
                project_name,
                self._project_anatomy_key,
                data_cache,
                last_saved_info
            )

    @classmethod
    def prepare_mongo_update_dict(cls, in_data):
        data = {}
        for key, value in in_data.items():
            if not isinstance(value, dict):
                data[key] = value
                continue

            new_value = cls.prepare_mongo_update_dict(value)
            for _key, _value in new_value.items():
                new_key = ".".join((key, _key))
                data[new_key] = _value

        return data

    def save_change_log(self, project_name, changes, settings_type):
        """Log all settings changes to separate collection"""
        if not changes:
            return

        if settings_type == "project" and not project_name:
            project_name = "default"

        host_info = get_workstation_info()

        document = {
            "user_id": get_user_id(),
            "username": host_info["username"],
            "workstation_name": host_info["workstation_name"],
            "host_ip": host_info["host_ip"],
            "system_name": host_info["system_name"],
            "date_created": datetime.datetime.now(),
            "project": project_name,
            "settings_type": settings_type,
            "changes": changes
        }
        collection_name = "settings_log"
        collection = self.mongo_client[self.database_name][collection_name]
        collection.insert_one(document)

    def _save_project_anatomy_data(self, project_name, data_cache):
        # Create copy of data as they will be modified during save
        new_data = data_cache.data_copy()

        # Prepare avalon project document
        project_doc = get_project(project_name)
        if not project_doc:
            raise ValueError((
                "Project document of project \"{}\" does not exists."
                " Create project first."
            ).format(project_name))

        collection = get_project_connection(project_name)
        # Project's data
        update_dict_data = {}
        project_doc_data = project_doc.get("data") or {}
        attributes = new_data.pop("attributes")
        _applications = attributes.pop(APPS_SETTINGS_KEY, None) or []
        for key, value in attributes.items():
            if (
                key in project_doc_data
                and project_doc_data[key] == value
            ):
                continue
            update_dict_data[key] = value

        update_dict_config = {}

        applications = []
        for application in _applications:
            if not application:
                continue
            if isinstance(application, six.string_types):
                applications.append({"name": application})

        new_data["apps"] = applications

        for key, value in new_data.items():
            project_doc_value = project_doc.get(key)
            if key in project_doc and project_doc_value == value:
                continue
            update_dict_config[key] = value

        if not update_dict_data and not update_dict_config:
            return

        data_changes = self.prepare_mongo_update_dict(update_dict_data)

        # Update dictionary of changes that will be changed in mongo
        update_dict = {}
        for key, value in data_changes.items():
            new_key = "data.{}".format(key)
            update_dict[new_key] = value

        for key, value in update_dict_config.items():
            new_key = "config.{}".format(key)
            update_dict[new_key] = value

        collection.update_one(
            {"type": "project"},
            {"$set": update_dict}
        )

    def _save_project_data(
        self, project_name, doc_type, data_cache, last_saved_info
    ):
        is_default = bool(project_name is None)
        query_filter = {
            "type": doc_type,
            "is_default": is_default,
            "version": self._current_version
        }

        new_project_settings_doc = {
            "type": doc_type,
            "data": data_cache.data,
            "is_default": is_default,
            "version": self._current_version,
            "last_saved_info": last_saved_info.to_data()
        }

        if not is_default:
            query_filter["project_name"] = project_name
            new_project_settings_doc["project_name"] = project_name

        project_settings_doc = self.collection.find_one(
            query_filter,
            {"_id": True}
        )
        if project_settings_doc:
            self.collection.update_one(
                {"_id": project_settings_doc["_id"]},
                {"$set": new_project_settings_doc}
            )
        else:
            self.collection.insert_one(new_project_settings_doc)

    def _get_versions_order_doc(self, projection=None):
        # TODO cache
        return self.collection.find_one(
            {"type": self._version_order_key},
            projection
        ) or {}

    def _check_version_order(self):
        """This method will work only in QuadPype process.

        Will create/update mongo document where QuadPype versions are stored
        in semantic version order.

        This document can be then used to find closes version of settings in
        processes where 'QuadPypeVersion' is not available.
        """
        # Do this step only once
        if self._version_order_checked:
            return
        self._version_order_checked = True

        from quadpype.lib.quadpype_version import get_QuadPypeVersion

        QuadPypeVersion = get_QuadPypeVersion()
        # Skip if 'QuadPypeVersion' is not available
        if QuadPypeVersion is None:
            return

        # Query document holding sorted list of version strings
        doc = self._get_versions_order_doc()
        if not doc:
            doc = {"type": self._version_order_key}

        if self._all_versions_keys not in doc:
            doc[self._all_versions_keys] = []

        # Skip if current version is already available
        if self._current_version in doc[self._all_versions_keys]:
            return

        if self._current_version not in doc[self._all_versions_keys]:
            # Add all versions into list
            all_objected_versions = [
                QuadPypeVersion(version=self._current_version)
            ]
            for version_str in doc[self._all_versions_keys]:
                all_objected_versions.append(
                    QuadPypeVersion(version=version_str)
                )

            doc[self._all_versions_keys] = [
                str(version) for version in sorted(all_objected_versions)
            ]

        self.collection.replace_one(
            {"type": self._version_order_key},
            doc,
            upsert=True
        )

    def find_closest_version_for_projects(self, project_names):
        output = {
            project_name: None
            for project_name in project_names
        }
        from quadpype.lib.quadpype_version import get_QuadPypeVersion
        QuadPypeVersion = get_QuadPypeVersion()
        if QuadPypeVersion is None:
            return output

        versioned_doc = self._get_versions_order_doc()

        settings_ids = []
        for project_name in project_names:
            if project_name is None:
                doc_filter = {"is_default": True}
            else:
                doc_filter = {"project_name": project_name}
            settings_id = self._find_closest_settings_id(
                self._project_settings_key,
                PROJECT_SETTINGS_KEY,
                doc_filter,
                versioned_doc
            )
            if settings_id:
                settings_ids.append(settings_id)

        if settings_ids:
            docs = self.collection.find(
                {"_id": {"$in": settings_ids}},
                {"version": True, "project_name": True}
            )
            for doc in docs:
                project_name = doc.get("project_name")
                version = doc.get("version")
                output[project_name] = version
        return output

    def _find_closest_settings_id(
        self, key, legacy_key, additional_filters=None, versioned_doc=None
    ):
        """Try to find closes available versioned settings for settings key.

        This method should be used only if settings for current QuadPype
        version are not available.

        Args:
            key(str): Settings key under which are settings stored ("type").
            legacy_key(str): Settings key under which were stored not versioned
                settings.
            additional_filters(dict): Additional filters of document. Used
                for project specific settings.
        """
        # Trigger check of versions
        self._check_version_order()

        doc_filters = {
            "type": {"$in": [key, legacy_key]}
        }
        if additional_filters:
            doc_filters.update(additional_filters)

        # Query base data of each settings doc
        other_versions = self.collection.find(
            doc_filters,
            {
                "_id": True,
                "version": True,
                "type": True
            }
        )
        # Query doc with list of sorted versions
        if versioned_doc is None:
            versioned_doc = self._get_versions_order_doc()

        # Separate queried docs
        legacy_settings_doc = None
        versioned_settings_by_version = {}
        for doc in other_versions:
            if doc["type"] == legacy_key:
                legacy_settings_doc = doc
            elif doc["type"] == key:
                if doc["version"] == self._current_version:
                    return doc["_id"]
                versioned_settings_by_version[doc["version"]] = doc

        versions_in_doc = versioned_doc.get(self._all_versions_keys) or []
        # Cases when only legacy settings can be used
        if (
            # There are not versioned documents yet
            not versioned_settings_by_version
            # Versioned document is not available at all
            # - this can happen only if old build of QuadPype was used
            or not versioned_doc
            # Current QuadPype version is not available
            # - something went really wrong when this happens
            or self._current_version not in versions_in_doc
        ):
            if not legacy_settings_doc:
                return None
            return legacy_settings_doc["_id"]

        # Separate versions to lower and higher and keep their order
        lower_versions = []
        higher_versions = []
        before = True
        for version_str in versions_in_doc:
            if version_str == self._current_version:
                before = False
            elif before:
                lower_versions.append(version_str)
            else:
                higher_versions.append(version_str)

        # Use legacy settings doc as source document
        src_doc_id = None
        if legacy_settings_doc:
            src_doc_id = legacy_settings_doc["_id"]

        # Find the highest version which has available settings
        if lower_versions:
            for version_str in reversed(lower_versions):
                doc = versioned_settings_by_version.get(version_str)
                if doc:
                    src_doc_id = doc["_id"]
                    break

        # Use versions with higher version only if there are no legacy
        #   settings and there are not any versions before
        if src_doc_id is None and higher_versions:
            for version_str in higher_versions:
                doc = versioned_settings_by_version.get(version_str)
                if doc:
                    src_doc_id = doc["_id"]
                    break

        return src_doc_id

    def _find_closest_settings(
        self, key, legacy_key, additional_filters=None, versioned_doc=None
    ):
        doc_id = self._find_closest_settings_id(
            key, legacy_key, additional_filters, versioned_doc
        )
        if doc_id is None:
            return None
        return self.collection.find_one({"_id": doc_id})

    def _find_closest_global_settings(self):
        return self._find_closest_settings(
            self._global_settings_key,
            GLOBAL_SETTINGS_KEY
        )

    def _find_closest_project_settings(self, project_name):
        if project_name is None:
            additional_filters = {"is_default": True}
        else:
            additional_filters = {"project_name": project_name}

        return self._find_closest_settings(
            self._project_settings_key,
            PROJECT_SETTINGS_KEY,
            additional_filters
        )

    def _find_closest_project_anatomy(self):
        additional_filters = {"is_default": True}
        return self._find_closest_settings(
            self._project_anatomy_key,
            PROJECT_ANATOMY_KEY,
            additional_filters
        )

    def _get_studio_global_settings_overrides_for_version(self, version=None):
        # QUESTION cache?
        if version is None:
            version = self._current_version

        return self.collection.find_one({
            "type": self._global_settings_key,
            "version": version
        })

    def _get_project_settings_overrides_for_version(
        self, project_name, version=None
    ):
        if version is None:
            version = self._current_version

        document_filter = {
            "type": self._project_settings_key,
            "version": version
        }

        if project_name is None:
            document_filter["is_default"] = True
        else:
            document_filter["project_name"] = project_name
        return self.collection.find_one(document_filter)

    def _get_project_anatomy_overrides_for_version(self, version=None):
        # QUESTION cache?
        if version is None:
            version = self._current_version

        return self.collection.find_one({
            "type": self._project_anatomy_key,
            "is_default": True,
            "version": version
        })

    def get_studio_global_settings_overrides(self, return_version):
        """Studio overrides of global settings."""
        if self.global_settings_cache.is_outdated:
            core_document = self.get_core_settings_doc()
            document, version = self._get_global_settings_overrides_doc()

            last_saved_info = SettingsStateInfo.from_document(
                version, GLOBAL_SETTINGS_KEY, document
            )
            merged_document = self._apply_core_settings(
                document, core_document
            )

            self.global_settings_cache.update_from_document(
                merged_document, version
            )
            self.global_settings_cache.update_last_saved_info(
                last_saved_info
            )

        cache = self.global_settings_cache
        data = cache.data_copy()
        if return_version:
            return data, cache.version
        return data

    def _get_global_settings_overrides_doc(self):
        document = (
            self._get_studio_global_settings_overrides_for_version()
        )
        if document is None:
            document = self._find_closest_global_settings()

        version = None
        if document:
            version = document["version"]

        return document, version

    def get_global_settings_last_saved_info(self):
        # Make sure settings are re-cached
        self.global_settings_cache.set_outdated()
        self.get_studio_global_settings_overrides(False)

        return self.global_settings_cache.last_saved_info.copy()

    def _get_project_settings_overrides(self, project_name, return_version):
        if self.project_settings_cache[project_name].is_outdated:
            document, version = self._get_project_settings_overrides_doc(
                project_name
            )
            self.project_settings_cache[project_name].update_from_document(
                document, version
            )
            last_saved_info = SettingsStateInfo.from_document(
                version, PROJECT_SETTINGS_KEY, document
            )
            self.project_settings_cache[project_name].update_last_saved_info(
                last_saved_info
            )

        cache = self.project_settings_cache[project_name]
        data = cache.data_copy()
        if return_version:
            return data, cache.version
        return data

    def _get_project_settings_overrides_doc(self, project_name):
        document = self._get_project_settings_overrides_for_version(
            project_name
        )
        if document is None:
            document = self._find_closest_project_settings(project_name)

        version = None
        if document:
            version = document["version"]

        return document, version

    def get_project_settings_last_saved_info(self, project_name):
        # Make sure settings are re-cached
        self.project_settings_cache[project_name].set_outdated()
        self._get_project_settings_overrides(project_name, False)

        return self.project_settings_cache[project_name].last_saved_info.copy()

    def get_studio_project_settings_overrides(self, return_version):
        """Studio overrides of default project settings."""
        return self._get_project_settings_overrides(None, return_version)

    def get_project_settings_overrides(self, project_name, return_version):
        """Studio overrides of project settings for specific project.

        Args:
            project_name(str): Name of project for which data should be loaded.

        Returns:
            dict: Only overrides for entered project, may be empty dictionary.
        """
        if not project_name:
            if return_version:
                return {}, None
            return {}
        return self._get_project_settings_overrides(
            project_name, return_version
        )

    def project_doc_to_anatomy_data(self, project_doc):
        """Convert project document to anatomy data.

        Probably should fill missing keys and values.
        """
        if not project_doc:
            return {}

        attributes = {}
        project_doc_data = project_doc.get("data") or {}
        for key in self.attribute_keys:
            value = project_doc_data.get(key)
            if value is not None:
                attributes[key] = value

        project_doc_config = project_doc.get("config") or {}

        app_names = set()
        if not project_doc_config or "apps" not in project_doc_config:
            set_applications = False
        else:
            set_applications = True
            for app_item in project_doc_config["apps"]:
                if not app_item:
                    continue
                app_name = app_item.get("name")
                if app_name:
                    app_names.add(app_name)

        if set_applications:
            attributes[APPS_SETTINGS_KEY] = list(app_names)

        output = {"attributes": attributes}
        for key in self.anatomy_keys:
            value = project_doc_config.get(key)
            if value is not None:
                output[key] = value

        return output

    def _get_project_anatomy_overrides(self, project_name, return_version):
        if self.project_anatomy_cache[project_name].is_outdated:
            if project_name is None:
                document = self._get_project_anatomy_overrides_for_version()
                if document is None:
                    document = self._find_closest_project_anatomy()

                version = None
                if document:
                    version = document["version"]

                self.project_anatomy_cache[project_name].update_from_document(
                    document, version
                )

            else:
                project_doc = get_project(project_name)
                self.project_anatomy_cache[project_name].update_data(
                    self.project_doc_to_anatomy_data(project_doc),
                    self._current_version
                )

        cache = self.project_anatomy_cache[project_name]
        data = cache.data_copy()
        if return_version:
            return data, cache.version
        return data

    def get_studio_project_anatomy_overrides(self, return_version):
        """Studio overrides of default project anatomy data."""
        return self._get_project_anatomy_overrides(None, return_version)

    def get_project_anatomy_overrides(self, project_name, return_version):
        """Studio overrides of project anatomy for specific project.

        Args:
            project_name(str): Name of project for which data should be loaded.
            return_version(bool): Version string will be added to output.

        Returns:
            dict: Only overrides for entered project, may be empty dictionary.
        """
        if not project_name:
            return {}
        return self._get_project_anatomy_overrides(project_name, return_version)

    # Implementations of abstract methods to get overrides for version
    def get_studio_global_settings_overrides_for_version(self, version):
        doc = self._get_studio_global_settings_overrides_for_version(version)
        if not doc:
            return doc
        return doc["data"]

    def get_studio_project_anatomy_overrides_for_version(self, version):
        doc = self._get_project_anatomy_overrides_for_version(version)
        if not doc:
            return doc
        return doc["data"]

    def get_studio_project_settings_overrides_for_version(self, version):
        doc = self._get_project_settings_overrides_for_version(None, version)
        if not doc:
            return doc
        return doc["data"]

    def get_project_settings_overrides_for_version(
        self, project_name, version
    ):
        doc = self._get_project_settings_overrides_for_version(
            project_name, version
        )
        if not doc:
            return doc
        return doc["data"]

    # Implementations of abstract methods to clear overrides for version
    def clear_studio_global_settings_overrides_for_version(self, version):
        self.collection.delete_one({
            "type": self._global_settings_key,
            "version": version
        })

    def clear_studio_project_settings_overrides_for_version(self, version):
        self.collection.delete_one({
            "type": self._project_settings_key,
            "version": version,
            "is_default": True
        })

    def clear_studio_project_anatomy_overrides_for_version(self, version):
        self.collection.delete_one({
            "type": self._project_anatomy_key,
            "version": version
        })

    def clear_project_settings_overrides_for_version(
        self, version, project_name
    ):
        self.collection.delete_one({
            "type": self._project_settings_key,
            "version": version,
            "project_name": project_name
        })

    def _sort_versions(self, versions):
        """Sort versions.

        WARNING:
        This method does not handle all possible issues so it should not be
        used in logic which determine which settings are used. Is used for
        sorting of available versions.
        """
        if not versions:
            return []

        set_versions = set(versions)

        from quadpype.lib.quadpype_version import get_QuadPypeVersion

        QuadPypeVersion = get_QuadPypeVersion()

        # Skip if 'QuadPypeVersion' is not available
        if QuadPypeVersion is not None:
            obj_versions = sorted(
                [QuadPypeVersion(version=version) for version in set_versions]
            )
            sorted_versions = [str(version) for version in obj_versions]

            return sorted_versions

        doc = self._get_versions_order_doc()
        all_versions = doc.get(self._all_versions_keys)
        if not all_versions:
            return list(sorted(versions))

        sorted_versions = []
        for version in all_versions:
            if version in set_versions:
                set_versions.remove(version)
                sorted_versions.append(version)

        for version in sorted(set_versions):
            sorted_versions.insert(0, version)

        return sorted_versions

    # Get available versions for settings type
    def get_available_studio_global_settings_overrides_versions(
        self, sorted=None
    ):
        docs = self.collection.find(
            {"type": {
                "$in": [self._global_settings_key, GLOBAL_SETTINGS_KEY]
            }},
            {"type": True, "version": True}
        )
        output = set()
        for doc in docs:
            output.add(doc["version"])
        if not sorted:
            return output
        return self._sort_versions(output)

    def get_available_studio_project_anatomy_overrides_versions(
        self, sorted=None
    ):
        docs = self.collection.find(
            {"type": {
                "$in": [self._project_anatomy_key, PROJECT_ANATOMY_KEY]
            }},
            {"type": True, "version": True}
        )
        output = set()
        for doc in docs:
            output.add(doc["version"])
        if not sorted:
            return output
        return self._sort_versions(output)

    def get_available_studio_project_settings_overrides_versions(
        self, sorted=None
    ):
        docs = self.collection.find(
            {
                "is_default": True,
                "type": {
                    "$in": [self._project_settings_key, PROJECT_SETTINGS_KEY]
                }
            },
            {"type": True, "version": True}
        )
        output = set()
        for doc in docs:
            output.add(doc["version"])
        if not sorted:
            return output
        return self._sort_versions(output)

    def get_available_project_settings_overrides_versions(
        self, project_name, sorted=None
    ):
        docs = self.collection.find(
            {
                "project_name": project_name,
                "type": {
                    "$in": [self._project_settings_key, PROJECT_SETTINGS_KEY]
                }
            },
            {"type": True, "version": True}
        )
        output = set()
        for doc in docs:
            output.add(doc["version"])
        if not sorted:
            return output
        return self._sort_versions(output)

    def get_last_opened_info(self):
        doc = self.collection.find_one({
            "type": "last_opened_settings_ui",
            "version": self._current_version
        }) or {}
        info_data = doc.get("info", {})
        if not info_data:
            return info_data

        # Fill not available information
        info_data["quadpype_version"] = self._current_version
        info_data["settings_type"] = None
        info_data["project_name"] = None
        return SettingsStateInfo.from_data(info_data)

    def opened_settings_ui(self):
        doc_filter = {
            "type": "last_opened_settings_ui",
            "version": self._current_version
        }

        opened_info = SettingsStateInfo.create_new(self._current_version)
        new_doc_data = copy.deepcopy(doc_filter)
        new_doc_data["info"] = opened_info.to_document_data()

        doc = self.collection.find_one(
            doc_filter,
            {"_id": True}
        )
        if doc:
            self.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": new_doc_data}
            )
        else:
            self.collection.insert_one(new_doc_data)
        return opened_info

    def closed_settings_ui(self, info_obj):
        doc_filter = {
            "type": "last_opened_settings_ui",
            "version": self._current_version
        }
        doc = self.collection.find_one(doc_filter) or {}
        info_data = doc.get("info")
        if not info_data:
            return

        info_data["quadpype_version"] = self._current_version
        info_data["settings_type"] = None
        info_data["project_name"] = None
        current_info = SettingsStateInfo.from_data(info_data)
        if current_info == info_obj:
            self.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"info": None}}
            )


class MongoUserHandler(UserHandler):
    """Settings handler that use mongo for store and load user info & settings.

    The Data query criteria is the key "user_id" which can be obtained
    with the `get_user_id` function.
    """

    def __init__(self, user_id=None):
        # Get mongo connection
        from quadpype.lib import get_user_id

        if user_id is None:
            user_id = get_user_id()

        database_name = os.environ["QUADPYPE_DATABASE_NAME"]
        collection_name = "users"

        self.mongo_client = QuadPypeMongoConnection.get_mongo_client()

        self.database_name = database_name
        self.collection_name = collection_name

        self.collection = self.mongo_client[database_name][collection_name]

        self.user_id = user_id

        self.user_settings_cache = CacheValues()

    def create_user_profile(self):
        user_profile = deepcopy(self.user_profile_template)
        user_profile["user_id"] = self.user_id

        timestamp = datetime.datetime.now()
        user_profile["first_connection"] = timestamp
        user_profile["last_connection"] = timestamp

        user_profile["workstation_profiles"].append(get_workstation_info())

        self.collection.replace_one(
            {"user_id": self.user_id},
            user_profile, upsert=True
        )
        return user_profile

    def get_user_profile(self):
        user_profile = self.collection.find_one({
            "user_id": self.user_id
        })

        if user_profile is None:
            raise RuntimeError("Cannot find the user profile in the QuadPype database.\n"
                               "This shouldn't be possible, please contact the Quad Dev Team.")

        return user_profile

    def update_user_profile_on_startup(self):
        """Update user profile on startup"""
        user_profile = self.get_user_profile()
        user_profile["last_connection"] = datetime.datetime.now()

        workstation_info = get_workstation_info()

        workstation_profile_found = False
        for index, workstation_profile in enumerate(user_profile["workstation_profiles"]):
            if workstation_info == workstation_profile:
                user_profile["last_workstation_profile_index"] = index
                workstation_profile_found = True
                break

        if not workstation_profile_found:
            user_profile["workstation_profiles"].append(workstation_info)
            user_profile["last_workstation_profile_index"] = len(user_profile["workstation_profiles"]) - 1

        self.collection.replace_one(
            {"user_id": self.user_id},
            user_profile, upsert=True
        )

        return user_profile

    def save_user_settings(self, data):
        """Save user settings.

        Args:
            data(dict): Data of studio overrides with override metadata.
        """
        data = data or {}

        self.user_settings_cache.update_data(data, None)

        user_profile = self.collection.find_one(
            { "user_id": self.user_id }
        )

        if not user_profile:
            raise RuntimeError("Cannot find the user profile in the QuadPype database.\n"
                               "This shouldn't be possible, please contact the Quad Dev Team.")

        user_profile["settings"] = data

        self.collection.replace_one(
            { "user_id": self.user_id },
            user_profile
        )

    def get_user_settings(self):
        """Get the user according to the user id."""
        if self.user_settings_cache.is_outdated:
            document = self.collection.find_one({
                "user_id": self.user_id
            })

            self.user_settings_cache.update_from_document(document["settings"], None)

        return self.user_settings_cache.data_copy()