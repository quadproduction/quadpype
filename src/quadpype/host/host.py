import os
import logging
import contextlib
from abc import ABC, abstractproperty

# NOTE can't import 'typing' because of issues in Maya 2020
#   - shiboken crashes on 'typing' module import


class HostBase(ABC):
    """Base of host implementation class.

    Host is pipeline implementation of DCC application. This class should help
    to identify what must/should/can be implemented for specific functionality.
    """

    _log = None

    def __init__(self):
        """Initialization of host.

        Register DCC callbacks, host specific plugin paths, targets etc.

        Note:
            At this moment global "installation" must happen before host
            installation. Because of this current limitation it is recommended
            to implement 'install' method which is triggered after global
            'install'.
        """

        pass

    def install(self):
        """Install host specific functionality.

        This is where should be added menu with tools, registered callbacks
        and other host integration initialization.

        It is called automatically when 'quadpype.pipeline.install_host' is
        triggered.
        """

        pass

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    @abstractproperty
    def name(self):
        """Host name."""

        pass

    def get_current_project_name(self):
        """
        Returns:
            Union[str, None]: Current project name.
        """

        return os.getenv("QUADPYPE_PROJECT_NAME")

    def get_current_asset_name(self):
        """
        Returns:
            Union[str, None]: Current asset name.
        """

        return os.getenv("QUADPYPE_ASSET_NAME")

    def get_current_task_name(self):
        """
        Returns:
            Union[str, None]: Current task name.
        """

        return os.getenv("QUADPYPE_TASK_NAME")

    def get_current_context(self):
        """Get current context information.

        This method should be used to get current context of host. Usage of
        this method can be crucial for host implementations in DCCs where
        can be opened multiple workfiles at one moment and change of context
        can't be caught properly.

        Returns:
            Dict[str, Union[str, None]]: Context with 3 keys 'project_name',
                'asset_name' and 'task_name'. All of them can be 'None'.
        """

        return {
            "project_name": self.get_current_project_name(),
            "asset_name": self.get_current_asset_name(),
            "task_name": self.get_current_task_name()
        }

    def get_context_title(self):
        """Context title shown for UI purposes.

        Should return current context title if possible.

        Note:
            This method is used only for UI purposes so it is possible to
                return some logical title for contextless cases.
            Is not meant for "Context menu" label.

        Returns:
            str: Context title.
            None: Default title is used based on UI implementation.
        """

        # Use current context to fill the context title
        current_context = self.get_current_context()
        project_name = current_context["project_name"]
        asset_name = current_context["asset_name"]
        task_name = current_context["task_name"]
        items = []
        if project_name:
            items.append(project_name)
            if asset_name:
                items.append(asset_name.lstrip("/"))
                if task_name:
                    items.append(task_name)
        if items:
            return "/".join(items)
        return None

    @contextlib.contextmanager
    def maintained_selection(self):
        """Some functionality will happen but selection should stay same.

        This is DCC specific. Some may not allow to implement this ability
        that is the reason why default implementation is empty context manager.

        Yields:
            None: Yield when is ready to restore selected at the end.
        """

        try:
            yield
        finally:
            pass
