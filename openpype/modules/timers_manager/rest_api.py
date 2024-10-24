import json

from fastapi import Response, status
from quadpype.lib import Logger


class TimersManagerModuleRestApi:
    """
        REST API endpoint used for calling from hosts when context change
        happens in Workfile app.
    """
    def __init__(self, user_module, server_manager):
        self._log = None
        self.module = user_module
        self.server_manager = server_manager

        self.prefix = "/timers_manager"

        self.register()

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    def register(self):
        self.server_manager.add_route(
            "POST",
            self.prefix + "/start_timer",
            self.start_timer
        )
        self.server_manager.add_route(
            "POST",
            self.prefix + "/stop_timer",
            self.stop_timer
        )
        self.server_manager.add_route(
            "GET",
            self.prefix + "/get_task_time",
            self.get_task_time
        )

    async def start_timer(self, request):
        data = await request.json()
        try:
            project_name = data["project_name"]
            asset_name = data["asset_name"]
            task_name = data["task_name"]
        except KeyError:
            msg = (
                "Payload must contain fields 'project_name,"
                " 'asset_name' and 'task_name'"
            )
            self.log.error(msg)
            return Response(status_code=status.HTTP_400_BAD_REQUEST, content=msg)

        self.module.stop_timers()
        try:
            self.module.start_timer(project_name, asset_name, task_name)
        except Exception as exc:
            return Response(status_code=status.HTTP_404_NOT_FOUND, content=str(exc))

        return Response(status_code=status.HTTP_200_OK)

    async def stop_timer(self, request):
        self.module.stop_timers()
        return Response(status_code=status.HTTP_200_OK)

    async def get_task_time(self, request):
        data = await request.json()
        try:
            project_name = data['project_name']
            asset_name = data['asset_name']
            task_name = data['task_name']
        except KeyError:
            message = (
                "Payload must contain fields 'project_name, 'asset_name',"
                " 'task_name'"
            )
            self.log.warning(message)
            return Response(content=message, status_code=status.HTTP_404_NOT_FOUND)

        time = self.module.get_task_time(project_name, asset_name, task_name)
        return Response(content=json.dumps(time))
