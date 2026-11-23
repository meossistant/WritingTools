import json
import logging
import os
from functools import partial

from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from writing_tools.paths import get_data_dir, get_resource_path
from writing_tools.ui.ui_utils import COLOR_MODE, ThemeBackground

_ = lambda x: x

################################################################################
# Default `options.json` content to restore when missing or user presses "Reset"
################################################################################
DEFAULT_OPTIONS_JSON = r"""{
  "Proofread": {
    "prefix": "Proofread this:\n\n",
    "instruction": "You are a grammar proofreading assistant.\nOutput ONLY the corrected text without any additional comments.\nMaintain the original text structure and writing style.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with this (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/magnifying_glass",
    "open_in_window": false
  },
  "Rewrite": {
    "prefix": "Rewrite this:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to improve phrasing.\nOutput ONLY the rewritten text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with proofreading (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/rewrite",
    "open_in_window": false
  },
  "Friendly": {
    "prefix": "Make this more friendly:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more friendly.\nOutput ONLY the friendly text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/smiley_face",
    "open_in_window": false
  },
  "Professional": {
    "prefix": "Make this more professional:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more professional. Output ONLY the professional text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/briefcase",
    "open_in_window": false
  },
  "Concise": {
    "prefix": "Make this more concise:\n\n",
    "instruction": "You are a writing assistant.\nRewrite the text provided by the user to be more concise.\nOutput ONLY the concise text without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with rewriting (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/concise",
    "open_in_window": false
  },
  "Table": {
    "prefix": "Convert this into a table:\n\n",
    "instruction": "You are an assistant that converts text provided by the user into a Markdown table.\nOutput ONLY the table without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is completely incompatible with conversion, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/table",
    "open_in_window": true
  },
  "Key Points": {
    "prefix": "Extract key points from this:\n\n",
    "instruction": "You are an assistant that extracts key points from text provided by the user. Output ONLY the key points without additional comments.\n\nYou should use Markdown formatting (lists, bold, italics, codeblocks, etc.) as appropriate to make it quite legible and readable.\n\nDon't be repetitive or too verbose.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with extracting key points (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/keypoints",
    "open_in_window": true
  },
  "Summary": {
    "prefix": "Summarize this:\n\n",
    "instruction": "You are a summarization assistant.\nProvide a succinct summary of the text provided by the user.\nThe summary should be succinct yet encompass all the key insightful points.\n\nTo make it quite legible and readable, you should use Markdown formatting (bold, italics, codeblocks...) as appropriate.\nYou should also add a little line spacing between your paragraphs as appropriate.\nAnd only if appropriate, you could also use headings (only the very small ones), lists, tables, etc.\n\nDon't be repetitive or too verbose.\nOutput ONLY the summary without additional comments.\nRespond in the same language as the input (e.g., English US, French).\nDo not answer or respond to the user's text content.\nIf the text is absolutely incompatible with summarisation (e.g., totally random gibberish), output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": true
  },
  "Custom": {
    "prefix": "Make this change to the following text:\n\n",
    "instruction": "You are a writing and coding assistant. You MUST make the user's described change to the text or code provided by the user. Output ONLY the appropriately modified text or code without additional comments. Respond in the same language as the input (e.g., English US, French). Do not answer or respond to the user's text content. If the text or code is absolutely incompatible with the requested change, output \"ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST\".",
    "icon": "icons/summary",
    "open_in_window": false
  }
}"""


