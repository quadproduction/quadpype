# -*- coding: utf-8 -*-
"""Module storing the API routes and functions to display notifications."""
from typing import Optional

from fastapi import APIRouter

from quadpype.tools.tray import SystemTrayIcon, get_tray_icon_widget


router = APIRouter(prefix="/notification", tags=["notification"])


@router.post("/tray/", tags=["tray"])
async def show_tray_message(message: str):
    tray_icon_widget: Optional[SystemTrayIcon] = get_tray_icon_widget()
    if tray_icon_widget:
        tray_icon_widget.showMessage("Notification", message)
    return {"message": "Message displayed"}
