# -*- coding: utf-8 -*-
"""Tools used in **Igniter** GUI."""
import os
import sys
from pathlib import Path


def is_running_locally():
    return "python" in os.path.basename(sys.executable).lower()


def load_stylesheet() -> str:
    """Load the CSS stylesheet.

    Returns:
        str: content of the stylesheet

    """
    stylesheet_path = Path(__file__).parent.resolve().joinpath(
        "resources", "style", "stylesheet.css")

    return stylesheet_path.read_text()


def get_app_icon_path(variation_name=None) -> str:
    """Path to the app icon png file.

    Returns:
        str: path of the png icon file

    """
    if not variation_name:
        variation_name = "default"

    icon_path = Path(__file__).parent.resolve().joinpath(
        "resources", "icons", "quadpype_icon_{}.png".format(variation_name))

    return str(icon_path)


def get_fonts_dir_path() -> str:
    """Path to the igniter fonts directory.

    Returns:
        str: path to the directory containing the font files

    """
    return str(Path(__file__).parent.resolve().joinpath("resources", "fonts"))
