from .module_importer import load_quadpype_module


registry_module = load_quadpype_module("quadpype/lib/registry.py", "quadpype.lib.registry")

# Expose specific classes from registry
QuadPypeSecureRegistry = registry_module.QuadPypeSecureRegistry
QuadPypeSettingsRegistry = registry_module.QuadPypeSettingsRegistry


__all__ = [
    "QuadPypeSecureRegistry",
    "QuadPypeSettingsRegistry"
]
