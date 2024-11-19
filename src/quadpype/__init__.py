import os

from importlib import import_module
import pkgutil


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")

_WEB_API_ROUTERS = []  # Don't hardcode values in this variable, it's autofilled


def get_all_registered_web_api_routers():
    """Iterate over all sub-packages and return the list of FastAPI routers registered"""
    global _WEB_API_ROUTERS

    if len(_WEB_API_ROUTERS):
        # Routers already retrieved
        # Avoid doing the operation again
        return _WEB_API_ROUTERS

    for _, subpackage_name, is_pkg in pkgutil.iter_modules(__path__, prefix=f"quadpype."):
        if not is_pkg:
            continue

        try:
            subpackage = import_module(subpackage_name)

            if hasattr(subpackage, "get_web_api_routers"):
                get_routers_func = getattr(subpackage, "get_web_api_routers")
                if callable(get_routers_func):
                    routers = get_routers_func()
                    if isinstance(routers, list):
                        _WEB_API_ROUTERS.extend(routers)
        except Exception as e:
            print(f"Web API routers lookup: Error while importing package {subpackage_name}: {e}")

    return _WEB_API_ROUTERS
