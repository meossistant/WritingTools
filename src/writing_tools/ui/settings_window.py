import os

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QScrollArea

from writing_tools.ai_provider import AIProvider
from writing_tools.autostart import AutostartManager
from writing_tools.hotkey_listener import validate_hotkey
from writing_tools.paths import get_resource_path
from writing_tools.ui.ui_utils import COLOR_MODE, UIUtils

_ = lambda x: x

CURRENT_CONFIG_VERSION = 9

_OUTPUT_LANGUAGE_OPTIONS = [
    ("Auto (Match Input Language)", "auto"),
    ("English", "English"),
    ("Vietnamese", "Vietnamese"),
    ("German", "German"),
    ("Spanish", "Spanish"),
    ("French", "French"),
    ("Italian", "Italian"),
    ("Japanese", "Japanese"),
    ("Chinese", "Chinese"),
    ("Korean", "Korean"),
]
_CUSTOM_LANG_SENTINEL = "__custom__"
_LOCALE_DISPLAY_NAMES = {
    "en": "English (en)",
    "it": "Italiano (it)",
    "vi": "Tiếng Việt (vi)",
    "de": "Deutsch (de)",
    "es": "Español (es)",
    "fr": "Français (fr)",
    "nl": "Nederlands (nl)",
    "he": "עברית (he)",
}


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
        self.ui_locale_dropdown = None
        self.output_lang_dropdown = None
        self.custom_output_lang_input = None
        self.global_rule_input = None
        self.check_focus_checkbox = None
        self.loading_indicator_checkbox = None
        self.auto_pause_fullscreen_checkbox = None
        self.terminal_shortcuts_checkbox = None
        self.app_blacklist_input = None
        self.app_shortcut_rules_input = None
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

            shortcut_label = QtWidgets.QLabel(
                _("Shortcut Key (supports combos like ctrl+space or double-tap like ctrl+ctrl):")
            )
            shortcut_label.setStyleSheet(
                f"font-size: 15px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            shortcut_label.setWordWrap(True)
            content_layout.addWidget(shortcut_label)

            input_style = f"""
                font-size: 15px;
                padding: 5px;
                background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
            """
            label_style = (
                f"font-size: 15px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )

            self.shortcut_input = QtWidgets.QLineEdit(self.app.config.get("shortcut", "ctrl+space"))
            self.shortcut_input.setPlaceholderText("e.g. ctrl+space, ctrl+ctrl, alt+alt, shift+shift")
            self.shortcut_input.setStyleSheet(input_style)
            content_layout.addWidget(self.shortcut_input)

            theme_label = QtWidgets.QLabel(_("Background Theme:"))
            theme_label.setStyleSheet(label_style)
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

            # UI Language selector (#48)
            ui_lang_row = QHBoxLayout()
            ui_lang_label = QtWidgets.QLabel(_("Interface Language:"))
            ui_lang_label.setStyleSheet(label_style)
            self.ui_locale_dropdown = QtWidgets.QComboBox()
            self.ui_locale_dropdown.setStyleSheet(input_style)
            locales_dir = get_resource_path("locales")
            available_locales = []
            if os.path.isdir(locales_dir):
                for entry in sorted(os.listdir(locales_dir)):
                    if os.path.isdir(os.path.join(locales_dir, entry)):
                        available_locales.append(entry)
            if "en" not in available_locales:
                available_locales.insert(0, "en")
            current_locale = self.app.config.get("locale", "en")
            if current_locale and current_locale not in available_locales:
                available_locales.append(current_locale)
            for code in available_locales:
                self.ui_locale_dropdown.addItem(_LOCALE_DISPLAY_NAMES.get(code, code), code)
            loc_idx = self.ui_locale_dropdown.findData(current_locale)
            self.ui_locale_dropdown.setCurrentIndex(loc_idx if loc_idx != -1 else 0)
            ui_lang_row.addWidget(ui_lang_label)
            ui_lang_row.addWidget(self.ui_locale_dropdown, 1)
            content_layout.addLayout(ui_lang_row)

            # Preferred Output Language (#48)
            out_lang_row = QHBoxLayout()
            out_lang_label = QtWidgets.QLabel(_("Preferred Output Language:"))
            out_lang_label.setStyleSheet(label_style)
            self.output_lang_dropdown = QtWidgets.QComboBox()
            self.output_lang_dropdown.setStyleSheet(input_style)
            for disp, val in _OUTPUT_LANGUAGE_OPTIONS:
                self.output_lang_dropdown.addItem(disp, val)
            self.output_lang_dropdown.addItem(_("Custom..."), _CUSTOM_LANG_SENTINEL)

            saved_out_lang = (self.app.config.get("output_language") or "auto").strip()
            out_idx = self.output_lang_dropdown.findData(saved_out_lang)
            if out_idx != -1:
                self.output_lang_dropdown.setCurrentIndex(out_idx)
            else:
                self.output_lang_dropdown.setCurrentIndex(
                    self.output_lang_dropdown.findData(_CUSTOM_LANG_SENTINEL)
                )
            out_lang_row.addWidget(out_lang_label)
            out_lang_row.addWidget(self.output_lang_dropdown, 1)
            content_layout.addLayout(out_lang_row)

            self.custom_output_lang_input = QtWidgets.QLineEdit()
            self.custom_output_lang_input.setPlaceholderText(
                _("Enter custom output language (e.g. Portuguese, Polish)")
            )
            self.custom_output_lang_input.setStyleSheet(input_style)
            if out_idx == -1 and saved_out_lang and saved_out_lang != "auto":
                self.custom_output_lang_input.setText(saved_out_lang)
            self.custom_output_lang_input.setVisible(
                self.output_lang_dropdown.currentData() == _CUSTOM_LANG_SENTINEL
            )
            self.output_lang_dropdown.currentIndexChanged.connect(
                lambda: self.custom_output_lang_input.setVisible(
                    self.output_lang_dropdown.currentData() == _CUSTOM_LANG_SENTINEL
                )
            )
            content_layout.addWidget(self.custom_output_lang_input)

            # Global custom rule (#149)
            rule_label = QtWidgets.QLabel(_("Global Custom Rule (appended to all AI prompts):"))
            rule_label.setStyleSheet(label_style)
            content_layout.addWidget(rule_label)

            self.global_rule_input = QtWidgets.QLineEdit(self.app.config.get("global_rule", ""))
            self.global_rule_input.setPlaceholderText(
                _('e.g. "Use British English" or "Keep responses concise and formal"')
            )
            self.global_rule_input.setStyleSheet(input_style)
            content_layout.addWidget(self.global_rule_input)

            # Safety & Behavior section (#23, #139, #113, #99)
            safety_sep = QtWidgets.QFrame()
            safety_sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            safety_sep.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
            content_layout.addWidget(safety_sep)

            safety_title = QtWidgets.QLabel(_("Safety, Window Focus & Shortcuts:"))
            safety_title.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
            )
            content_layout.addWidget(safety_title)

            self.check_focus_checkbox = QtWidgets.QCheckBox(
                _("Check active window focus before pasting (open window if switched)")
            )
            self.check_focus_checkbox.setStyleSheet(label_style)
            self.check_focus_checkbox.setChecked(
                bool(self.app.config.get("check_focus_before_paste", True))
            )
            content_layout.addWidget(self.check_focus_checkbox)

            self.loading_indicator_checkbox = QtWidgets.QCheckBox(
                _("Show floating loading indicator during inline replacements")
            )
            self.loading_indicator_checkbox.setStyleSheet(label_style)
            self.loading_indicator_checkbox.setChecked(
                bool(self.app.config.get("show_loading_indicator", True))
            )
            content_layout.addWidget(self.loading_indicator_checkbox)

            self.auto_pause_fullscreen_checkbox = QtWidgets.QCheckBox(
                _("Auto-pause hotkeys in fullscreen apps (e.g. games)")
            )
            self.auto_pause_fullscreen_checkbox.setStyleSheet(label_style)
            self.auto_pause_fullscreen_checkbox.setChecked(
                bool(self.app.config.get("auto_pause_fullscreen", False))
            )
            content_layout.addWidget(self.auto_pause_fullscreen_checkbox)

            self.terminal_shortcuts_checkbox = QtWidgets.QCheckBox(
                _("Automatically use Ctrl+Shift+C / V in terminal emulators")
            )
            self.terminal_shortcuts_checkbox.setStyleSheet(label_style)
            self.terminal_shortcuts_checkbox.setChecked(
                bool(self.app.config.get("enable_terminal_shortcuts", True))
            )
            content_layout.addWidget(self.terminal_shortcuts_checkbox)

            bl_label = QtWidgets.QLabel(_("Application Blacklist (comma-separated process/title patterns):"))
            bl_label.setStyleSheet(label_style)
            content_layout.addWidget(bl_label)

            self.app_blacklist_input = QtWidgets.QLineEdit(self.app.config.get("app_blacklist", ""))
            self.app_blacklist_input.setPlaceholderText("e.g. cs2, valorant, dota2")
            self.app_blacklist_input.setStyleSheet(input_style)
            content_layout.addWidget(self.app_blacklist_input)

            rules_label = QtWidgets.QLabel(
                _("Custom Per-App Copy/Paste Rules (one per line: app=copy,paste):")
            )
            rules_label.setStyleSheet(label_style)
            content_layout.addWidget(rules_label)

            self.app_shortcut_rules_input = QtWidgets.QPlainTextEdit()
            self.app_shortcut_rules_input.setMaximumHeight(68)
            self.app_shortcut_rules_input.setPlaceholderText("emacs=alt+w,ctrl+y\nkitty=ctrl+shift+c,ctrl+shift+v")
            self.app_shortcut_rules_input.setPlainText(
                self.app.config.get("app_shortcut_rules", "")
            )
            self.app_shortcut_rules_input.setStyleSheet(input_style)
            content_layout.addWidget(self.app_shortcut_rules_input)

            provider_sep = QtWidgets.QFrame()
            provider_sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            provider_sep.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
            content_layout.addWidget(provider_sep)

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
            ok_hk, err_hk = validate_hotkey(shortcut)
            if not ok_hk:
                QtWidgets.QMessageBox.warning(self, _("Invalid Shortcut"), err_hk)
                return
            self.app.config["shortcut"] = shortcut
            self.app.config["theme"] = "gradient" if self.gradient_radio.isChecked() else "plain"

            if self.ui_locale_dropdown is not None:
                chosen_locale = self.ui_locale_dropdown.currentData() or "en"
                self.app.config["locale"] = chosen_locale
                if hasattr(self.app, "change_language"):
                    self.app.change_language(chosen_locale)

            if self.output_lang_dropdown is not None:
                out_data = self.output_lang_dropdown.currentData()
                if out_data == _CUSTOM_LANG_SENTINEL:
                    out_val = (
                        self.custom_output_lang_input.text().strip()
                        if self.custom_output_lang_input
                        else ""
                    ) or "auto"
                else:
                    out_val = out_data or "auto"
                self.app.config["output_language"] = out_val

            if self.global_rule_input is not None:
                self.app.config["global_rule"] = self.global_rule_input.text().strip()
            if self.check_focus_checkbox is not None:
                self.app.config["check_focus_before_paste"] = self.check_focus_checkbox.isChecked()
            if self.loading_indicator_checkbox is not None:
                self.app.config["show_loading_indicator"] = self.loading_indicator_checkbox.isChecked()
            if self.auto_pause_fullscreen_checkbox is not None:
                self.app.config["auto_pause_fullscreen"] = self.auto_pause_fullscreen_checkbox.isChecked()
            if self.terminal_shortcuts_checkbox is not None:
                self.app.config["enable_terminal_shortcuts"] = self.terminal_shortcuts_checkbox.isChecked()
            if self.app_blacklist_input is not None:
                self.app.config["app_blacklist"] = self.app_blacklist_input.text().strip()
            if self.app_shortcut_rules_input is not None:
                self.app.config["app_shortcut_rules"] = (
                    self.app_shortcut_rules_input.toPlainText().strip()
                )
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
