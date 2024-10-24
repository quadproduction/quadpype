"""Helper functions or classes for Webserver module.

These must not be imported in module itself to not break Python 2
applications.
"""

import inspect
from fastapi import Request, HTTPException, status


DEFAULT_METHODS = ("GET", "POST", "PUT", "DELETE")


# /!\ DEPRECATED /!\
# This is the old way to create and add endpoint (a.k.a route) to the API
# Please don't use this for new endpoints, check how to properly declare
# routes with FastAPI on the official documentation online.
class RestApiEndpoint:
    """Helper endpoint class for single endpoint.

    Class can define `get`, `post`, `put` or `delete` async methods for the
    endpoint.
    """
    def __init__(self):
        methods = {}

        for method_name in DEFAULT_METHODS:
            method = getattr(self, method_name.lower(), None)
            if method:
                methods[method_name.upper()] = method

        self.methods = methods

    async def dispatch(self, request: Request):
        method = self.methods.get(request.method.upper())
        if not method:
            details = "Allowed methods: {}".format(", ".join(DEFAULT_METHODS))
            raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail=details)

        wanted_args = list(inspect.signature(method).parameters.keys())

        # RestApiEndpoint support only query_params not path_params.
        # This is another limitation pushing to use FastAPI

        # To add a param, we need to create a copy (but query_params is a special type)
        # This is why we need to iterate on items
        available_args = {}
        for param_key, param_value in request.query_params.items():
            available_args[param_key] = param_value
        available_args["request"] = request

        unsatisfied_args = set(wanted_args) - set(available_args.keys())
        if unsatisfied_args:
            # Expected match info that doesn't exist
            details = ("Some required parameters hasn't been sent with the request, "
                       "missing parameters: {}".format(", ".join(unsatisfied_args)))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=details)

        return await method(**{
            arg_name: available_args[arg_name]
            for arg_name in wanted_args
        })
