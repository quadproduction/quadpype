from operator import truediv

from quadpype.lib import Logger
from quadpype.pipeline import InventoryAction

LOADER_NAME = "BlendLoader"
class MakeLibraryOverride(InventoryAction):
    """Will create a library override on linked objects in subset"""
    label = "Make Library Override"
    icon = "gears"
    color = "#cc0000"

    log = Logger.get_logger(__name__)

    @staticmethod
    def is_compatible(container):
        # Check if the loader type is BlendLoad
        if not MakeLibraryOverride.is_blend_loader(container):
            return False
        # Check if the members are linked
        if not MakeLibraryOverride.is_members_linked_in_blend_loader(container.get("members")):
            return False
        # Check if the members don't have any override
        if not MakeLibraryOverride.is_members_library_override(container.get("members")):
            return False
        return True

    @staticmethod
    def is_blend_loader(container):
        """Check if the containers are from a BlendLoader
        Args:
            container(dict): A dict of data about the container.
        Returns:
            bool
        """
        # Get Loader
        loader_name = container.get("loader")
        return loader_name == LOADER_NAME

    @staticmethod
    def is_members_linked_in_blend_loader(members):
        """Check if all members of the container are linked
        Args:
            members(list): List of element in the subset.
        Returns:
            bool
        """
        is_linked = True
        for member in members:
            if not hasattr(member, "library"):
                continue
            if not member.library:
                continue
            is_linked = False
        return is_linked

    @staticmethod
    def is_members_library_override(members):
        """Check if all member library is already override.
        Args:
            members(list): List of element in the subset.
        Returns:
            bool
        """
        is_override = False
        for member in members:
            if not hasattr(member, "override_library"):
                continue
            if not member.override_library:
                continue
            is_override = True
        return is_override

    def process(self, containers):
        """Will create a library override on linked members inside containers"""
        for container in containers:
            if not self.is_compatible(container):
                continue
            #ToDo create override on linked
            print("hey")
