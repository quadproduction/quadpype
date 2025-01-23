from importlib import import_module
import pkgutil

from fastapi import APIRouter

from .handler import (
    get_event_handler,
    send_event,
    get_event_doc
)

from .notification import (
    show_tray_message
)


# Find and include routers defined in this package modules
def get_web_api_routers():
    routers = []
    package_name = __name__
    for _, module_name, _ in pkgutil.iter_modules(__path__, prefix=f"{package_name}."):
        try:
            module = import_module(module_name)

            if hasattr(module, "router"):
                router = getattr(module, "router")
                if isinstance(router, APIRouter):
                    routers.append(router)
        except Exception as e:
            print(f"Get web API routers: Error while handling module {module_name}: {e}")

    return routers


__all__ = (
    "get_event_handler",
    "send_event",
    "get_event_doc",

    "get_web_api_routers",

    "show_tray_message"
)
