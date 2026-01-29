# -*- coding: utf-8 -*-
"""Package storing all functions related to user data."""
import os
import copy
import getpass
import functools
import platform
import socket

from datetime import datetime, timezone
from abc import ABC, abstractmethod

from .registry import get_app_registry
from .cache import UserSettingsCacheValues
from quadpype.client.mongo import QuadPypeMongoConnection
from quadpype.client import save_project_timestamp


# Handler for users
_USER_HANDLER = None


class UserHandler(ABC):
    """Handler using to store and load user info & settings.

    User settings are specific modifications that modify how
    global and project settings look on the workstation and only there.
    """
    user_profile_template = {
        "user_id": "",
        "role": "user",
        "first_connection_timestamp": datetime.now(timezone.utc),
        "last_connection_timestamp": datetime.now(timezone.utc),
        "last_workstation_profile_index": 0,
        "workstation_profiles": [],
        "tracker_logins": {},
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

    @abstractmethod
    def set_tracker_login_to_user_profile(self, tracker_name, login_value):
        """Set the user login for a specific tracker in his profile."""
        pass


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

        if not self.collection.find_one({"user_id": self.user_id}):
            # if there isn't any user, the first one is automatically added as administrator
            user_role = "user" if self.collection.count_documents({}) else "administrator"
            # Create the user profile in the database
            self.create_user_profile(user_role=user_role)

        self.user_settings_cache = UserSettingsCacheValues(name=self.user_id)

    def create_user_profile(self, user_role="user"):
        user_profile = copy.deepcopy(self.user_profile_template)
        user_profile["user_id"] = self.user_id
        user_profile["role"] = user_role

        timestamp = datetime.now(timezone.utc)
        user_profile["first_connection_timestamp"] = timestamp
        user_profile["last_connection_timestamp"] = timestamp

        user_profile["workstation_profiles"].append(get_user_workstation_info())

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
            self.create_user_profile()

        return user_profile

    def get_all_user_profiles(self):
        return self.collection.find({})

    def update_user_profile_on_startup(self):
        """Update user profile on startup"""
        user_profile = self.get_user_profile()
        user_profile["last_connection_timestamp"] = datetime.now(timezone.utc)

        workstation_info = get_user_workstation_info()

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

        save_project_timestamp(
            project_name=f"user:{self.user_id}",
            updated_entity='settings'
        )

        return user_profile

    def set_tracker_login_to_user_profile(self, tracker_name, login_value):
        user_profile = self.get_user_profile()

        if "tracker_logins" not in user_profile:
            # Ensure the dict exists in the user profile
            user_profile["tracker_logins"] = {}

        user_profile["tracker_logins"][tracker_name] = login_value

        self.collection.replace_one(
            {"user_id": self.user_id},
            user_profile, upsert=True
        )

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

        save_project_timestamp(
            project_name=self.user_id,
            updated_entity='settings'
        )

    def get_user_settings(self):
        """Get the user according to the user id."""
        if self.user_settings_cache.is_outdated:
            document = self.collection.find_one({
                "user_id": self.user_id
            })
            # Key renaming Required to work with the cache system
            document["data"] = document.pop("settings")

            self.user_settings_cache.update_from_document(document, None)

        return self.user_settings_cache.data_copy()


def create_user_handler():
    return MongoUserHandler()


def require_user_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _USER_HANDLER
        if _USER_HANDLER is None:
            _USER_HANDLER = create_user_handler()
        return func(*args, **kwargs)
    return wrapper


@require_user_handler
def save_user_settings(data):
    return _USER_HANDLER.save_user_settings(data)


@require_user_handler
def get_user_settings():
    return _USER_HANDLER.get_user_settings()


@require_user_handler
def get_user_profile():
    return _USER_HANDLER.get_user_profile()


@require_user_handler
def get_all_user_profiles():
    return _USER_HANDLER.get_all_user_profiles()


@require_user_handler
def update_user_profile_on_startup():
    return _USER_HANDLER.update_user_profile_on_startup()


@require_user_handler
def set_tracker_login_to_user_profile(tracker_name, login_value):
    return _USER_HANDLER.set_tracker_login_to_user_profile(tracker_name, login_value)


def _create_user_id(registry=None):
    """Create a user identifier."""
    from coolname import generate_slug

    if registry is None:
        registry = get_app_registry()

    new_id = generate_slug(3)

    print("Created user id \"{}\"".format(new_id))

    registry.set_item("user_id", new_id)

    return new_id


def get_user_id():
    """Get user identifier.

    Identifier is created if it does not exists yet.
    """

    registry = get_app_registry()
    try:
        return registry.get_item("user_id")
    except ValueError:
        return _create_user_id(registry=registry)


def get_local_site_id():
    """Get the local site identifier."""

    # Check if the value is set on the env variable
    # This is used for background syncing
    if os.getenv("QUADPYPE_LOCAL_ID"):
        return os.environ["QUADPYPE_LOCAL_ID"]

    # Else using the user ID
    return get_user_id()


def get_quadpype_username():
    """QuadPype username used for templates and publishing.

    May be different from machine's username.

    Always returns "QUADPYPE_USERNAME" environment if is set then tries local
    settings and last option is to use `getpass.getuser()` which returns
    machine username.
    """

    username = os.getenv("QUADPYPE_USERNAME")
    if not username:
        user_settings = get_user_settings()
        username = (
            user_settings
            .get("general", {})
            .get("username")
        )
        if not username:
            username = getpass.getuser()
    return username


def get_user_workstation_info():
    """Basic information about workstation."""
    host_name = socket.gethostname()
    try:
        host_ip = socket.gethostbyname(host_name)
    except socket.gaierror:
        host_ip = "127.0.0.1"

    return {
        "workstation_name": host_name,
        "host_ip": host_ip,
        "username": getpass.getuser(),
        "system_name": platform.system()
    }
