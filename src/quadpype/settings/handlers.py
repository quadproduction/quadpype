import os
import copy
import collections
import platform

from datetime import datetime, timezone
from abc import ABC, abstractmethod

import quadpype.version
from quadpype.client.mongo import (
    QuadPypeMongoConnection,
    get_project_connection,
)
from quadpype.client import get_project
from quadpype.lib import get_user_workstation_info, get_user_id, CacheValues
from quadpype.lib.version import PackageVersion, get_package
from .constants import (
    CORE_KEYS,
    CORE_SETTINGS_DOC_KEY,
    CORE_SETTINGS_KEY,
    GLOBAL_SETTINGS_KEY,
    PROJECT_SETTINGS_KEY,
    PROJECT_ANATOMY_KEY,
    M_OVERRIDDEN_KEY,

    APPS_SETTINGS_KEY,

    DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY,
    DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
    DATABASE_PROJECT_ANATOMY_VERSIONED_KEY
)
from .lib import (
    apply_core_settings,
    check_version_order,
    get_versions_order_doc,
    find_closest_settings_id,
    find_closest_settings,
    get_global_settings_overrides_doc,
    get_global_settings_overrides_for_version_doc
)


class SettingsStateInfo:
    """Helper state information about some settings state.

    Is used to hold information about last saved and last opened UI. Keep
    information about the time when that happened and on which machine under
    which user and on which QuadPype version.

    To create current machine and time information use 'create_new' method.
    """

    timestamp_format = "%Y-%m-%d %H:%M:%S.%f%z"

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
            if "+" not in timestamp:
                # Ensure an UTC offset is set
                timestamp += "+0000"

            timestamp_obj = datetime.strptime(
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

        from quadpype.lib import get_user_workstation_info

        now = datetime.now(timezone.utc)
        workstation_info = get_user_workstation_info()

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


class SettingsHandler(ABC):

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

        Output must contain all keys from 'CORE_KEYS'. If value is not set
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


class MongoSettingsHandler(SettingsHandler):
    """Settings handler that uses mongo for storing and loading of settings."""

    def __init__(self):
        self._anatomy_keys = None
        self._attribute_keys = None

        self._version_order_checked = False
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
            core_settings_doc = self.collection.find_one({
                "type": CORE_SETTINGS_DOC_KEY
            }) or {}
            self.core_settings_cache.update_data(core_settings_doc, None)
        return self.core_settings_cache.data_copy()

    def get_core_settings(self):
        global_settings_doc = self.get_core_settings_doc()
        global_settings = global_settings_doc.get("data", {})
        return {
            key: global_settings[key]
            for key in CORE_KEYS
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
        for key in CORE_KEYS:
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

        # Check and potentially apply the changes to the package instance
        self._apply_core_settings_changes_to_package_instance(core_settings)

        # Update the cache
        self.core_settings_cache.update_data(
            core_settings,
            None
        )

        global_settings_doc = self.collection.find_one(
            {
                "type": DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY,
                "version": self._current_version
            },
            {"_id": True}
        )

        # Store global settings
        new_global_settings_doc = {
            "type": DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY,
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

        # Add or update the core settings in the database
        self.collection.replace_one(
            {
                "type": CORE_SETTINGS_DOC_KEY
            },
            {
                "type": CORE_SETTINGS_DOC_KEY,
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
            DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
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
                DATABASE_PROJECT_ANATOMY_VERSIONED_KEY,
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

        host_info = get_user_workstation_info()

        document = {
            "user_id": get_user_id(),
            "username": host_info["username"],
            "workstation_name": host_info["workstation_name"],
            "host_ip": host_info["host_ip"],
            "system_name": host_info["system_name"],
            "date_created": datetime.now(timezone.utc),
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

        # Prepare database project document
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
        attributes = new_data.pop("attributes", {})
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
            if isinstance(application, str):
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

    def _apply_core_settings_changes_to_package_instance(self, new_core_settings):
        """Apply the new changes of the core settings to the QuadPype package instance."""
        platform_low = platform.system().lower()
        package = get_package("quadpype")

        # Fetch the core settings
        curr_core_settings_doc = self.get_core_settings_doc()
        curr_core_settings = curr_core_settings_doc["data"] if curr_core_settings_doc else {}

        # Keys to monitor
        keys_to_check = [
            ("remote_sources", package.change_remote_sources),
            ("local_versions_dir", package.change_local_dir_path)
        ]

        changes = {}
        # Check for changes
        for key, _ in keys_to_check:
            curr_value = curr_core_settings.get(key)
            new_value = new_core_settings.get(key)
            if curr_value != new_value:
                changes[key] = new_value

        if not changes:
            return

        # Apply the changes
        for key, funct in keys_to_check:
            if key in changes:
                if changes[key] and platform_low in changes[key]:
                    funct(changes[key][platform_low])
                else:
                    funct(None)

    def _check_version_order(self):
        """This method will work only in QuadPype process.

        Will create/update mongo document where QuadPype versions are stored
        in semantic version order.

        This document can be then used to find closes version of settings in
        processes where 'PackageVersion' is not available.
        """
        # Do this step only once
        if self._version_order_checked:
            return
        self._version_order_checked = True

        check_version_order(self.collection, self._current_version)

    def find_closest_version_for_projects(self, project_names):
        output = {
            project_name: None
            for project_name in project_names
        }
        versioned_doc = get_versions_order_doc(self.collection)

        settings_ids = []
        for project_name in project_names:
            if project_name is None:
                doc_filter = {"is_default": True}
            else:
                doc_filter = {"project_name": project_name}
            settings_id = find_closest_settings_id(
                self.collection,
                self._current_version,
                DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
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

    def _find_closest_project_settings(self, project_name):
        if project_name is None:
            additional_filters = {"is_default": True}
        else:
            additional_filters = {"project_name": project_name}

        return find_closest_settings(
            self.collection,
            self._current_version,
            DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
            PROJECT_SETTINGS_KEY,
            additional_filters
        )

    def _find_closest_project_anatomy(self):
        additional_filters = {"is_default": True}
        return find_closest_settings(
            self.collection,
            self._current_version,
            DATABASE_PROJECT_ANATOMY_VERSIONED_KEY,
            PROJECT_ANATOMY_KEY,
            additional_filters
        )

    def _get_project_settings_overrides_for_version(
        self, project_name, version=None
    ):
        if version is None:
            version = self._current_version

        document_filter = {
            "type": DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
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
            "type": DATABASE_PROJECT_ANATOMY_VERSIONED_KEY,
            "is_default": True,
            "version": version
        })

    def get_studio_global_settings_overrides(self, return_version):
        """Studio overrides of global settings."""
        if self.global_settings_cache.is_outdated:
            core_document = self.get_core_settings_doc()
            document, version = get_global_settings_overrides_doc(
                self.collection,
                self._current_version
            )

            last_saved_info = SettingsStateInfo.from_document(
                version, GLOBAL_SETTINGS_KEY, document
            )
            merged_document = apply_core_settings(document, core_document)

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
        if document and document["type"] == DATABASE_PROJECT_SETTINGS_VERSIONED_KEY:
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
                if document and document["type"] == DATABASE_PROJECT_ANATOMY_VERSIONED_KEY:
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
        version = version if version else self._current_version
        doc = get_global_settings_overrides_for_version_doc(self.collection, version)
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
            "type": DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY,
            "version": version
        })

    def clear_studio_project_settings_overrides_for_version(self, version):
        self.collection.delete_one({
            "type": DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
            "version": version,
            "is_default": True
        })

    def clear_studio_project_anatomy_overrides_for_version(self, version):
        self.collection.delete_one({
            "type": DATABASE_PROJECT_ANATOMY_VERSIONED_KEY,
            "version": version
        })

    def clear_project_settings_overrides_for_version(
        self, version, project_name
    ):
        self.collection.delete_one({
            "type": DATABASE_PROJECT_SETTINGS_VERSIONED_KEY,
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

        sorted_versions = sorted(
            list({str(PackageVersion(version=version)) for version in versions})
        )

        return sorted_versions

    # Get available versions for settings type
    def get_available_studio_global_settings_overrides_versions(
        self, sorted=None
    ):
        docs = self.collection.find(
            {"type": DATABASE_GLOBAL_SETTINGS_VERSIONED_KEY},
            {"version": True}
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
                "$in": [DATABASE_PROJECT_ANATOMY_VERSIONED_KEY, PROJECT_ANATOMY_KEY]
            }},
            {"version": True}
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
                    "$in": [DATABASE_PROJECT_SETTINGS_VERSIONED_KEY, PROJECT_SETTINGS_KEY]
                }
            },
            {"version": True}
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
                    "$in": [DATABASE_PROJECT_SETTINGS_VERSIONED_KEY, PROJECT_SETTINGS_KEY]
                }
            },
            {"version": True}
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
        info_data = doc.get("info", {}) or {}
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
