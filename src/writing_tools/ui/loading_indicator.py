"""
Non-focus-stealing floating inline loading indicator (Issues #139, #206).

Appears near the cursor while an inline text replacement is in flight so the user
knows Writing Tools is actively working, and provides a one-click Cancel button
without taking keyboard focus away from the target editor.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from writing_tools.ui.ui_utils import COLOR_MODE


class InlineLoadingIndicator(QtWidgets.QWidget):
    """Compact floating progress pill shown near the cursor during inline operations."""

    def __init__(self, on_cancel: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self._on_cancel = on_cancel
        self._base_text = "Working"
        self._dot_index = 0
        self._dots = ["", ".", "..", "..."]

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        container = QtWidgets.QFrame(self)
        container.setObjectName("pill")
        bg = "rgba(35, 35, 38, 235)" if COLOR_MODE == "dark" else "rgba(255, 255, 255, 242)"
        fg = "#ffffff" if COLOR_MODE == "dark" else "#222222"
        border = "#555555" if COLOR_MODE == "dark" else "#cccccc"
        hover_bg = "#555555" if COLOR_MODE == "dark" else "#e5e5e5"

        container.setStyleSheet(
            f"""
            QFrame#pill {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel {{
                color: {fg};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
            QPushButton {{
                background-color: transparent;
                color: {fg};
                border: none;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        row = QtWidgets.QHBoxLayout(container)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(8)

        self.status_label = QtWidgets.QLabel("Working...")
        self.status_label.setMinimumWidth(110)
        row.addWidget(self.status_label)

        self.cancel_btn = QtWidgets.QPushButton("×")
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.setToolTip("Cancel request")
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.clicked.connect(self._handle_cancel)
        row.addWidget(self.cancel_btn)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._dot_index = (self._dot_index + 1) % len(self._dots)
        self.status_label.setText(f"{self._base_text}{self._dots[self._dot_index]}")

    def _handle_cancel(self):
        self.hide_indicator()
        if self._on_cancel is not None:
            self._on_cancel()

    def show_for_action(self, action_label: str = "Working"):
        """Show the floating pill near the cursor without activating or stealing focus."""
        self._base_text = action_label.strip() or "Working"
        self._dot_index = 0
        self.status_label.setText(f"{self._base_text}...")
        self.adjustSize()

        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        x = cursor_pos.x() + 16
        y = cursor_pos.y() + 16
        if screen is not None:
            geo = screen.geometry()
            if x + self.width() > geo.right():
                x = max(geo.left(), cursor_pos.x() - self.width() - 12)
            if y + self.height() > geo.bottom():
                y = max(geo.top(), cursor_pos.y() - self.height() - 12)
        self.move(x, y)
        self.show()
        self._timer.start()

    def hide_indicator(self):
        self._timer.stop()
        if self.isVisible():
            self.hide()
