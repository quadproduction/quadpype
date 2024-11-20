import sys
import importlib.util
from pathlib import Path


# To avoid code duplication the required classes are imported manually
# from the base QuadPype package version

# /!\ Careful: Edits made in ZIP patch versions won't be used, to
#    propagate the changes here a true update need to be created and
#    installed on all machines using the QuadPype


def load_quadpype_module(module_relative_path, module_name):
    module_relative_path = module_relative_path.replace("\\", "/")
    # Define the path to the registry.py module in the QuadPype package
    module_path = Path(__file__).parent.parent.joinpath(module_relative_path).resolve()

    # Load the registry module without triggering __init__.py
    # Appending _proxy at the end of the module-name to avoid conflicts between modules in sys.modules
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module
