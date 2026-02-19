import time
import pyautogui
import re

import win32gui
import win32con


SMALL_OFFSET = 10
LARGE_OFFSET = 50
IMPORT_AS_COMP_OPTION_INDEX = 2  # Starts from 0
ONLY_LETTERS_REGEX = r'[^a-zA-Z]'
TRIES = 5
DEFAULT_WAITING_TIME = 0.1

IMPORT_FILE = "Importer fichier"
IMPORT = "Importer sous :"


def try_several_times(function):
    """ Decorator to try to execute decorator function a certain number of times (defined by TRIES constant).
    Waiting time will gradually increase each loop to avoid large waiting times.
    """
    def wrapper(*args, **kwargs):
        attempt = 0
        while attempt < TRIES:
            result = function(*args, **kwargs)
            if result:
                return result

            time_to_wait = 0.1 + (attempt / 10)
            time.sleep(time_to_wait)
            attempt += 1

        return False

    return wrapper


def wait_after(time_to_wait):
    """ Decorator to wait a certain amount of time after function execution.
    """
    def decorator(function):
        def wrapper(*args, **kwargs):
            result = function(*args, **kwargs)
            time.sleep(time_to_wait)
            return result
        return wrapper
    return decorator


@try_several_times
def find_window_by_title(window_name):
    return win32gui.FindWindow(None, window_name)


@try_several_times
def find_window_by_partial_title(partial_title):
    result = {'hwnd': None}

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.startswith(partial_title):
                result['hwnd'] = hwnd
                return False

        return True

    win32gui.EnumWindows(callback, None)
    return result['hwnd']


@wait_after(DEFAULT_WAITING_TIME)
def force_foreground_window(hwnd):
    try:
        if not win32gui.IsWindow(hwnd):
            print("Given HWND is not valid.")
            return False

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)

        return True

    except Exception as e:
        print(f"An error has occured when forcing window to foreground : {e}")
        return False


def _pass_filter(hwnd, class_name, text):
    """ Filter retrieved windows handle with class name and text.
    We only keep letters from texts as specific characters (like special whitespaces) may be used in ui.
    """
    given_text = re.sub(ONLY_LETTERS_REGEX, '', text) if text else None
    element_text = re.sub(ONLY_LETTERS_REGEX, '', win32gui.GetWindowText(hwnd)) if text else None

    return (
        (not class_name or win32gui.GetClassName(hwnd) == class_name) and
        (not text or given_text == element_text)
    )


