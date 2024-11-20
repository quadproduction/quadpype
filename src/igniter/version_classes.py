from .module_importer import load_quadpype_module


version_module = load_quadpype_module("quadpype/lib/version.py", "quadpype.lib.version")

QuadPypeVersion = version_module.QuadPypeVersion
QuadPypeVersionExists = version_module.QuadPypeVersionExists
QuadPypeVersionIOError = version_module.QuadPypeVersionIOError
QuadPypeVersionInvalid = version_module.QuadPypeVersionInvalid
QuadPypeVersionNotFound = version_module.QuadPypeVersionNotFound
QuadPypeVersionIncompatible = version_module.QuadPypeVersionIncompatible

__all__ = [
    "QuadPypeVersion",
    "QuadPypeVersionExists",
    "QuadPypeVersionIOError",
    "QuadPypeVersionInvalid",
    "QuadPypeVersionNotFound",
    "QuadPypeVersionIncompatible"
]
