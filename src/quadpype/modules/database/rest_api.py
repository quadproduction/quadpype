import json
import datetime

from bson.objectid import ObjectId

from fastapi import Response, status

from quadpype.client import (
    get_projects,
    get_project,
    get_assets,
    get_asset_by_name,
)
from quadpype_modules.webserver.base_routes import RestApiEndpoint


class _RestApiEndpoint(RestApiEndpoint):
    def __init__(self, resource):
        self.resource = resource
        super().__init__()


class DatabaseProjectsEndpoint(_RestApiEndpoint):
    async def get(self) -> Response:
        output = [
            project_doc
            for project_doc in get_projects()
        ]
        return Response(
            status_code=status.HTTP_200_OK,
            content=self.resource.encode(output),
            media_type="application/json"
        )


class DatabaseProjectEndpoint(_RestApiEndpoint):
    async def get(self, project_name) -> Response:
        project_doc = get_project(project_name)
        if project_doc:
            return Response(
                status_code=status.HTTP_200_OK,
                content=self.resource.encode(project_doc),
                media_type="application/json"
            )
        return Response(
            status_code=status.HTTP_404_NOT_FOUND,
            content="Project name {} not found".format(project_name)
        )


class DatabaseAssetsEndpoint(_RestApiEndpoint):
    async def get(self, project_name) -> Response:
        asset_docs = list(get_assets(project_name))
        return Response(
            status_code=status.HTTP_200_OK,
            content=self.resource.encode(asset_docs),
            media_type="application/json"
        )


class DatabaseAssetEndpoint(_RestApiEndpoint):
    async def get(self, project_name, asset_name) -> Response:
        asset_doc = get_asset_by_name(project_name, asset_name)
        if asset_doc:
            return Response(
                status_code=status.HTTP_200_OK,
                content=self.resource.encode(asset_doc),
                media_type="application/json"
            )
        return Response(
            status_code=status.HTTP_404_NOT_FOUND,
            content="Asset name {} not found in project {}".format(
                asset_name, project_name
            )
        )


class DatabaseRestApiResource:
    def __init__(self, database_module, server_manager):
        self.module = database_module
        self.server_manager = server_manager

        self.prefix = "/data"

        self.endpoint_defs = (
            (
                "GET",
                "/projects",
                DatabaseProjectsEndpoint(self)
            ),
            (
                "GET",
                "/projects/{project_name}",
                DatabaseProjectEndpoint(self)
            ),
            (
                "GET",
                "/projects/{project_name}/assets",
                DatabaseAssetsEndpoint(self)
            ),
            (
                "GET",
                "/projects/{project_name}/assets/{asset_name}",
                DatabaseAssetEndpoint(self)
            )
        )

        self.register()

    def register(self):
        for methods, url, endpoint in self.endpoint_defs:
            final_url = self.prefix + url
            self.server_manager.add_route(
                methods, final_url, endpoint.dispatch
            )

    @staticmethod
    def json_dump_handler(value):
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        if isinstance(value, ObjectId):
            return str(value)
        raise TypeError(value)

    @classmethod
    def encode(cls, data):
        return json.dumps(
            data,
            indent=4,
            default=cls.json_dump_handler
        ).encode("utf-8")
