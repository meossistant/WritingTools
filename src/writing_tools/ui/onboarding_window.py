import logging

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QHBoxLayout, QRadioButton

from writing_tools.autostart import AutostartManager
from writing_tools.ui.ui_utils import COLOR_MODE, UIUtils

_ = lambda x: x


class OnboardingWindow(QtWidgets.QWidget):
    close_signal = QtCore.Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.shortcut = "ctrl+space"
        self.theme = "gradient"
        self.content_layout = None
        self.shortcut_input = None
        self.autostart_checkbox = None
        self.self_close = False
        self.init_ui()

    def init_ui(self):
        logging.debug("Initializing onboarding UI")
        self.setWindowTitle(_("Welcome to Writing Tools"))
        self.resize(600, 560)

        UIUtils.setup_window_and_layout(self)

        self.content_layout = QtWidgets.QVBoxLayout()
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(20)

        self.background.setLayout(self.content_layout)
        self.show_welcome_screen()

    def show_welcome_screen(self):
        UIUtils.clear_layout(self.content_layout)

        title_label = QtWidgets.QLabel(_("Welcome to Writing Tools") + "!")
        title_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        self.content_layout.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        features_text = f"""
        • {_('Instantly optimize your writing with AI by selecting your text and invoking Writing Tools with "ctrl+space", anywhere.')}

        • {_('Get a summary you can chat with of articles, YouTube videos, or documents by selecting all text with "ctrl+a"')}
          {_('(or selecting a transcript), invoking Writing Tools, and choosing Summary.')}

        • {_('Customize buttons and assign direct per-button hotkeys right from the popup.')}

        • {_('Supports an extensive range of AI models:')}
            - {_('Google Gemini (Gemini Flash Latest, Gemini 3.8 Flash, Gemini 4) & Gemma 4')}
            - {_('ANY OpenAI-Compatible API (GPT-6, GPT-5.4, OpenRouter, vLLM, etc.)')}
            - {_('Local LLMs via llama.cpp (Gemma 4 E2B IT, etc.)')}
            - {_('Non-AI offline proofreading via external LanguageTool server')}
        """
        features_label = QtWidgets.QLabel(features_text)
        features_label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        features_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        features_label.setWordWrap(True)
        self.content_layout.addWidget(features_label)

        shortcut_label = QtWidgets.QLabel(
            _('Customize your shortcut key (default: "ctrl+space"; double-tap like "ctrl+ctrl" supported):')
        )
        shortcut_label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        shortcut_label.setWordWrap(True)
        self.content_layout.addWidget(shortcut_label)

        self.shortcut_input = QtWidgets.QLineEdit(self.shortcut)
        self.shortcut_input.setPlaceholderText("e.g. ctrl+space, ctrl+ctrl, alt+alt")
        self.shortcut_input.setStyleSheet(
            f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
            color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
            border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
        """
        )
        self.content_layout.addWidget(self.shortcut_input)

        if AutostartManager.get_startup_path():
            self.autostart_checkbox = QtWidgets.QCheckBox(_("Start on Boot"))
            self.autostart_checkbox.setStyleSheet(
                f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
            self.content_layout.addWidget(self.autostart_checkbox)

        theme_label = QtWidgets.QLabel(_("Choose your theme:"))
        theme_label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        self.content_layout.addWidget(theme_label)

        theme_layout = QHBoxLayout()
        gradient_radio = QRadioButton(_("Gradient"))
        plain_radio = QRadioButton(_("Plain"))
        gradient_radio.setStyleSheet(f"color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};")
        plain_radio.setStyleSheet(f"color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};")
        gradient_radio.setChecked(self.theme == "gradient")
        plain_radio.setChecked(self.theme == "plain")
        theme_layout.addWidget(gradient_radio)
        theme_layout.addWidget(plain_radio)
        self.content_layout.addLayout(theme_layout)

        next_button = QtWidgets.QPushButton(_("Next"))
        next_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                font-size: 16px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        next_button.clicked.connect(lambda: self.on_next_clicked(gradient_radio.isChecked()))
        self.content_layout.addWidget(next_button)

    def on_next_clicked(self, is_gradient):
        self.shortcut = self.shortcut_input.text().strip() or "ctrl+space"
        self.theme = "gradient" if is_gradient else "plain"
        if self.autostart_checkbox is not None:
            AutostartManager.set_autostart(self.autostart_checkbox.isChecked())
        logging.debug(f"User selected shortcut: {self.shortcut}, theme: {self.theme}")
        self.app.config = {
            "shortcut": self.shortcut,
            "theme": self.theme,
        }
        self.show_api_key_input()

    def show_api_key_input(self):
        self.app.show_settings(providers_only=True)
        self.self_close = True
        self.close()

    def closeEvent(self, event):
        if not self.self_close:
            self.close_signal.emit()
        super().closeEvent(event)
