import notifypy
from quadpype.style import get_app_icon_path

def notify_message(title, message):
    notification = notifypy.Notify()
    notification.title = title
    notification.message = message
    notification.icon = get_app_icon_path()
    notification.send(block=False)
