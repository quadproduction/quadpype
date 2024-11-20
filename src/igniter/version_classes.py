import importlib
from .module_importer import load_quadpype_module


version_module = load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

PackageVersion = version_module.PackageVersion
PackageVersionExists = version_module.PackageVersionExists
PackageVersionIOError = version_module.PackageVersionIOError
PackageVersionInvalid = version_module.PackageVersionInvalid
PackageVersionNotFound = version_module.PackageVersionNotFound
PackageVersionIncompatible = version_module.PackageVersionIncompatible

QuadPypeVersionManager = version_module.QuadPypeVersionManager


def reload_module():
    load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

def get_app_version_manager() -> QuadPypeVersionManager:
    if version_module.QUADPYPE_VERSION_MANAGER is None:
        raise RuntimeError("QuadPype Version Manager is not initialized")
    return version_module.QUADPYPE_VERSION_MANAGER


__all__ = [
    "PackageVersion",
    "PackageVersionExists",
    "PackageVersionIOError",
    "PackageVersionInvalid",
    "PackageVersionNotFound",
    "PackageVersionIncompatible",

    "QuadPypeVersionManager",
    "get_app_version_manager"
]
