import logging
import os

import markdown2
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QScrollArea

from writing_tools.diff_utils import build_word_diff
from writing_tools.paths import get_resource_path
from writing_tools.ui.ui_utils import COLOR_MODE, UIUtils

_ = lambda x: x


class MarkdownTextBrowser(QtWidgets.QTextBrowser):
    """Enhanced text browser for displaying Markdown content with dynamic height sizing."""

    def __init__(self, parent=None, is_user_message=False):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.zoom_factor = 1.2
        self.base_font_size = 14
        self.is_user_message = is_user_message

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        self._apply_zoom()

    def _apply_zoom(self):
        new_size = int(self.base_font_size * self.zoom_factor)

        self.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {('transparent' if self.is_user_message else '#333' if COLOR_MODE == 'dark' else 'white')};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: {('none' if self.is_user_message else '1px solid ' + ('#555' if COLOR_MODE == 'dark' else '#ccc'))};
                border-radius: 8px;
                padding: 8px;
                margin: 0px;
                font-size: {new_size}px;
                line-height: 1.3;
                width: 100%;
            }}

            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10px 0;
            }}

            th, td {{
                border: 1px solid {'#555' if COLOR_MODE == 'dark' else '#ccc'};
                padding: 8px;
                text-align: left;
            }}

            th {{
                background-color: {'#444' if COLOR_MODE == 'dark' else '#f5f5f5'};
                font-weight: bold;
            }}

            tr:nth-child(even) {{
                background-color: {'#3a3a3a' if COLOR_MODE == 'dark' else '#f9f9f9'};
            }}

            tr:hover {{
                background-color: {'#484848' if COLOR_MODE == 'dark' else '#f0f0f0'};
            }}

            pre, code {{
                background-color: {'#252525' if COLOR_MODE == 'dark' else '#f4f4f4'};
                font-family: monospace;
            }}
        """
        )

    def _update_size(self):
        available_width = max(100, self.viewport().width() - 16)
        self.document().setTextWidth(available_width)

        doc_size = self.document().size()
        new_height = int(doc_size.height() + 16)

        if self.minimumHeight() != new_height:
            self.setMinimumHeight(new_height)
            self.setMaximumHeight(new_height)

            scroll_area = self.get_scroll_area()
            if scroll_area:
                scroll_area.update_content_height()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            parent = self.parent()
            while parent and not isinstance(parent, ResponseWindow):
                parent = parent.parent()

            if parent:
                if delta > 0:
                    parent.zoom_all_messages("in")
                else:
                    parent.zoom_all_messages("out")
                event.accept()
        else:
            if self.parent():
                self.parent().wheelEvent(event)

    def zoom_in(self):
        old_factor = self.zoom_factor
        self.zoom_factor = min(3.0, self.zoom_factor * 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def zoom_out(self):
        old_factor = self.zoom_factor
        self.zoom_factor = max(0.5, self.zoom_factor / 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def reset_zoom(self):
        old_factor = self.zoom_factor
        self.zoom_factor = 1.2
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()

    def get_scroll_area(self):
        parent = self.parent()
        while parent:
            if isinstance(parent, ChatContentScrollArea):
                return parent
            parent = parent.parent()
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_size()


class ChatContentScrollArea(QScrollArea):
    """Scrollable container for chat messages with dynamic sizing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.content_widget = None
        self.layout = None
        self.setup_ui()

    def get_response_window(self):
        """Walk up the widget hierarchy to locate the owning ResponseWindow."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ResponseWindow):
                return parent
            parent = parent.parent()
        return None

    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )
        self.setWidget(self.content_widget)

        self.layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.addStretch()

        self.setStyleSheet(
            """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(128, 128, 128, 0.5);
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        )

    def add_message(self, text, is_user=False):
        # Remove bottom stretch
        self.layout.takeAt(self.layout.count() - 1)

        msg_container = QtWidgets.QWidget()
        msg_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        msg_layout = QtWidgets.QVBoxLayout(msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(0)

        text_display = MarkdownTextBrowser(is_user_message=is_user)
        html = markdown2.markdown(text, extras=["tables", "strike", "fenced-code-blocks"])
        text_display.setHtml(html)

        available_width = max(100, self.width() - 40)
        text_display.document().setTextWidth(available_width)
        doc_size = text_display.document().size()
        text_display.setMinimumHeight(int(doc_size.height() + 16))

        msg_layout.addWidget(text_display)

        self.layout.addWidget(msg_container)
        self.layout.addStretch()

        response_window = self.get_response_window()
        if response_window is not None:
            response_window.current_text_display = text_display

        QtCore.QTimer.singleShot(50, self.post_message_updates)
        return text_display

    def remove_last_message(self):
        """Remove the most recently added message widget (used by Regenerate)."""
        # Layout always ends with a trailing stretch item
        if self.layout.count() <= 1:
            return
        item = self.layout.takeAt(self.layout.count() - 2)
        removed_widget = item.widget() if item else None
        response_window = self.get_response_window()
        if removed_widget is not None:
            if response_window is not None:
                if (
                    response_window.current_text_display is not None
                    and removed_widget.isAncestorOf(response_window.current_text_display)
                ):
                    response_window.current_text_display = None
                if (
                    response_window.first_response_display is not None
                    and removed_widget.isAncestorOf(response_window.first_response_display)
                ):
                    response_window.first_response_display = None
            removed_widget.setParent(None)
            removed_widget.deleteLater()
        self.update_content_height()

    def clear_messages(self):
        """Remove all message widgets while preserving the trailing stretch."""
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
        self.update_content_height()

    def post_message_updates(self):
        self.scroll_to_bottom()
        response_window = self.get_response_window()
        if response_window is not None:
            response_window._adjust_window_height()

    def update_content_height(self):
        total_height = 0
        for i in range(self.layout.count() - 1):
            item = self.layout.itemAt(i)
            if item and item.widget():
                total_height += item.widget().sizeHint().height()

        msg_count = max(0, self.layout.count() - 1)
        if msg_count > 1:
            total_height += self.layout.spacing() * (msg_count - 1)
        margins = self.layout.contentsMargins()
        total_height += margins.top() + margins.bottom()

        self.content_widget.setMinimumHeight(total_height + 10)

        response_window = self.get_response_window()
        if response_window is not None:
            response_window._adjust_window_height()

    def scroll_to_bottom(self):
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        available_width = max(100, self.width() - 40)
        for i in range(self.layout.count() - 1):
            item = self.layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                text_display = container.layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    text_display.document().setTextWidth(available_width)
                    doc_size = text_display.document().size()
                    text_display.setMinimumHeight(int(doc_size.height() + 20))


class ResponseWindow(QtWidgets.QWidget):
    """
    Response window with Markdown rendering, word-level diff toggle (#284),
    one-click regeneration (#148), collapsible original text (#127),
    formatted & Markdown copy, zoom persistence, and follow-up chat.
    """

    def __init__(self, app, title=_("Response"), parent=None):
        super().__init__(parent)
        self.app = app
        self.original_title = title
        self.setWindowTitle(title)
        self.option = title.replace(" Result", "")
        self.selected_text = None
        self.custom_change = None
        self.active_provider = None
        self.model_override = None
        self.input_field = None
        self.loading_label = None
        self.loading_container = None
        self.chat_area = None
        self.current_text_display = None
        self.first_response_display = None
        self.first_response_markdown = ""
        self.diff_mode = False
        self.result_mode_btn = None
        self.changes_mode_btn = None
        self.regenerate_btn = None
        self.original_toggle_btn = None
        self.original_text_box = None
        self.status_banner = None
        self.chat_history = []
        self._closed = False

        self.thinking_timer = QtCore.QTimer(self)
        self.thinking_timer.timeout.connect(self.update_thinking_dots)
        self.thinking_dots_state = 0
        self.thinking_dots = ["", ".", "..", "..."]
        self.thinking_timer.setInterval(300)

        self.init_ui()
        self.resize(640, 440)

    def init_ui(self):
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowCloseButtonHint
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setMinimumSize(620, 420)

        UIUtils.setup_window_and_layout(self)
        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(10)

        top_bar = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel(self.option)
        title_label.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        top_bar.addWidget(title_label)
        top_bar.addStretch()

        # Regenerate button (#148) using bundled regenerate_{dark,light}.png icon
        self.regenerate_btn = QtWidgets.QPushButton()
        regen_icon_path = get_resource_path(
            "icons", "regenerate" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(regen_icon_path):
            self.regenerate_btn.setIcon(QtGui.QIcon(regen_icon_path))
        else:
            self.regenerate_btn.setText("R")
        self.regenerate_btn.setStyleSheet(self.get_button_style())
        self.regenerate_btn.setToolTip(_("Regenerate latest response"))
        self.regenerate_btn.clicked.connect(self.regenerate_latest_response)
        self.regenerate_btn.setFixedSize(30, 30)
        self.regenerate_btn.setEnabled(False)
        top_bar.addWidget(self.regenerate_btn)

        zoom_label = QtWidgets.QLabel("Zoom:")
        zoom_label.setStyleSheet(
            f"""
            color: {'#aaaaaa' if COLOR_MODE == 'dark' else '#666666'};
            font-size: 14px;
            margin-left: 8px;
            margin-right: 5px;
        """
        )
        top_bar.addWidget(zoom_label)

        zoom_controls = [
            ("plus", "Zoom In", lambda: self.zoom_all_messages("in")),
            ("minus", "Zoom Out", lambda: self.zoom_all_messages("out")),
            ("reset", "Reset Zoom", lambda: self.zoom_all_messages("reset")),
        ]

        for icon, tooltip, action in zoom_controls:
            btn = QtWidgets.QPushButton()
            icon_path = get_resource_path(
                "icons", icon + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
            )
            if os.path.exists(icon_path):
                btn.setIcon(QtGui.QIcon(icon_path))
            btn.setStyleSheet(self.get_button_style())
            btn.setToolTip(tooltip)
            btn.clicked.connect(action)
            btn.setFixedSize(30, 30)
            top_bar.addWidget(btn)

        content_layout.addLayout(top_bar)

        # Optional status notice banner (e.g., focus changed before paste)
        self.status_banner = QtWidgets.QLabel()
        self.status_banner.setWordWrap(True)
        self.status_banner.setStyleSheet(
            f"""
            QLabel {{
                background-color: {'#3a3218' if COLOR_MODE == 'dark' else '#fef9c3'};
                color: {'#fde68a' if COLOR_MODE == 'dark' else '#854d0e'};
                border: 1px solid {'#713f12' if COLOR_MODE == 'dark' else '#facc15'};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
        """
        )
        self.status_banner.hide()
        content_layout.addWidget(self.status_banner)

        # Action bar: [Result | Changes] toggle, Original toggle, Copy Formatted, Copy as Markdown
        action_bar = QtWidgets.QHBoxLayout()
        action_bar.setSpacing(6)

        self.result_mode_btn = QtWidgets.QPushButton(_("Result"))
        self.result_mode_btn.setCheckable(True)
        self.result_mode_btn.setChecked(True)
        self.result_mode_btn.setEnabled(False)
        self.result_mode_btn.setStyleSheet(self._get_toggle_button_style())
        self.result_mode_btn.clicked.connect(lambda: self.set_diff_mode(False))
        action_bar.addWidget(self.result_mode_btn)

        self.changes_mode_btn = QtWidgets.QPushButton(_("Changes"))
        self.changes_mode_btn.setCheckable(True)
        self.changes_mode_btn.setChecked(False)
        self.changes_mode_btn.setEnabled(False)
        self.changes_mode_btn.setToolTip(_("Show word-level diff against original selection"))
        self.changes_mode_btn.setStyleSheet(self._get_toggle_button_style())
        self.changes_mode_btn.clicked.connect(lambda: self.set_diff_mode(True))
        action_bar.addWidget(self.changes_mode_btn)

        self.original_toggle_btn = QtWidgets.QPushButton(_("Original"))
        self.original_toggle_btn.setCheckable(True)
        self.original_toggle_btn.setChecked(False)
        self.original_toggle_btn.setToolTip(_("Show or hide the original selected text"))
        self.original_toggle_btn.setStyleSheet(self._get_toggle_button_style())
        self.original_toggle_btn.toggled.connect(self._toggle_original_panel)
        action_bar.addWidget(self.original_toggle_btn)

        action_bar.addStretch()

        copy_fmt_btn = QtWidgets.QPushButton(_("Copy Formatted"))
        copy_fmt_btn.setToolTip(_("Copy latest response as formatted rich text"))
        copy_fmt_btn.setStyleSheet(self.get_button_style())
        copy_fmt_btn.clicked.connect(self.copy_latest_formatted)
        action_bar.addWidget(copy_fmt_btn)

        copy_md_btn = QtWidgets.QPushButton(_("Copy as Markdown"))
        copy_md_btn.setToolTip(_("Copy latest response as Markdown"))
        copy_md_btn.setStyleSheet(self.get_button_style())
        copy_md_btn.clicked.connect(self.copy_latest_response)
        action_bar.addWidget(copy_md_btn)
        content_layout.addLayout(action_bar)

        # Collapsible original text viewer (#127)
        self.original_text_box = QtWidgets.QPlainTextEdit()
        self.original_text_box.setReadOnly(True)
        self.original_text_box.setMaximumHeight(110)
        self.original_text_box.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {'#2a2a2a' if COLOR_MODE == 'dark' else '#f8f9fa'};
                color: {'#dddddd' if COLOR_MODE == 'dark' else '#333333'};
                border: 1px solid {'#555' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }}
        """
        )
        self.original_text_box.hide()
        content_layout.addWidget(self.original_text_box)

        loading_container = QtWidgets.QWidget()
        loading_layout = QtWidgets.QHBoxLayout(loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)

        self.loading_label = QtWidgets.QLabel(_("Thinking"))
        self.loading_label.setStyleSheet(
            f"""
            QLabel {{
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};
                font-size: 18px;
                padding: 20px;
            }}
        """
        )
        self.loading_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        loading_inner_container = QtWidgets.QWidget()
        loading_inner_container.setFixedWidth(180)
        loading_inner_layout = QtWidgets.QHBoxLayout(loading_inner_container)
        loading_inner_layout.setContentsMargins(0, 0, 0, 0)
        loading_inner_layout.addWidget(self.loading_label)

        loading_layout.addStretch()
        loading_layout.addWidget(loading_inner_container)
        loading_layout.addStretch()

        content_layout.addWidget(loading_container)
        self.loading_container = loading_container

        self.start_thinking_animation(initial=True)

        self.chat_area = ChatContentScrollArea()
        content_layout.addWidget(self.chat_area)

        bottom_bar = QtWidgets.QHBoxLayout()

        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText(_("Ask a follow-up question") + "...")
        self.input_field.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if COLOR_MODE == 'dark' else 'white'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                font-size: 14px;
            }}
        """
        )
        self.input_field.returnPressed.connect(self.send_message)
        bottom_bar.addWidget(self.input_field)

        send_button = QtWidgets.QPushButton()
        send_icon = get_resource_path(
            "icons", "send" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(send_icon):
            send_button.setIcon(QtGui.QIcon(send_icon))
        send_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {'#2e7d32' if COLOR_MODE == 'dark' else '#4CAF50'};
                border: none;
                border-radius: 8px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {'#1b5e20' if COLOR_MODE == 'dark' else '#45a049'};
            }}
        """
        )
        send_button.setFixedSize(
            self.input_field.sizeHint().height(), self.input_field.sizeHint().height()
        )
        send_button.clicked.connect(self.send_message)
        bottom_bar.addWidget(send_button)

        content_layout.addLayout(bottom_bar)

    def get_first_response_text(self):
        try:
            for msg in self.chat_history:
                if msg.get("role") == "assistant":
                    return msg.get("content")
            return None
        except Exception as e:
            logging.error(f"Error getting first response: {e}")
            return None

    def get_latest_response_text(self):
        """Return the most recent assistant response in the conversation."""
        try:
            for msg in reversed(self.chat_history):
                if msg.get("role") == "assistant":
                    return msg.get("content")
            return None
        except Exception as e:
            logging.error(f"Error getting latest response: {e}")
            return None

    def copy_first_response(self):
        response_text = self.get_first_response_text()
        if response_text:
            QtWidgets.QApplication.clipboard().setText(response_text)

    def copy_latest_response(self):
        """Copy the latest AI response as Markdown (fixing follow-up copy behavior)."""
        response_text = self.get_latest_response_text()
        if response_text:
            QtWidgets.QApplication.clipboard().setText(response_text)

    def copy_latest_formatted(self):
        """Copy the latest AI response as formatted rich text + clean plain text (#127)."""
        response_text = self.get_latest_response_text()
        if not response_text:
            return
        html_content = markdown2.markdown(
            response_text, extras=["tables", "strike", "fenced-code-blocks"]
        )
        helper = QtWidgets.QTextEdit()
        helper.setHtml(html_content)
        helper.selectAll()
        helper.copy()

    def set_status_notice(self, message: str):
        """Show or hide an informational banner inside the response window."""
        if not self.status_banner:
            return
        if message:
            self.status_banner.setText(message)
            self.status_banner.show()
        else:
            self.status_banner.hide()

    def _toggle_original_panel(self, checked: bool):
        if self.original_text_box is None:
            return
        if checked:
            self.original_text_box.setPlainText(self.selected_text or "")
            self.original_text_box.show()
        else:
            self.original_text_box.hide()

    def set_diff_mode(self, show_diff: bool):
        """Switch the initial response between rendered Markdown (`Result`) and word-level diff (`Changes`)."""
        self.diff_mode = bool(show_diff)
        if self.result_mode_btn is not None:
            self.result_mode_btn.setChecked(not self.diff_mode)
        if self.changes_mode_btn is not None:
            self.changes_mode_btn.setChecked(self.diff_mode)

        if self.first_response_display is None or not self.first_response_markdown:
            return

        if self.diff_mode and self.selected_text is not None:
            diff_res = build_word_diff(
                self.selected_text, self.first_response_markdown, color_mode=COLOR_MODE
            )
            self.first_response_display.setHtml(diff_res.html)
        else:
            html_content = markdown2.markdown(
                self.first_response_markdown, extras=["tables", "strike", "fenced-code-blocks"]
            )
            self.first_response_display.setHtml(html_content)
        self.first_response_display._update_size()

    def regenerate_latest_response(self):
        """Regenerate the latest assistant response in-place (#148)."""
        if self._closed or not hasattr(self.app, "regenerate_response"):
            return

        # Determine whether we are regenerating the initial turn or a follow-up turn
        is_initial = sum(1 for m in self.chat_history if m.get("role") == "assistant") <= 1

        if self.chat_history and self.chat_history[-1].get("role") == "assistant":
            self.chat_history.pop()
            self.chat_area.remove_last_message()

        if is_initial:
            self.first_response_display = None
            self.first_response_markdown = ""
            self.diff_mode = False
            if self.result_mode_btn is not None:
                self.result_mode_btn.setChecked(True)
                self.result_mode_btn.setEnabled(False)
            if self.changes_mode_btn is not None:
                self.changes_mode_btn.setChecked(False)
                self.changes_mode_btn.setEnabled(False)

        if self.regenerate_btn is not None:
            self.regenerate_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self.start_thinking_animation(initial=is_initial)
        self.app.regenerate_response(self, is_initial=is_initial)

    def _get_toggle_button_style(self):
        return f"""
            QPushButton {{
                background-color: {'#444' if COLOR_MODE == 'dark' else '#f0f0f0'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QPushButton:checked {{
                background-color: {'#2e7d32' if COLOR_MODE == 'dark' else '#0078d4'};
                color: #ffffff;
                border: 1px solid {'#4caf50' if COLOR_MODE == 'dark' else '#005a9e'};
                font-weight: bold;
            }}
            QPushButton:disabled {{
                color: {'#777' if COLOR_MODE == 'dark' else '#999'};
            }}
        """

    def get_button_style(self):
        return f"""
            QPushButton {{
                background-color: {'#444' if COLOR_MODE == 'dark' else '#f0f0f0'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {'#555' if COLOR_MODE == 'dark' else '#e0e0e0'};
            }}
        """

    def update_thinking_dots(self):
        self.thinking_dots_state = (self.thinking_dots_state + 1) % len(self.thinking_dots)
        dots = self.thinking_dots[self.thinking_dots_state]

        if self.loading_label.isVisible():
            self.loading_label.setText(_("Thinking") + f"{dots}")
        else:
            self.input_field.setPlaceholderText(_("Thinking") + f"{dots}")

    def start_thinking_animation(self, initial=False):
        self.thinking_dots_state = 0
        if initial:
            self.loading_label.setText(_("Thinking"))
            self.loading_label.setVisible(True)
            self.loading_container.setVisible(True)
        else:
            self.input_field.setPlaceholderText(_("Thinking"))
            self.loading_container.setVisible(False)
        self.thinking_timer.start()

    @Slot()
    def stop_thinking_animation(self):
        self.thinking_timer.stop()
        self.loading_container.hide()
        self.loading_label.hide()
        self.input_field.setPlaceholderText(_("Ask a follow-up question") + "...")
        self.input_field.setEnabled(True)
        if self.regenerate_btn is not None:
            self.regenerate_btn.setEnabled(bool(self.chat_history))

        if self.layout():
            self.layout().invalidate()
            self.layout().activate()

    def zoom_all_messages(self, action="in"):
        for i in range(self.chat_area.layout.count() - 1):
            item = self.chat_area.layout.itemAt(i)
            if item and item.widget():
                text_display = item.widget().layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    if action == "in":
                        text_display.zoom_in()
                    elif action == "out":
                        text_display.zoom_out()
                    else:
                        text_display.reset_zoom()

        self.chat_area.update_content_height()

    def _adjust_window_height(self):
        if hasattr(self, "_size_initialized"):
            return

        try:
            content_height = self.chat_area.content_widget.sizeHint().height()
            ui_elements_height = (
                self.layout().contentsMargins().top()
                + self.layout().contentsMargins().bottom()
                + self.input_field.height()
                + self.layout().spacing() * 5
                + 200
            )

            screen = QtWidgets.QApplication.screenAt(self.pos()) or QtWidgets.QApplication.primaryScreen()
            max_height = int(screen.geometry().height() * 0.85)

            desired_content_height = int(content_height * 0.85)
            desired_total_height = min(desired_content_height + ui_elements_height, max_height)
            final_height = max(600, desired_total_height)
            final_width = 640

            self.resize(final_width, final_height)

            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(screen.geometry().center())
            self.move(frame_geometry.topLeft())
            self._size_initialized = True
        except Exception as e:
            logging.error(f"Error adjusting window height: {e}")
            self.resize(640, 600)
            self._size_initialized = True

    def _get_current_zoom(self) -> float:
        if self.current_text_display is not None:
            return self.current_text_display.zoom_factor
        if isinstance(self.app.config, dict) and "response_window_zoom" in self.app.config:
            try:
                return float(self.app.config["response_window_zoom"])
            except (TypeError, ValueError):
                pass
        return 1.2

    @Slot(str)
    def set_text(self, text):
        if self._closed:
            return
        if not text or not text.strip():
            self.stop_thinking_animation()
            return

        self.chat_history = [
            {"role": "user", "content": f"{self.option}: {self.selected_text}"},
            {"role": "assistant", "content": text},
        ]
        self.first_response_markdown = text

        self.stop_thinking_animation()
        zoom = self._get_current_zoom()
        text_display = self.chat_area.add_message(text)
        text_display.zoom_factor = zoom
        text_display._apply_zoom()
        text_display._update_size()
        self.first_response_display = text_display

        has_original = bool(self.selected_text)
        if self.result_mode_btn is not None:
            self.result_mode_btn.setEnabled(has_original)
            self.result_mode_btn.setChecked(True)
        if self.changes_mode_btn is not None:
            self.changes_mode_btn.setEnabled(has_original)
            self.changes_mode_btn.setChecked(False)
        if self.regenerate_btn is not None:
            self.regenerate_btn.setEnabled(True)
        if self.original_text_box is not None and self.original_text_box.isVisible():
            self.original_text_box.setPlainText(self.selected_text or "")

        QtCore.QTimer.singleShot(100, self._adjust_window_height)

    @Slot(str)
    def handle_followup_response(self, response_text):
        if self._closed:
            return
        if response_text:
            self.loading_label.setVisible(False)
            zoom = self._get_current_zoom()
            text_display = self.chat_area.add_message(response_text)
            text_display.zoom_factor = zoom
            text_display._apply_zoom()
            text_display._update_size()

            if not self.chat_history or self.chat_history[-1].get("role") != "assistant":
                self.chat_history.append({"role": "assistant", "content": response_text})

        self.stop_thinking_animation()
        self.input_field.setEnabled(True)
        if self.regenerate_btn is not None:
            self.regenerate_btn.setEnabled(True)
        QtCore.QTimer.singleShot(100, self._adjust_window_height)

    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return

        self.input_field.setEnabled(False)
        if self.regenerate_btn is not None:
            self.regenerate_btn.setEnabled(False)
        self.input_field.clear()

        zoom = self._get_current_zoom()
        text_display = self.chat_area.add_message(message, is_user=True)
        text_display.zoom_factor = zoom
        text_display._apply_zoom()
        text_display._update_size()

        self.chat_history.append({"role": "user", "content": message})
        self.start_thinking_animation()
        self.app.process_followup_question(self, message)

    def copy_as_markdown(self):
        markdown = ""
        for msg in self.chat_history:
            if msg["role"] == "user":
                markdown += f"**User**: {msg['content']}\n\n"
            else:
                markdown += f"**Assistant**: {msg['content']}\n\n"
        QtWidgets.QApplication.clipboard().setText(markdown)

    def closeEvent(self, event):
        self._closed = True
        self.thinking_timer.stop()

        if self.current_text_display is not None and isinstance(self.app.config, dict):
            self.app.config["response_window_zoom"] = self.current_text_display.zoom_factor
            self.app.save_config(self.app.config)

        self.chat_history = []
        if self.app.current_response_window is self:
            self.app.current_response_window = None

        super().closeEvent(event)