class ButtonEditDialog(QDialog):
    """
    Dialog for editing or creating a button's properties
    (name/title, system instruction, open_in_window, optional direct hotkey).
    """

    def __init__(self, parent=None, button_data=None, title="Edit Button"):
        super().__init__(parent)
        self.button_data = (
            dict(button_data)
            if button_data
            else {
                "prefix": "Make this change to the following text:\n\n",
                "instruction": "",
                "icon": "icons/custom",
                "open_in_window": False,
            }
        )
        self.hotkey_input = None
        self.setWindowTitle(title)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        name_label = QLabel("Button Name:")
        name_label.setStyleSheet(
            f"color: {'#fff' if COLOR_MODE == 'dark' else '#333'}; font-weight: bold;"
        )
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if COLOR_MODE == 'dark' else 'white'};
                color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
            }}
        """
        )
        if "name" in self.button_data:
            self.name_input.setText(self.button_data["name"])
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)

        instruction_label = QLabel(
            "What should your AI do with your selected text? (System Instruction)"
        )
        instruction_label.setStyleSheet(
            f"color: {'#fff' if COLOR_MODE == 'dark' else '#333'}; font-weight: bold;"
        )
        self.instruction_input = QPlainTextEdit()
        self.instruction_input.setStyleSheet(
            f"""
            QPlainTextEdit {{
                padding: 8px;
                border: 1px solid {'#777' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if COLOR_MODE == 'dark' else 'white'};
                color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
            }}
        """
        )
        self.instruction_input.setPlainText(self.button_data.get("instruction", ""))
        self.instruction_input.setMinimumHeight(100)
        self.instruction_input.setPlaceholderText(
            """Examples:
    - Fix / improve / explain this code.
    - Make it funny.
    - Translate to English.
    - Make the text title case.
    - Write a reply to this.
    - Analyse potential biases in this article."""
        )
        layout.addWidget(instruction_label)
        layout.addWidget(self.instruction_input)

        display_label = QLabel("How should your AI response be shown?")
        display_label.setStyleSheet(
            f"color: {'#fff' if COLOR_MODE == 'dark' else '#333'}; font-weight: bold;"
        )
        layout.addWidget(display_label)

        radio_layout = QHBoxLayout()
        self.replace_radio = QRadioButton("Replace the selected text")
        self.window_radio = QRadioButton("In a pop-up window (with follow-up support)")
        for r in (self.replace_radio, self.window_radio):
            r.setStyleSheet(f"color: {'#fff' if COLOR_MODE == 'dark' else '#333'};")

        self.replace_radio.setChecked(not self.button_data.get("open_in_window", False))
        self.window_radio.setChecked(bool(self.button_data.get("open_in_window", False)))

        radio_layout.addWidget(self.replace_radio)
        radio_layout.addWidget(self.window_radio)
        layout.addLayout(radio_layout)

        hotkey_label = QLabel("Direct hotkey (optional):")
        hotkey_label.setStyleSheet(
            f"color: {'#fff' if COLOR_MODE == 'dark' else '#333'}; font-weight: bold;"
        )
        layout.addWidget(hotkey_label)

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if COLOR_MODE == 'dark' else 'white'};
                color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
            }}
        """
        )
        self.hotkey_input.setPlaceholderText("e.g. ctrl+j  (leave blank for none)")
        self.hotkey_input.setText(self.button_data.get("hotkey", ""))
        layout.addWidget(self.hotkey_input)

        hotkey_hint = QLabel(
            "Press this combination from anywhere to run this button directly, skipping the popup.\n"
            "Use '+' between keys, e.g. ctrl+j or ctrl+shift+p."
        )
        hotkey_hint.setStyleSheet(
            f"color: {'#bbb' if COLOR_MODE == 'dark' else '#555'}; font-size: 12px;"
        )
        hotkey_hint.setWordWrap(True)
        layout.addWidget(hotkey_hint)

        btn_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        for btn in (ok_button, cancel_button):
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {'#444' if COLOR_MODE == 'dark' else '#f0f0f0'};
                    color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
                    border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
                    border-radius: 5px;
                    padding: 8px;
                    min-width: 100px;
                }}
                QPushButton:hover {{
                    background-color: {'#555' if COLOR_MODE == 'dark' else '#e0e0e0'};
                }}
            """
            )
        btn_layout.addWidget(ok_button)
        btn_layout.addWidget(cancel_button)
        layout.addLayout(btn_layout)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {'#222' if COLOR_MODE == 'dark' else '#f5f5f5'};
                border-radius: 10px;
            }}
        """
        )

    def get_button_data(self):
        # Preserve existing prefix and icon when editing built-in or customized buttons
        data = {
            "name": self.name_input.text().strip(),
            "prefix": self.button_data.get(
                "prefix", "Make this change to the following text:\n\n"
            ),
            "instruction": self.instruction_input.toPlainText(),
            "icon": self.button_data.get("icon", "icons/custom"),
            "open_in_window": self.window_radio.isChecked(),
        }
        hotkey = self.hotkey_input.text().strip().lower() if self.hotkey_input else ""
        if hotkey:
            data["hotkey"] = hotkey
        return data


