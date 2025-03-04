# -*- coding: utf-8 -*-
"""Package to deal with saving and retrieving user specific settings."""
import os
import json
import platform
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from functools import lru_cache
import configparser
from typing import Any

import appdirs


_PLACEHOLDER = object()
_REGISTRY = None


class QuadPypeSecureRegistry:
    """Store information using keyring.

    Registry should be used for private data that should be available only for
    user.

    All passed registry names will have added prefix `QuadPype/` to easier
    identify which data were created by QuadPype.

    Args:
        name(str): Name of registry used as identifier for data.
    """
    def __init__(self, name):
        try:
            import keyring

        except Exception:
            raise NotImplementedError(
                "Python module `keyring` is not available."
            )

        # hack for cx_freeze and Windows keyring backend
        if platform.system().lower() == "windows":
            from keyring.backends import Windows

            keyring.set_keyring(Windows.WinVaultKeyring())

        # Force "QuadPype" prefix
        self._name = "/".join(("QuadPype", name))

    def set_item(self, name, value):
        # type: (str, str) -> None
        """Set sensitive item into system's keyring.

        This uses `Keyring module`_ to save sensitive stuff into system's
        keyring.

        Args:
            name (str): Name of the item.
            value (str): Value of the item.

        .. _Keyring module:
            https://github.com/jaraco/keyring

        """
        import keyring

        keyring.set_password(self._name, name, value)

    @lru_cache(maxsize=32)
    def get_item(self, name, default=_PLACEHOLDER):
        """Get the value of sensitive item from the system's keyring.

        See also `Keyring module`_

        Args:
            name (str): Name of the item.
            default (Any): Default value if item is not available.

        Returns:
            value (str): Value of the item.

        Raises:
            ValueError: If item doesn't exist and default is not defined.

        .. _Keyring module:
            https://github.com/jaraco/keyring

        """
        import keyring

        value = keyring.get_password(self._name, name)
        if value is not None:
            return value

        if default is not _PLACEHOLDER:
            return default

        # NOTE Should raise `KeyError`
        raise ValueError(
            "Item {}:{} does not exist in keyring.".format(self._name, name)
        )

    def delete_item(self, name):
        # type: (str) -> None
        """Delete value stored in system's keyring.

        See also `Keyring module`_

        Args:
            name (str): Name of the item to be deleted.

        .. _Keyring module:
            https://github.com/jaraco/keyring

        """
        import keyring

        self.get_item.cache_clear()
        keyring.delete_password(self._name, name)


class ASettingRegistry(ABC):
    """Abstract class defining structure of **SettingRegistry** class.

    It is implementing methods to store secure items into keyring, otherwise
    mechanism for storing common items must be implemented in abstract
    methods.

    Attributes:
        _name (str): Registry names.

    """

    def __init__(self, name):
        # type: (str) -> ASettingRegistry
        super(ASettingRegistry, self).__init__()

        self._name = name
        self._items = {}

    def set_item(self, name, value):
        # type: (str, str) -> None
        """Set item to settings registry.

        Args:
            name (str): Name of the item.
            value (str): Value of the item.

        """
        self._set_item(name, value)

    @abstractmethod
    def _set_item(self, name, value):
        # type: (str, str) -> None
        # Implement it
        pass

    def __setitem__(self, name, value):
        self._items[name] = value
        self._set_item(name, value)

    def get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> str
        """Get item from settings registry.

        Args:
            name (str): Name of the item.
            fallback (Any): Fallback value if item is not found.

        Returns:
            value (str): Value of the item.

        Raises:
            ValueError: If item doesn't exist.

        """
        return self._get_item(name, fallback)

    @abstractmethod
    def _get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> str
        # Implement it
        pass

    def __getitem__(self, name):
        return self._get_item(name)

    def delete_item(self, name):
        # type: (str) -> None
        """Delete item from settings registry.

        Args:
            name (str): Name of the item.

        """
        self._delete_item(name)

    @abstractmethod
    def _delete_item(self, name):
        # type: (str) -> None
        """Delete item from settings.

        Note:
            see :meth:`quadpype.lib.user_settings.ARegistrySettings.delete_item`

        """
        pass

    def __delitem__(self, name):
        del self._items[name]
        self._delete_item(name)


