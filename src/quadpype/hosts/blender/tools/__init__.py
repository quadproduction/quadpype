from quadpype.tools.utils.host_tools import qt_app_context


class BlenderToolsSingleton:
    _look_assigner = None


def get_look_assigner_tool(parent):
    """Create, cache and return look assigner tool window."""
    if BlenderToolsSingleton._look_assigner is None:
        from .lookassigner import BlenderLookAssignerWindow
        mayalookassigner_window = BlenderLookAssignerWindow(parent)
        BlenderToolsSingleton._look_assigner = mayalookassigner_window
    return BlenderToolsSingleton._look_assigner


def show_look_assigner(parent=None):
    """Look manager is Maya specific tool for look management."""

    with qt_app_context():
        look_assigner_tool = get_look_assigner_tool(parent)
        look_assigner_tool.show()

        # Pull window to the front.
        look_assigner_tool.raise_()
        look_assigner_tool.activateWindow()
        look_assigner_tool.showNormal()