class DraggableButton(QtWidgets.QPushButton):
    def __init__(self, parent_popup, key, text):
        super().__init__(text, parent_popup)
        self.popup = parent_popup
        self.key = key
        self.drag_start_position = None
        self.setAcceptDrops(True)
        self.icon_container = None

        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("hover", False)
        self.setFixedSize(120, 40)

        self.base_style = f"""
            QPushButton {{
                background-color: {"#444" if COLOR_MODE == "dark" else "white"};
                border: 1px solid {"#666" if COLOR_MODE == "dark" else "#ccc"};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
                color: {"#fff" if COLOR_MODE == "dark" else "#000"};
            }}
            QPushButton[hover="true"] {{
                background-color: {"#555" if COLOR_MODE == "dark" else "#f0f0f0"};
            }}
        """
        self.setStyleSheet(self.base_style)

    def enterEvent(self, event):
        if not self.popup.edit_mode:
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.popup.edit_mode:
            self.setProperty("hover", False)
            self.style().unpolish(self)
            self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.popup.edit_mode:
                self.drag_start_position = event.pos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton) or not self.drag_start_position:
            return

        distance = (event.pos() - self.drag_start_position).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            return

        if self.popup.edit_mode:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            idx = self.popup.button_widgets.index(self)
            mime_data.setData("application/x-button-index", str(idx).encode())
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            self.drag_start_position = None
            drop_action = drag.exec(QtCore.Qt.DropAction.MoveAction)
            logging.debug(f"Drag completed with action: {drop_action}")

    def dragEnterEvent(self, event):
        if self.popup.edit_mode and event.mimeData().hasFormat("application/x-button-index"):
            event.acceptProposedAction()
            self.setStyleSheet(
                self.base_style
                + """
                QPushButton {
                    border: 2px dashed #666;
                }
            """
            )
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.base_style)
        event.accept()

    def dropEvent(self, event):
        if not self.popup.edit_mode or not event.mimeData().hasFormat("application/x-button-index"):
            event.ignore()
            return

        source_idx = int(event.mimeData().data("application/x-button-index").data().decode())
        target_idx = self.popup.button_widgets.index(self)

        if source_idx != target_idx:
            bw = self.popup.button_widgets
            bw[source_idx], bw[target_idx] = bw[target_idx], bw[source_idx]
            self.popup.rebuild_grid_layout()
            self.popup.update_json_from_grid()

        self.setStyleSheet(self.base_style)
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.acceptProposedAction()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.icon_container:
            self.icon_container.setGeometry(0, 0, self.width(), self.height())