def get_controls(hwnd_parent, filter_by_class=None, filter_by_text=None, verbose=False):
    """ Get controls in given window, based on class or text (or nothing to get all existing and visible controls).

    Arguments:
        hwnd_parent (int): Window handle (hwnd) in which to look out for file selection view.
        filter_by_class (str): Get specific controls with class
        filter_by_class (str): Get specifics controls with text
        verbose (bool): display more details regarding analyzed elements.

    Returns:
        object: Control corresponding to file selection view.
    """
    controls = []
    controls_logs = []

    def callback(hwnd, _):
        try:
            class_name = win32gui.GetClassName(hwnd)
            if not _pass_filter(hwnd, filter_by_class, filter_by_text):
                return

            visible = win32gui.IsWindowVisible(hwnd)
            if not visible:
                return

            controls.append(hwnd)

            if not verbose:
                return

            text = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            enabled = win32gui.IsWindowEnabled(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            controls_logs.append({
                'hwnd': hwnd,
                'class': class_name,
                'text': text,
                'rect': rect,
                'size': (width, height),
                'visible': visible,
                'enabled': enabled
            })

        except Exception as e:
            print(f"Error with hwnd {hwnd}: {e}")
        return True

    # Callback for recursive items
    try:
        win32gui.EnumChildWindows(hwnd_parent, callback, None)

    except TypeError:
        pass

    # Sort by global size
    controls.sort(
        key=lambda c: (
            (win32gui.GetWindowRect(c)[2] - win32gui.GetWindowRect(c)[0]) +
            (win32gui.GetWindowRect(c)[3] - win32gui.GetWindowRect(c)[1])
        ),
        reverse=True
    )

    if not verbose:
        return controls

    print(f"Total number of controls found: {len(controls)}")

    for i, ctrl in enumerate(controls_logs):
        print(f"[{i:3d}] Class: {ctrl['class']:35} | "
              f"Text: {ctrl['text'][:40]:40} | "
              f"Size: {ctrl['size'][0]:4}x{ctrl['size'][1]:<4} | "
              f"Pos: ({ctrl['rect'][0]}, {ctrl['rect'][1]}) | "
              f"Enabled: {ctrl['enabled']}")

    print('\n')
    return controls


def get_file_selection_view(hwnd_parent, verbose=False):
    """ Get file selection view from given window.
    We assume that this is the second larger DirectUIHWND of the given window, as the first one seems
    to always correspond to the global window.

    Arguments:
        hwnd_parent (int): Window handle (hwnd) in which to look out for file selection view.
        verbose (bool): display more details regarding analyzed elements.

    Returns:
        object: Control corresponding to file selection view.
    """
    direct_huiwnd_windows = get_controls(hwnd_parent, filter_by_class="DirectUIHWND", verbose=verbose)
    windows_number = len(direct_huiwnd_windows)
    if not windows_number >= 2:
        print(f"Correct window should be the second of found windows, but only {windows_number} have been found.")
        return

    return direct_huiwnd_windows[1]


@wait_after(DEFAULT_WAITING_TIME)
def click_on_element(hwnd_list, offset=SMALL_OFFSET):
    if isinstance(offset, list) or isinstance(offset, tuple):
        x_offset, y_offset = offset

    else:
        x_offset = y_offset = offset

    rect = win32gui.GetWindowRect(hwnd_list)

    pyautogui.click(rect[0] + x_offset, rect[1] + y_offset)

    return True


def get_combobox(hwnd_parent, text, verbose=False):
    """ Retrieve combobox in given window based on given text

    Arguments:
        hwnd_parent (int): Window handle (hwnd) in which to look out for file selection view.
        text (str): Text corresponding to the label up to the desired combobox.
        verbose (bool): display more details regarding analyzed elements.

    Returns:
        object: Control corresponding to file selection view.
    """
    comboboxes = get_controls(hwnd_parent, filter_by_class="ComboBox", verbose=verbose)
    if not comboboxes:
        print("Can not find any combobox in import window.")
        return

    if verbose:
        print(f"Comboboxes found : {len(comboboxes)}")
        for i, cb in enumerate(comboboxes):
            print(f"  [{i}] {win32gui.GetClassName(cb)} - {win32gui.GetWindowText(cb)} - Y:{win32gui.GetWindowRect(cb)[1]}")
        print('\n')

    labels = get_controls(hwnd_parent, filter_by_class="Static", filter_by_text=text, verbose=verbose)
    if not labels:
        print("Can not find any label in import window.")
        return

    if verbose:
        print(f"Labels found : {len(labels)}")
        for i, lb in enumerate(labels):
            print(
                f"  [{i}] {win32gui.GetClassName(lb)} - {win32gui.GetWindowText(lb)}")
        print('\n')

    label = labels[0]

    label_y = win32gui.GetWindowRect(label)[1]

    # Get nearby combobox horizontally
    nearby = [
        cb for cb in comboboxes
        if abs(win32gui.GetWindowRect(cb)[1] - label_y) < 40
    ]

    if not nearby:
        print("Can not find any nearby combobox.")
        return

    return nearby[0]


@wait_after(DEFAULT_WAITING_TIME)
def select_item_from_opened_combobox(item_number):
    for _ in range(item_number):
        pyautogui.press('down')


@wait_after(DEFAULT_WAITING_TIME)
def press_enter_key():
    pyautogui.press('enter')


def import_file_dialog_clic(file_name, verbose=False):
    """ Automatically import file as Composition through After Effects window loader.
    This function is using win32gui to retrieve opened windows and UI element + pyautogui to
    simulate user clicks and key events.
    The followed steps are :
    1. Get main import window and put it foreground
    2. Get files treeview and click on first element
    3. Select import type combobox, click on it and select the third option with down arrow
    4. Press enter key to validate previous choice
    5. Press enter key to validate import
    6. Wait for second import window to appears by tring to retrieve it
    7. Press enter key to finalize import

    Arguments:
        file_name (str): Imported file name without frame information.
        verbose (bool): display more details regarding analyzed elements.

    Returns:
        bool: True if success, else None
    """
    print("Launching auto clic script.")
    # Get main window and put in foreground
    ae_import_window = find_window_by_title(IMPORT_FILE)
    if not ae_import_window:
        print("Can not find import window.")
        return

    if not force_foreground_window(ae_import_window):
        print("Can not force given window to foreground.")
        return

    # Retrieve files list window and click on first element
    file_selection_window = get_file_selection_view(ae_import_window, verbose=verbose)
    if not file_selection_window:
        print("Can not find file selection window.")
        return

    click_on_element(file_selection_window, offset=LARGE_OFFSET)

    # Get combobox and select third option
    combobox_found = get_combobox(ae_import_window, IMPORT, verbose=verbose)
    if not combobox_found:
        print(f"Can not find combobox with name '{IMPORT}' in current window.")
        return

    click_on_element(combobox_found)
    select_item_from_opened_combobox(IMPORT_AS_COMP_OPTION_INDEX)

    press_enter_key()  # Validate combobox option
    press_enter_key()  # Validate import

    # Wait for new window appearance and finalize import
    time.sleep(.5)
    new_import_window = find_window_by_partial_title(file_name)
    if not new_import_window:
        print("Can not find second import window to finalize process.")
        return

    if not force_foreground_window(new_import_window):
        print("Can not force given window to foreground.")
        return

    press_enter_key()  # Finalise import
    print("Import ended with success.")

    return True
