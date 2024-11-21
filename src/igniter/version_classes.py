import importlib
from .module_importer import load_quadpype_module


version_module = load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

PackageVersion = version_module.PackageVersion
PackageVersionExists = version_module.PackageVersionExists
PackageVersionIOError = version_module.PackageVersionIOError
PackageVersionInvalid = version_module.PackageVersionInvalid
PackageVersionNotFound = version_module.PackageVersionNotFound
PackageVersionIncompatible = version_module.PackageVersionIncompatible

get_package = version_module.get_package

def reload_module():
    load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

__all__ = [
    "PackageVersion",
    "PackageVersionExists",
    "PackageVersionIOError",
    "PackageVersionInvalid",
    "PackageVersionNotFound",
    "PackageVersionIncompatible",

    "get_package",

    "reload_module"
]