class IniSettingRegistry(ASettingRegistry):
    """Class using :mod:`configparser`.

    This class is using :mod:`configparser` (ini) files to store items.

    """

    def __init__(self, name, path):
        # type: (str, str) -> IniSettingRegistry
        super().__init__(name)
        # get registry file
        version = os.getenv("QUADPYPE_VERSION", "N/A")
        self._registry_file = os.path.join(path, "{}.ini".format(name))
        if not os.path.exists(self._registry_file):
            with open(self._registry_file, mode="w") as cfg:
                print("# Settings registry", cfg)
                print("# Generated by QuadPype {}".format(version), cfg)
                now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
                print("# {}".format(now), cfg)

    def set_item_section(
            self, section, name, value):
        # type: (str, str, str) -> None
        """Set item to specific section of ini registry.

        If section doesn't exists, it is created.

        Args:
            section (str): Name of section.
            name (str): Name of the item.
            value (str): Value of the item.

        """
        value = str(value)
        config = configparser.ConfigParser()

        config.read(self._registry_file)
        if not config.has_section(section):
            config.add_section(section)
        current = config[section]
        current[name] = value

        with open(self._registry_file, mode="w") as cfg:
            config.write(cfg)

    def _set_item(self, name, value):
        # type: (str, str) -> None
        self.set_item_section("MAIN", name, value)

    def set_item(self, name, value):
        # type: (str, str) -> None
        """Set item to settings ini file.

        This saves item to ``DEFAULT`` section of ini as each item there
        must reside in some section.

        Args:
            name (str): Name of the item.
            value (str): Value of the item.

        """
        # this does the some, overridden just for different docstring.
        # we cast value to str as ini options values must be strings.
        super(IniSettingRegistry, self).set_item(name, str(value))

    def get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> str
        """Gets item from the settings INI file.

        This gets settings from the ``DEFAULT`` section of the ini file as each item
        there must reside in some section.

        Args:
            name (str): Name of the item.
            fallback (Any): Fallback value if item is not found.

        Returns:
            str: Value of item.

        Raises:
            ValueError: If value doesn't exist.

        """
        return super(IniSettingRegistry, self).get_item(name, fallback)

    @lru_cache(maxsize=32)
    def get_item_from_section(self, section, name, fallback=_PLACEHOLDER):
        # type: (str, str, Any) -> str
        """Get item from a specific section of the INI file.

        This will read the INI file and try to get item value from the specified
        section. If that section or item doesn't exist, :exc:`ValueError`
        is risen.

        Args:
            section (str): Name of the INI section.
            name (str): Name of the item.
            fallback (Any): Fallback value if item is not found.

        Returns:
            str: Item value.

        Raises:
            ValueError: If value doesn't exist.

        """
        config = configparser.ConfigParser()
        config.read(self._registry_file)
        try:
            value = config[section][name]
        except KeyError:
            if fallback is not _PLACEHOLDER:
                return fallback
            raise ValueError(
                "Registry doesn't contain value {}:{}".format(section, name))
        return value

    def _get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> str
        return self.get_item_from_section("MAIN", name, fallback)

    def delete_item_from_section(self, section, name):
        # type: (str, str) -> None
        """Delete an item from a section in the INI file.

        Args:
            section (str): Section name.
            name (str): Name of the item.

        Raises:
            ValueError: If item doesn't exist.

        """
        self.get_item_from_section.cache_clear()
        config = configparser.ConfigParser()
        config.read(self._registry_file)
        try:
            _ = config[section][name]
        except KeyError:
            raise ValueError(
                "Registry doesn't contain value {}:{}".format(section, name))
        config.remove_option(section, name)

        # if the section is empty, delete it
        if len(config[section].keys()) == 0:
            config.remove_section(section)

        with open(self._registry_file, mode="w") as cfg:
            config.write(cfg)

    def _delete_item(self, name):
        """Delete item from the default section.

        Note:
            See :meth:`~quadpype.lib.IniSettingsRegistry.delete_item_from_section`
        """
        self.delete_item_from_section("MAIN", name)


