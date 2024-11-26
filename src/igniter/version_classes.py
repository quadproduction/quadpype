from .module_importer import load_quadpype_module


version_module = load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

PackageHandler = version_module.PackageHandler
PackageVersion = version_module.PackageVersion
PackageVersionExists = version_module.PackageVersionExists
PackageVersionIOError = version_module.PackageVersionIOError
PackageVersionInvalid = version_module.PackageVersionInvalid
PackageVersionNotFound = version_module.PackageVersionNotFound
PackageVersionIncompatible = version_module.PackageVersionIncompatible

get_package = version_module.get_package
create_package_manager = version_module.create_package_manager

def reload_module():
    load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")


__all__ = [
    "PackageHandler",
    "PackageVersion",
    "PackageVersionExists",
    "PackageVersionIOError",
    "PackageVersionInvalid",
    "PackageVersionNotFound",
    "PackageVersionIncompatible",

    "get_package",
    "create_package_manager",

    "reload_module"
]
