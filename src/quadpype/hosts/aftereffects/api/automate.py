import cv2
import numpy as np
import pyautogui
import time
from mss import mss
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
        return Point(self.anchor_point.x + self.shape.width / 2, self.anchor_point.y + self.shape.height / 1.2)

    @property
    def bottom_limit(self):
        return Point(self.anchor_point.x + self.shape.width / 2, self.anchor_point.y + self.shape.height - 1)

    @property
    def left(self):
        return Point(self.anchor_point.x + self.shape.width / 8, self.anchor_point.y + self.shape.height / 2)

    @property
    def bottom_right(self):
        return Point(self.anchor_point.x + self.shape.width / 1.2, self.anchor_point.y + self.shape.height / 1.2)

    @property
    def bottom_left(self):
        return Point(self.anchor_point.x + self.shape.width / 8, self.anchor_point.y + self.shape.height / 1.2)


class ClickableElement:
    file_name: list[str]
    folder_path: str
    wait_after: float
    threshold: float
    default_click: str

    def __init__(self, files_names, folder_path, wait_after=0.0, threshold=0.5, click="center"):
        self.files_names = files_names
        self.folder_path = folder_path
        self.wait_after = wait_after
        self.threshold = threshold
        self.default_click = click

        if not all([file_path.is_file() for file_path in self.files_paths]):
            raise FileNotFoundError

    @property
    def files_paths(self):
        return [Path(self.folder_path, file_name) for file_name in self.files_names]

    def file_path(self, file_name):
        return Path(self.folder_path, file_name)

    def get_file_name(self, file_path):
        return getattr(file_path, "stem", Path(file_path).stem)


def get_combined_monitors_offset():
    with mss() as sct:
        return [sct.monitors[0]["left"], sct.monitors[0]["top"]]


def get_monitors_screenshot():
    with mss() as sct:
        screenshot = np.array(sct.grab(sct.monitors[0]))
        return cv2.cvtColor(screenshot, cv2.COLOR_RGB2RGBA)


def get_element_coordinates(template_path, screenshot, threshold, log, fixed_scale=None):
    template_path = Path(template_path)
    if not template_path.is_file():
        log.error(f"Can not find file at path {template_path}.")
        return

    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    template = cv2.cvtColor(template, cv2.COLOR_RGB2RGBA)
    template_height, template_width = template.shape[:2]

    found = get_match(
        scales=[fixed_scale] if fixed_scale else np.linspace(0.25, 1.0, 20)[::-1],
        screenshot=screenshot,
        template=template,
        log=log
    )

    if _match_is_not_valid(found, threshold) and fixed_scale:
        log.debug(
            f"No match found with previous memorized scale ({fixed_scale}). Will try again with all available spaces."
        )
        found = get_match(
            scales=np.linspace(0.25, 1.0, 20)[::-1],
            screenshot=screenshot,
            template=template,
            log=log
        )

    if _match_is_not_valid(found, threshold):
        log.warning(f"Can not found {template_path.stem} in user monitor.")
        return None, None

    return ElementCoordinates(
        point=Point(int(found.anchor_point.x * found.ratio), int(found.anchor_point.y * found.ratio)),
        shape=Shape(template_width * found.ratio, template_height * found.ratio)
    ), found.scale


def _match_is_not_valid(found, threshold):
    return found is None or found.confidence < threshold


def get_match(scales, screenshot, template, log):
    template_height, template_width = template.shape[:2]
    found = None

    for scale in scales:
        resized = imutils.resize(screenshot, width=int(screenshot.shape[1] * scale))
        ratio = screenshot.shape[1] / float(resized.shape[1])

        if resized.shape[0] < template_height or resized.shape[1] < template_width:
            log.warning("Resized screenshot is too large in comparison of given image. Process will be stopped.")
            break

        result = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, location = cv2.minMaxLoc(result)
        match_result = MatchResult(
            anchor_point=location,
            confidence=confidence,
            ratio=ratio,
            scale=scale
        )

        if not found or match_result.confidence > found.confidence:
            found = match_result

    return found


def move_cursor_and_click(coordinates, offset, log, click="center"):
    if not coordinates:
        log.error("Can not move cursor because coordinates are null.")
        return
    click_coordinates = getattr(coordinates, click)
    pyautogui.moveTo(offset[0] + click_coordinates.x, offset[1] + click_coordinates.y)
    pyautogui.click()
    return True


def import_file_dialog_clic(log):
    screen_offset = get_combined_monitors_offset()
    folder_path = Path(__file__).parent / "resources" / "auto_click" / platform.system().lower()

    assert folder_path.is_dir(), "Folder containing image ressources used for comparison can not be found."

    elements_to_click = list()

    try:
        elements_to_click.append(
            ClickableElement(
                files_names=["photoshop_file_icon_1.png", "photoshop_file_icon_2.png"],
                folder_path=folder_path,
                click="bottom_right"
            )
        )
        elements_to_click.append(ClickableElement(["metrage.png"], folder_path, click="bottom"))
        elements_to_click.append(ClickableElement(["composition.png"], folder_path, click="bottom_limit", wait_after=0.3))
        elements_to_click.append(ClickableElement(["importer.png"], folder_path, click="bottom_left", wait_after=0.3))
        elements_to_click.append(ClickableElement(["ok.png"], folder_path, click="left"))

    except FileNotFoundError as err:
        log.error("An error has occured when retrieving image for comparison. Abort process.")
        log.error(err)
        return False

    scale_used = None
    for concerned_element in elements_to_click:
        element_coordinates = None

        for file_path in concerned_element.files_paths:
            file_name = concerned_element.get_file_name(file_path)
            log.debug(f"Will try to click on element named {file_name}.")
            element_coordinates, scale_used = get_element_coordinates(
                file_path,
                get_monitors_screenshot(),
                concerned_element.threshold,
                log,
                fixed_scale=scale_used
            )

            if not element_coordinates:
                continue

            move_cursor_and_click(element_coordinates, screen_offset, log, click=concerned_element.default_click)
            log.info(f"Button named {file_name} has ben correctly clicked.")

            if concerned_element.wait_after:
                time.sleep(concerned_element.wait_after)

            break

        if not element_coordinates:
            log.error(f"Process has been aborted because button was not found.")
            return

    return True
