import os

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QScrollArea

from writing_tools.ai_provider import AIProvider
from writing_tools.autostart import AutostartManager
from writing_tools.paths import get_resource_path
from writing_tools.ui.ui_utils import COLOR_MODE, UIUtils

_ = lambda x: x

CURRENT_CONFIG_VERSION = 9


class SettingsWindow(QtWidgets.QWidget):
    """
    The settings window for the application, with scrolling support.
    """

    close_signal = QtCore.Signal()

    def __init__(self, app, providers_only=False):
        super().__init__()
        self.app = app
        self.current_provider_layout = None
        self.providers_only = providers_only
        self.gradient_radio = None
        self.plain_radio = None
        self.provider_dropdown = None
        self.provider_container = None
        self.autostart_checkbox = None
        self.shortcut_input = None
        self.init_ui()
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(_("Settings"))

    def init_provider_ui(self, provider: AIProvider, layout):
        """
        Initialize the UI for the selected provider, safely deobfuscating secret settings
        before populating input fields.
        """
        if self.current_provider_layout:
            self.current_provider_layout.setParent(None)
            UIUtils.clear_layout(self.current_provider_layout)
            self.current_provider_layout.deleteLater()

        self.current_provider_layout = QtWidgets.QVBoxLayout()

        provider_header_layout = QtWidgets.QHBoxLayout()
        provider_header_layout.setSpacing(10)
        provider_header_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        if provider.logo:
            logo_path = get_resource_path("icons", f"provider_{provider.logo}.png")
            if os.path.exists(logo_path):
                target_pixmap = UIUtils.resize_and_round_image(QImage(logo_path), 30, 15)
                logo_label = QtWidgets.QLabel()
                logo_label.setPixmap(target_pixmap)
                logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
                provider_header_layout.addWidget(logo_label)

        provider_name_label = QtWidgets.QLabel(provider.provider_name)
        provider_name_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        provider_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        provider_header_layout.addWidget(provider_name_label)

        self.current_provider_layout.addLayout(provider_header_layout)

        if provider.description:
            description_label = QtWidgets.QLabel(provider.description)
            description_label.setStyleSheet(
                f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'}; text-align: center;"
            )
            description_label.setWordWrap(True)
            self.current_provider_layout.addWidget(description_label)

        if provider.button_text and provider.button_action:
            button = QtWidgets.QPushButton(provider.button_text)
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {'#4CAF50' if COLOR_MODE == 'dark' else '#008CBA'};
                    color: white;
                    padding: 10px;
                    font-size: 16px;
                    border: none;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: {'#45a049' if COLOR_MODE == 'dark' else '#007095'};
                }}
            """
            )
            button.clicked.connect(provider.button_action)
            self.current_provider_layout.addWidget(
                button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
            )

        providers_cfg = self.app.config.setdefault("providers", {})
        provider_cfg = providers_cfg.setdefault(provider.provider_name, {})

        for setting in provider.settings:
            stored_val = provider_cfg.get(setting.name, setting.default_value)
            display_val = provider.get_setting_display_value(setting, stored_val)
            setting.set_value(display_val)
            setting.render_to_layout(self.current_provider_layout)

        layout.addLayout(self.current_provider_layout)

    def init_ui(self):
        self.setWindowTitle(_("Settings"))
        self.setMinimumWidth(592)
        self.setFixedWidth(592)

        UIUtils.setup_window_and_layout(self)
        main_layout = QtWidgets.QVBoxLayout(self.background)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
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

        scroll_content = QtWidgets.QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        if not self.providers_only:
            title_label = QtWidgets.QLabel(_("Settings"))
            title_label.setStyleSheet(
                f"font-size: 24px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            content_layout.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

            if AutostartManager.get_startup_path():
                self.autostart_checkbox = QtWidgets.QCheckBox(_("Start on Boot"))
                self.autostart_checkbox.setStyleSheet(
                    f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
                )
                self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
                self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
                content_layout.addWidget(self.autostart_checkbox)

            shortcut_label = QtWidgets.QLabel(_("Shortcut Key:"))
            shortcut_label.setStyleSheet(
                f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            content_layout.addWidget(shortcut_label)

            self.shortcut_input = QtWidgets.QLineEdit(self.app.config.get("shortcut", "ctrl+space"))
            self.shortcut_input.setStyleSheet(
                f"""
                font-size: 16px;
                padding: 5px;
                background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
            """
            )
            content_layout.addWidget(self.shortcut_input)

            theme_label = QtWidgets.QLabel(_("Background Theme:"))
            theme_label.setStyleSheet(
                f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            content_layout.addWidget(theme_label)

            theme_layout = QHBoxLayout()
            self.gradient_radio = QRadioButton(_("Blurry Gradient"))
            self.plain_radio = QRadioButton(_("Plain"))
            self.gradient_radio.setStyleSheet(
                f"color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            self.plain_radio.setStyleSheet(
                f"color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            current_theme = self.app.config.get("theme", "gradient")
            self.gradient_radio.setChecked(current_theme == "gradient")
            self.plain_radio.setChecked(current_theme == "plain")
            theme_layout.addWidget(self.gradient_radio)
            theme_layout.addWidget(self.plain_radio)
            content_layout.addLayout(theme_layout)

        provider_label = QtWidgets.QLabel(_("Choose AI Provider:"))
        provider_label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        content_layout.addWidget(provider_label)

        self.provider_dropdown = QtWidgets.QComboBox()
        self.provider_dropdown.setStyleSheet(
            f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
            color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
            border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
        """
        )
        self.provider_dropdown.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        default_provider_name = self.app.providers[0].provider_name
        current_provider = self.app.config.get("provider", default_provider_name)
        for provider in self.app.providers:
            self.provider_dropdown.addItem(provider.provider_name)
        idx = self.provider_dropdown.findText(current_provider)
        self.provider_dropdown.setCurrentIndex(idx if idx != -1 else 0)
        content_layout.addWidget(self.provider_dropdown)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        content_layout.addWidget(line)

        self.provider_container = QtWidgets.QVBoxLayout()
        content_layout.addLayout(self.provider_container)

        provider_instance = self.app.providers[self.provider_dropdown.currentIndex()]
        self.init_provider_ui(provider_instance, self.provider_container)

        self.provider_dropdown.currentIndexChanged.connect(
            lambda: self.init_provider_ui(
                self.app.providers[self.provider_dropdown.currentIndex()],
                self.provider_container,
            )
        )

        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        content_layout.addWidget(line2)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        bottom_container = QtWidgets.QWidget()
        bottom_container.setStyleSheet("background: transparent;")
        bottom_layout = QtWidgets.QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(30, 0, 30, 30)
        bottom_layout.setSpacing(10)

        save_button = QtWidgets.QPushButton(
            _("Finish AI Setup") if self.providers_only else _("Save")
        )
        save_button.setStyleSheet(
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
        save_button.clicked.connect(self.save_settings)
        bottom_layout.addWidget(save_button)

        main_layout.addWidget(bottom_container)

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        max_height = int(screen.height() * 0.85)
        desired_height = min(720, max_height)
        self.resize(592, desired_height)

    @staticmethod
    def toggle_autostart(state):
        AutostartManager.set_autostart(state == QtCore.Qt.CheckState.Checked.value)

    def save_settings(self):
        """Save the current settings, preserving locale and stamping all migration flags."""
        if "locale" not in self.app.config:
            self.app.config["locale"] = "en"

        if not self.providers_only:
            shortcut = self.shortcut_input.text().strip() or "ctrl+space"
            self.app.config["shortcut"] = shortcut
            self.app.config["theme"] = "gradient" if self.gradient_radio.isChecked() else "plain"
        else:
            self.app.create_tray_icon()

        self.app.config["streaming"] = False
        self.app.config["provider"] = self.provider_dropdown.currentText()

        # Stamp all config migration flags up to current version
        for n in range(8, CURRENT_CONFIG_VERSION + 1):
            self.app.config[f"is_config_file_updated_for_v{n}"] = True

        selected_provider = self.app.providers[self.provider_dropdown.currentIndex()]
        selected_provider.save_config()

        if self.app.current_provider is not None and self.app.current_provider != selected_provider:
            self.app.current_provider.before_load()

        provider_name = self.app.config.get("provider", self.app.providers[0].provider_name)
        self.app.current_provider = next(
            (provider for provider in self.app.providers if provider.provider_name == provider_name),
            self.app.providers[0],
        )

        self.app.current_provider.load_config(
            self.app.config.get("providers", {}).get(provider_name, {})
        )

        self.app.register_hotkey()
        if self.providers_only:
            self.app.init_update_checker()
        self.providers_only = False
        self.close()

    def closeEvent(self, event):
        if self.providers_only:
            self.close_signal.emit()
        super().closeEvent(event)
