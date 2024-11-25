from .module_importer import load_quadpype_module


registry_module = load_quadpype_module("quadpype/lib/registry.py", "quadpype.lib.registry")

# Expose specific classes from registry
QuadPypeSecureRegistry = registry_module.QuadPypeSecureRegistry
QuadPypeRegistry = registry_module.QuadPypeRegistry


__all__ = [
    "QuadPypeSecureRegistry",
    "QuadPypeRegistry"
]
