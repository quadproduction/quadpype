import importlib.util
from pathlib import Path


# To avoid code duplication the required classes are imported manually
# from the base QuadPype package version

# /!\ Careful: Edits made in ZIP patch versions won't be used, to
#    propagate the changes here a true update need to be created and
#    installed on all machines using the QuadPype

# Define the path to the registry.py module in the QuadPype package
registry_module_path = Path(__file__).parent.parent.joinpath("quadpype", "lib", "registry.py").resolve()

# Load the registry module without triggering __init__.py
spec = importlib.util.spec_from_file_location("igniter.registry_proxy", registry_module_path)
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)

# Expose specific classes from registry
QuadPypeSecureRegistry = registry.QuadPypeSecureRegistry
QuadPypeSettingsRegistry = registry.QuadPypeSettingsRegistry


__all__ = [
    "QuadPypeSecureRegistry",
    "QuadPypeSettingsRegistry"
]
