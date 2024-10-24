

def cleanup_quadpype_qt_widgets():
    """
        Workaround for Substance failing to shut down correctly
        when a Qt window was still open at the time of shutting down.

        This seems to work sometimes, but not all the time.

    """
    # TODO: Create a more reliable method to close down all QuadPype Qt widgets
    from PySide2 import QtWidgets
    import substance_painter.ui

    # Kill QuadPype Qt widgets
    print("Killing QuadPype Qt widgets..")
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.__module__.startswith("quadpype."):
            print(f"Deleting widget: {widget.__class__.__name__}")
            substance_painter.ui.delete_ui_element(widget)


def start_plugin():
    from quadpype.pipeline import install_host
    from quadpype.hosts.substancepainter.api import SubstanceHost
    install_host(SubstanceHost())


def close_plugin():
    from quadpype.pipeline import uninstall_host
    cleanup_quadpype_qt_widgets()
    uninstall_host()


if __name__ == "__main__":
    start_plugin()
