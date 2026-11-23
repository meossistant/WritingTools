import os

import darkdetect
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QImage, QPixmap

from writing_tools.paths import get_resource_path

COLOR_MODE = "dark" if darkdetect.isDark() else "light"


class UIUtils:
    @classmethod
    def clear_layout(cls, layout):
        """Clear the layout of all child widgets, sub-layouts, and spacer items."""
        if layout is None:
            return
        while (child := layout.takeAt(0)) is not None:
            if child.layout() is not None:
                cls.clear_layout(child.layout())
                child.layout().deleteLater()
            elif child.widget() is not None:
                child.widget().deleteLater()

    @classmethod
    def resize_and_round_image(cls, image, image_size=100, rounding_amount=50):
        image = image.scaledToWidth(
            image_size, QtCore.Qt.TransformationMode.SmoothTransformation
        )
        clip_path = QtGui.QPainterPath()
        clip_path.addRoundedRect(0, 0, image_size, image_size, rounding_amount, rounding_amount)
        target = QImage(image_size, image_size, QImage.Format.Format_ARGB32)
        target.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(target)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setClipPath(clip_path)
        painter.drawImage(0, 0, image)
        painter.end()
        return QPixmap.fromImage(target)

    @classmethod
    def setup_window_and_layout(cls, base: QtWidgets.QWidget):
        icon_path = get_resource_path("icons", "app_icon.png")
        if os.path.exists(icon_path):
            base.setWindowIcon(QtGui.QIcon(icon_path))
        main_layout = QtWidgets.QVBoxLayout(base)
        main_layout.setContentsMargins(0, 0, 0, 0)
        base.background = ThemeBackground(base, "gradient")
        main_layout.addWidget(base.background)


class ThemeBackground(QtWidgets.QWidget):
    """A custom widget that draws a cached gradient or plain background based on theme."""

    _pixmap_cache: dict[tuple[bool, str], QtGui.QPixmap] = {}

    def __init__(self, parent=None, theme="gradient", is_popup=False, border_radius=0):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.theme = theme
        self.is_popup = is_popup
        self.border_radius = border_radius

    @classmethod
    def _get_background_pixmap(cls, is_popup: bool, mode: str) -> QtGui.QPixmap:
        cache_key = (is_popup, mode)
        pixmap = cls._pixmap_cache.get(cache_key)
        if pixmap is None:
            if is_popup:
                filename = "background_popup_dark.png" if mode == "dark" else "background_popup.png"
            else:
                filename = "background_dark.png" if mode == "dark" else "background.png"
            pixmap = QtGui.QPixmap(get_resource_path("backgrounds", filename))
            cls._pixmap_cache[cache_key] = pixmap
        return pixmap

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        if self.theme == "gradient":
            background_image = self._get_background_pixmap(self.is_popup, COLOR_MODE)
            path = QtGui.QPainterPath()
            path.addRoundedRect(
                0, 0, self.width(), self.height(), self.border_radius, self.border_radius
            )
            painter.setClipPath(path)
            if not background_image.isNull():
                painter.drawPixmap(self.rect(), background_image)
            else:
                fallback = (
                    QtGui.QColor(35, 35, 35)
                    if COLOR_MODE == "dark"
                    else QtGui.QColor(240, 240, 240)
                )
                painter.fillRect(self.rect(), fallback)
        else:
            color = (
                QtGui.QColor(35, 35, 35)
                if COLOR_MODE == "dark"
                else QtGui.QColor(222, 222, 222)
            )
            painter.setBrush(QtGui.QBrush(color))
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 0))
            pen.setWidth(0)
            painter.setPen(pen)
            painter.drawRoundedRect(
                QtCore.QRect(0, 0, self.width(), self.height()),
                self.border_radius,
                self.border_radius,
            )
        painter.end()
