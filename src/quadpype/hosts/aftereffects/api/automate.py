import cv2
import numpy as np
import pyautogui
import time
from mss import mss
import logging
import platform
import imutils
from pathlib import Path


class Point:
    x: int
    y: int

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)


class Shape:
    width: int
    height: int

    def __init__(self, width, height):
        self.width = width
        self.height = height

    def __add__(self, other):
        return Shape(self.width + other.width, self.height + other.height)

    @property
    def center(self):
        return Point(self.width / 2, self.height / 2)


class MatchResult:
    anchor_point: Point
    confidence: float
    ratio: float
    scale: float

    def __init__(self, anchor_point, confidence, ratio, scale):
        self.anchor_point = Point(anchor_point[0], anchor_point[1])
        self.confidence = confidence
        self.ratio = ratio
        self.scale = scale


class ElementCoordinates:
    anchor_point: Point
    shape: Shape
    default_click: None

    def __init__(self, point, shape):
        self.anchor_point = point
        self.shape = shape

    def __add__(self, other):
        return ElementCoordinates(self.anchor_point + other.anchor_point, self.shape + other.shape)

    @property
    def center(self):
        return Point(self.anchor_point.x + self.shape.width / 2, self.anchor_point.y + self.shape.height / 2)

    @property
    def bottom(self):
        return Point(self.anchor_point.x + self.shape.width / 2, self.anchor_point.y + (self.shape.height / 1.25))


class ClickableElement:
    file_name: str
    folder_path: str
    wait_after: float
    threshold: float
    default_click: str

    def __init__(self, file_name, folder_path, wait_after=0.0, threshold=0.7, click="center"):
        self.file_name = file_name
        self.folder_path = folder_path
        self.wait_after = wait_after
        self.threshold = threshold
        self.default_click = click

        file_path = Path(folder_path, file_name)
        if not file_path.is_file():
            logging.error(f"File at path {file_path} does not exists.")
            raise FileNotFoundError

    @property
    def file_path(self):
        return str(Path(self.folder_path, self.file_name))


def get_combined_monitors_offset():
    with mss() as sct:
        return [sct.monitors[0]["left"], sct.monitors[0]["top"]]


def get_monitors_screenshot():
    with mss() as sct:
        screenshot = np.array(sct.grab(sct.monitors[0]))
        return cv2.cvtColor(screenshot, cv2.COLOR_RGB2HSV)


def get_element_coordinates(template_path, screenshot, threshold, fixed_scale=None):
    template_path = Path(template_path)
    if not template_path.is_file():
        logging.error(f"Can not find file at path {template_path}.")
        return

    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    template = cv2.cvtColor(template, cv2.COLOR_RGB2HSV)
    template_height, template_width = template.shape[:2]

    found = get_match(
        scales=[fixed_scale] if fixed_scale else np.linspace(0.25, 1.0, 20)[::-1],
        screenshot=screenshot,
        template=template
    )

    if not found and fixed_scale:
        logging.debug(
            f"No match found with previous memorized scale ({fixed_scale}). Will try again with all available spaces."
        )
        found = get_match(
            scales=np.linspace(0.25, 1.0, 20)[::-1],
            screenshot=screenshot,
            template=template
        )

    if found is None or found.confidence < threshold:
        logging.warning(f"Can not found {template_path.stem} in user monitor.")
        return None, None

    return ElementCoordinates(
        point=Point(int(found.anchor_point.x * found.ratio), int(found.anchor_point.y * found.ratio)),
        shape=Shape(template_width, template_height)
    ), found.scale


def get_match(scales, screenshot, template):
    template_height, template_width = template.shape[:2]
    found = None
    get_first_result = len(scales) == 1

    for scale in scales:
        resized = imutils.resize(screenshot, width=int(screenshot.shape[1] * scale))
        ratio = screenshot.shape[1] / float(resized.shape[1])

        if resized.shape[0] < template_height or resized.shape[1] < template_width:
            logging.warning("Resized screenshot is too large in comparison of given image. Process will be stopped.")
            break

        result = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, location = cv2.minMaxLoc(result)

        match_result = MatchResult(
            anchor_point=location,
            confidence=confidence,
            ratio=ratio,
            scale=scale
        )

        if get_first_result:
            return match_result

        if found and match_result.confidence < found.confidence:
            return found

        found = match_result

    return None


def move_cursor_and_click(coordinates, offset, click="center"):
    if not coordinates:
        logging.error("Can not move cursor because coordinates are null.")
        return
    click_coordinates = getattr(coordinates, click)
    pyautogui.moveTo(offset[0] + click_coordinates.x, offset[1] + click_coordinates.y)
    pyautogui.click()
    return True


def import_file_dialog_clic():
    screen_offset = get_combined_monitors_offset()
    folder_path = Path(__file__).parent / "resources" / "auto_click" / platform.system().lower()

    assert folder_path.is_dir(), "Folder containing image ressources used for comparison can not be found."

    elements_to_click = list()

    try:
        elements_to_click.append(ClickableElement("photoshop_file_icon.png", folder_path))
        elements_to_click.append(ClickableElement("metrage.png", folder_path, wait_after=0.1))
        elements_to_click.append(ClickableElement("composition.png", folder_path, click="bottom"))
        elements_to_click.append(ClickableElement("importer.png", folder_path, wait_after=0.2))
        elements_to_click.append(ClickableElement("ok.png", folder_path))

    except FileNotFoundError:
        logging.error("An error has occured when retrieving image for comparison. Abort process.")
        return False

    scale_used = None
    for concerned_element in elements_to_click:
        logging.debug(f"Will try to click on element named {concerned_element.file_name}.")
        element_coordinates, scale_used = get_element_coordinates(
            concerned_element.file_path,
            get_monitors_screenshot(),
            concerned_element.threshold,
            fixed_scale=scale_used
        )
        if not element_coordinates:
            logging.error(f"Process has been aborted because button was not found.")
            return

        move_cursor_and_click(element_coordinates, screen_offset, click=concerned_element.default_click)
        logging.debug(f"Button named {concerned_element.file_name} has ben correctly clicked.")

        if concerned_element.wait_after:
            time.sleep(concerned_element.wait_after)

    return True
