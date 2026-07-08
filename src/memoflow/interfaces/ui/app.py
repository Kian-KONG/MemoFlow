"""NiceGUI 页面注册入口。"""
from __future__ import annotations

from memoflow.container import AppContainer
from memoflow.interfaces.ui.pages.dashboard import register_dashboard_page
from memoflow.interfaces.ui.pages.meeting_detail import register_meeting_detail_page
from memoflow.interfaces.ui.pages.settings import register_settings_page


def register_ui(container: AppContainer) -> None:
    register_dashboard_page(container)
    register_meeting_detail_page(container)
    register_settings_page(container)