class CustomPopupWindow(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.edit_mode = False

        self.drag_label = None
        self.edit_button = None
        self.reset_button = None
        self.close_button = None
        self.custom_input = None
        self.input_area = None

        self.button_widgets = []

        logging.debug("Initializing CustomPopupWindow")
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Writing Tools")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background = ThemeBackground(
            self,
            self.app.config.get("theme", "gradient") if self.app.config else "gradient",
            is_popup=True,
            border_radius=10,
        )
        main_layout.addWidget(self.background)

        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(10, 4, 10, 10)
        content_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        self.edit_button = QPushButton()
        pencil_icon = get_resource_path(
            "icons", "pencil" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(pencil_icon):
            self.edit_button.setIcon(QtGui.QIcon(pencil_icon))
        self.edit_button.setFixedSize(24, 24)
        self.edit_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 0px;
                margin-top: 3px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if COLOR_MODE == 'dark' else '#ebebeb'};
            }}
        """
        )
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        top_bar.addWidget(self.edit_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.drag_label = QLabel("Drag to rearrange")
        self.drag_label.setStyleSheet(
            f"""
            color: {'#fff' if COLOR_MODE == 'dark' else '#333'};
            font-size: 14px;
            font-weight: bold;
        """
        )
        self.drag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_label.hide()
        top_bar.addWidget(
            self.drag_label, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )

        self.reset_button = QPushButton()
        reset_icon_path = get_resource_path(
            "icons", "restore" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(reset_icon_path):
            self.reset_button.setIcon(QtGui.QIcon(reset_icon_path))
        self.reset_button.setText("")
        self.reset_button.setFixedSize(24, 24)
        self.reset_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if COLOR_MODE == 'dark' else '#ebebeb'};
            }}
        """
        )
        self.reset_button.clicked.connect(self.on_reset_clicked)
        self.reset_button.hide()
        top_bar.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignRight)

        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {'#fff' if COLOR_MODE == 'dark' else '#333'};
                font-size: 20px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if COLOR_MODE == 'dark' else '#ebebeb'};
            }}
        """
        )
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addLayout(top_bar)

        self.input_area = QWidget()
        input_layout = QHBoxLayout(self.input_area)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText(_("Describe your change..."))
        self.custom_input.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if COLOR_MODE == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if COLOR_MODE == 'dark' else 'white'};
                color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
            }}
        """
        )
        self.custom_input.returnPressed.connect(self.on_custom_change)
        input_layout.addWidget(self.custom_input)

        send_btn = QPushButton()
        send_icon = get_resource_path(
            "icons", "send" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(send_icon):
            send_btn.setIcon(QtGui.QIcon(send_icon))
        send_btn.setStyleSheet(
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
        send_btn.setFixedSize(
            self.custom_input.sizeHint().height(),
            self.custom_input.sizeHint().height(),
        )
        send_btn.clicked.connect(self.on_custom_change)
        input_layout.addWidget(send_btn)

        content_layout.addWidget(self.input_area)

        self.build_buttons_list()
        self.rebuild_grid_layout(content_layout)

        if self.app.config and self.app.config.get("update_available", False):
            update_label = QLabel()
            update_label.setOpenExternalLinks(True)
            update_label.setText(
                '<a href="https://github.com/theJayTea/WritingTools/releases" '
                'style="color:rgb(255, 0, 0); text-decoration: underline; font-weight: bold;">'
                "There's an update available. Download now.</a>"
            )
            update_label.setStyleSheet("margin-top: 10px;")
            content_layout.addWidget(update_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.installEventFilter(self)
        QtCore.QTimer.singleShot(250, lambda: self.custom_input.setFocus())

    @staticmethod
    def load_options():
        options_path = os.path.join(get_data_dir(), "options.json")
        if os.path.exists(options_path):
            try:
                with open(options_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"Failed to read options.json ({e}); restoring defaults.")

        data = json.loads(DEFAULT_OPTIONS_JSON)
        try:
            CustomPopupWindow.save_options(data)
        except OSError as e:
            logging.warning(f"Could not save default options.json: {e}")
        return data

    @staticmethod
    def save_options(options):
        options_path = os.path.join(get_data_dir(), "options.json")
        with open(options_path, "w", encoding="utf-8") as f:
            json.dump(options, f, indent=2, ensure_ascii=False)

    def _reload_app_options(self):
        """Apply button & hotkey changes live without forcing the app to quit."""
        self.app.load_options()
        self.app.register_hotkey()

    def build_buttons_list(self):
        for btn in self.button_widgets:
            btn.deleteLater()
        self.button_widgets.clear()
        data = self.load_options()

        for k, v in data.items():
            if k == "Custom" or not isinstance(v, dict):
                continue
            b = DraggableButton(self, k, k)
            icon_rel = v.get("icon", "icons/custom").replace("-", "_")
            icon_path = get_resource_path(
                icon_rel + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
            )
            if os.path.exists(icon_path):
                b.setIcon(QtGui.QIcon(icon_path))

            hotkey = (v.get("hotkey") or "").strip()
            if hotkey:
                b.setToolTip(f"Direct hotkey: {hotkey}")

            if not self.edit_mode:
                b.clicked.connect(partial(self.on_generic_instruction, k))
            else:
                self.add_edit_delete_icons(b)
            self.button_widgets.append(b)

    def rebuild_grid_layout(self, parent_layout=None):
        if not parent_layout:
            parent_layout = self.background.layout()

        for i in reversed(range(parent_layout.count())):
            item = parent_layout.itemAt(i)
            if isinstance(item, QtWidgets.QGridLayout):
                grid = item
                for j in reversed(range(grid.count())):
                    w = grid.itemAt(j).widget()
                    if w:
                        grid.removeWidget(w)
                parent_layout.removeItem(grid)
            elif (
                item.widget()
                and isinstance(item.widget(), QPushButton)
                and item.widget().text() == "+ Add New"
            ):
                item.widget().deleteLater()

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 120)

        row = 0
        col = 0
        for b in self.button_widgets:
            grid.addWidget(b, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

        parent_layout.addLayout(grid)

        if self.edit_mode:
            add_btn = QPushButton("+ Add New")
            add_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {'#333' if COLOR_MODE == 'dark' else '#e0e0e0'};
                    border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 14px;
                    text-align: center;
                    color: {'#fff' if COLOR_MODE == 'dark' else '#000'};
                    margin-top: 10px;
                }}
                QPushButton:hover {{
                    background-color: {'#444' if COLOR_MODE == 'dark' else '#d0d0d0'};
                }}
            """
            )
            add_btn.clicked.connect(self.add_new_button_clicked)
            parent_layout.addWidget(add_btn)

    def add_edit_delete_icons(self, btn):
        if hasattr(btn, "icon_container") and btn.icon_container:
            btn.icon_container.deleteLater()

        btn.icon_container = QtWidgets.QWidget(btn)
        btn.icon_container.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
        )
        btn.icon_container.setGeometry(0, 0, btn.width(), btn.height())

        circle_style = f"""
            QPushButton {{
                background-color: {'#666' if COLOR_MODE == 'dark' else '#999'};
                border-radius: 10px;
                min-width: 16px;
                min-height: 16px;
                max-width: 16px;
                max-height: 16px;
                padding: 1px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#888' if COLOR_MODE == 'dark' else '#bbb'};
            }}
        """

        edit_btn = QPushButton(btn.icon_container)
        edit_btn.setGeometry(3, 3, 16, 16)
        pencil_icon = get_resource_path(
            "icons", "pencil" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(pencil_icon):
            edit_btn.setIcon(QtGui.QIcon(pencil_icon))
        edit_btn.setStyleSheet(circle_style)
        edit_btn.clicked.connect(partial(self.edit_button_clicked, btn))
        edit_btn.show()

        delete_btn = QPushButton(btn.icon_container)
        delete_btn.setGeometry(btn.width() - 23, 3, 16, 16)
        del_icon = get_resource_path(
            "icons", "cross" + ("_dark" if COLOR_MODE == "dark" else "_light") + ".png"
        )
        if os.path.exists(del_icon):
            delete_btn.setIcon(QtGui.QIcon(del_icon))
        delete_btn.setStyleSheet(circle_style)
        delete_btn.clicked.connect(partial(self.delete_button_clicked, btn))
        delete_btn.show()

        btn.icon_container.raise_()
        btn.icon_container.show()

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        logging.debug(f"Edit mode toggled: {self.edit_mode}")

        if self.edit_mode:
            icon_name = "check"
            self.edit_button.setText("")
            self.edit_button.setFixedSize(36, 36)
            self.edit_button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background-color: {'#333' if COLOR_MODE == 'dark' else '#ebebeb'};
                }}
            """
            )
            self.close_button.hide()
            self.reset_button.show()
            self.drag_label.show()
        else:
            icon_name = "pencil"
            self.edit_button.setText("")
            self.edit_button.setFixedSize(24, 24)
            self.close_button.show()
            self.reset_button.hide()
            self.drag_label.hide()
            self._reload_app_options()

        icon_path = get_resource_path(
            "icons", f"{icon_name}_{'dark' if COLOR_MODE == 'dark' else 'light'}.png"
        )
        if os.path.exists(icon_path):
            self.edit_button.setIcon(QtGui.QIcon(icon_path))

        self.input_area.setVisible(not self.edit_mode)

        for btn in self.button_widgets:
            try:
                btn.clicked.disconnect()
            except RuntimeError:
                pass

            if not self.edit_mode:
                btn.clicked.connect(partial(self.on_generic_instruction, btn.key))
                if hasattr(btn, "icon_container") and btn.icon_container:
                    btn.icon_container.deleteLater()
                    btn.icon_container = None
            else:
                self.add_edit_delete_icons(btn)

            btn.setStyleSheet(btn.base_style)

        self.rebuild_grid_layout()
        self.adjustSize()

    def on_reset_clicked(self):
        confirm_box = QtWidgets.QMessageBox(self)
        confirm_box.setWindowTitle("Confirm Reset to Defaults")
        confirm_box.setText("Reset all buttons to their original default configuration?")
        confirm_box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        confirm_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)

        if confirm_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                default_data = json.loads(DEFAULT_OPTIONS_JSON)
                self.save_options(default_data)
                self._reload_app_options()
                self.build_buttons_list()
                self.rebuild_grid_layout()
                self.adjustSize()
            except Exception as e:
                logging.error(f"Error resetting options.json: {e}")
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"An error occurred while resetting: {e}"
                )

    def _validate_button_name(self, name, exclude_button=None):
        if not name:
            return False, "Button name cannot be empty."
        if name == "Custom":
            return False, "'Custom' is a reserved button name. Please choose another name."
        data = self.load_options()
        if name != exclude_button and name in data:
            return False, f"A button named '{name}' already exists."
        return True, None

    def _validate_hotkey(self, hotkey, exclude_button=None):
        if not hotkey:
            return True, None

        try:
            pykeyboard.HotKey.parse(self.app._to_pynput_hotkey(hotkey))
        except Exception as e:
            return False, (
                f"'{hotkey}' isn't a valid hotkey.\n\n"
                f"Use '+' between keys, e.g. ctrl+j or ctrl+shift+p.\n({e})"
            )

        global_shortcut = (
            (self.app.config.get("shortcut") if self.app.config else None) or "ctrl+space"
        ).strip().lower()
        if hotkey == global_shortcut:
            return False, (
                f"'{hotkey}' is already used as the main Writing Tools "
                "hotkey (set in Settings). Pick a different combination."
            )

        data = self.load_options()
        for k, v in data.items():
            if k == exclude_button or not isinstance(v, dict):
                continue
            other = (v.get("hotkey") or "").strip().lower()
            if other and other == hotkey:
                return False, (
                    f"'{hotkey}' is already used by the '{k}' button. "
                    "Pick a different combination."
                )

        return True, None

    @staticmethod
    def _build_button_entry(bd, existing=None):
        entry = dict(existing) if existing else {}
        entry["prefix"] = bd["prefix"]
        entry["instruction"] = bd["instruction"]
        entry["icon"] = bd["icon"]
        entry["open_in_window"] = bd["open_in_window"]
        if bd.get("hotkey"):
            entry["hotkey"] = bd["hotkey"]
        else:
            entry.pop("hotkey", None)
        return entry

    def add_new_button_clicked(self):
        dialog = ButtonEditDialog(self, title="Add New Button")
        while dialog.exec():
            bd = dialog.get_button_data()
            ok_name, err_name = self._validate_button_name(bd["name"])
            if not ok_name:
                QtWidgets.QMessageBox.warning(self, "Invalid Button Name", err_name)
                continue
            ok_hk, err_hk = self._validate_hotkey(bd.get("hotkey", ""))
            if not ok_hk:
                QtWidgets.QMessageBox.warning(self, "Invalid Hotkey", err_hk)
                continue

            data = self.load_options()
            data[bd["name"]] = self._build_button_entry(bd)
            self.save_options(data)
            self._reload_app_options()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            self.adjustSize()
            return

    def edit_button_clicked(self, btn):
        key = btn.key
        data = self.load_options()
        bd = dict(data[key])
        bd["name"] = key

        dialog = ButtonEditDialog(self, bd)
        while dialog.exec():
            new_data = dialog.get_button_data()
            ok_name, err_name = self._validate_button_name(
                new_data["name"], exclude_button=key
            )
            if not ok_name:
                QtWidgets.QMessageBox.warning(self, "Invalid Button Name", err_name)
                continue
            ok_hk, err_hk = self._validate_hotkey(
                new_data.get("hotkey", ""), exclude_button=key
            )
            if not ok_hk:
                QtWidgets.QMessageBox.warning(self, "Invalid Hotkey", err_hk)
                continue

            data = self.load_options()
            existing = data.get(key)
            if new_data["name"] != key:
                # Preserve button ordering on rename
                reordered = {}
                for k, v in data.items():
                    if k == key:
                        reordered[new_data["name"]] = self._build_button_entry(
                            new_data, existing=existing
                        )
                    else:
                        reordered[k] = v
                data = reordered
            else:
                data[key] = self._build_button_entry(new_data, existing=existing)

            self.save_options(data)
            self._reload_app_options()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            self.adjustSize()
            return

    def delete_button_clicked(self, btn):
        key = btn.key
        confirm = QtWidgets.QMessageBox(self)
        confirm.setWindowTitle("Confirm Delete")
        confirm.setText(f"Are you sure you want to delete the '{key}' button?")
        confirm.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)

        if confirm.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                data = self.load_options()
                data.pop(key, None)
                self.save_options(data)
                self._reload_app_options()
                self.build_buttons_list()
                self.rebuild_grid_layout()
                self.adjustSize()
            except Exception as e:
                logging.error(f"Error deleting button: {e}")
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"An error occurred while deleting the button: {e}"
                )

    def update_json_from_grid(self):
        data = self.load_options()
        new_data = {}
        for b in self.button_widgets:
            if b.key in data:
                new_data[b.key] = data[b.key]
        if "Custom" in data:
            new_data["Custom"] = data["Custom"]
        self.save_options(new_data)
        self._reload_app_options()

    def on_custom_change(self):
        txt = self.custom_input.text().strip()
        if txt:
            self.app.process_option("Custom", txt)
            self.close()

    def on_generic_instruction(self, instruction):
        if not self.edit_mode:
            self.app.process_option(instruction)
            self.close()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.WindowDeactivate:
            if not self.edit_mode:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