class JSONSettingRegistry(ASettingRegistry):
    """Class using a JSON file as storage."""

    def __init__(self, name, path, base_version=None):
        super(JSONSettingRegistry, self).__init__(name)
        #: str: name of registry file
        self._registry_file = os.path.join(path, "{}.json".format(name))
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")

        if not base_version:
            base_version = "N/A"
        version = os.getenv("QUADPYPE_VERSION", base_version)
        if not isinstance(version, str):
            version = str(version)

        default_content = {
            "__metadata__": {
                "quadpype_version": version,
                "generated": now
            },
            "registry": {
                "last_handled_event_timestamp": 0
            }
        }

        if not os.path.exists(os.path.dirname(self._registry_file)):
            os.makedirs(os.path.dirname(self._registry_file), exist_ok=True)
        if not os.path.exists(self._registry_file):
            with open(self._registry_file, mode="w") as cfg:
                json.dump(default_content, cfg, indent=4)

    @lru_cache(maxsize=32)
    def _get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> Any
        """Get item value from registry the JSON.

        Note:
            See :meth:`quadpype.lib.JSONSettingRegistry.get_item`

        """
        with open(self._registry_file, mode="r") as cfg:
            data = json.load(cfg)
            try:
                value = data["registry"][name]
            except KeyError:
                if fallback is not _PLACEHOLDER:
                    return fallback
                raise ValueError(
                    "Registry doesn't contain value {}".format(name))
        return value

    def get_item(self, name, fallback=_PLACEHOLDER):
        # type: (str, Any) -> Any
        """Get item value from registry the JSON.

        Args:
            name (str): Name of the item.
            fallback (Any): Fallback value if item is not found.

        Returns:
            value of the item

        Raises:
            ValueError: If item is not found in the registry file.

        """
        return self._get_item(name, fallback)

    def _set_item(self, name, value):
        # type: (str, object) -> None
        """Set item value to the registry JSON file.

        Note:
            See :meth:`quadpype.lib.JSONSettingRegistry.set_item`

        """
        with open(self._registry_file, "r+") as cfg:
            data = json.load(cfg)
            data["registry"][name] = value
            cfg.truncate(0)
            cfg.seek(0)
            json.dump(data, cfg, indent=4)

    def set_item(self, name, value):
        # type: (str, object) -> None
        """Set item and its value into json registry file.

        Args:
            name (str): name of the item.
            value (Any): value of the item.

        """
        self._set_item(name, value)

    def _delete_item(self, name):
        # type: (str) -> None
        self._get_item.cache_clear()
        with open(self._registry_file, "r+") as cfg:
            data = json.load(cfg)
            del data["registry"][name]
            cfg.truncate(0)
            cfg.seek(0)
            json.dump(data, cfg, indent=4)


class QuadPypeRegistry(JSONSettingRegistry):
    """Class handling QuadPype general settings registry.

    Attributes:
        vendor (str): Name used for path construction.
        product (str): Additional name used for path construction.

    """

    def __init__(self, name=None, base_version=None):
        vendor = "quad"
        product = "quadpype"
        default_name = "quadpype_settings"
        self.vendor = vendor
        self.product = product
        if not name:
            name = default_name
        path = appdirs.user_data_dir(self.product, self.vendor)
        super().__init__(name, path, base_version)


def get_app_registry() -> QuadPypeRegistry:
    global _REGISTRY
    if not _REGISTRY:
        _REGISTRY = QuadPypeRegistry()

    return _REGISTRY
