import gettext
import json
import logging
import os
import signal
import sys
import tempfile
import threading
import time

import darkdetect
import pyperclip
from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QLocale, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from writing_tools.ai_provider import (
    GeminiProvider,
    LanguageToolProvider,
    LlamaCppProvider,
    OpenAICompatibleProvider,
    obfuscate_api_key,
)
from writing_tools.paths import get_data_dir, get_resource_path
from writing_tools.ui import (
    about_window,
    custom_popup_window,
    onboarding_window,
    response_window,
    settings_window,
)
from writing_tools.update_checker import UpdateChecker

_ = gettext.gettext

CURRENT_CONFIG_VERSION = 9


class _SelectedTextHolder:
    """
    Carries the result of an async clipboard capture from `_show_popup` to
    `process_option_thread`. The capture thread sets `text` and signals
    `ready` once done.
    """

    __slots__ = ("text", "ready")

    def __init__(self):
        self.text = ""
        self.ready = threading.Event()


class WritingToolApp(QtWidgets.QApplication):
    """
    The main application class for Writing Tools.
    """

    output_ready_signal = Signal(str)
    show_message_signal = Signal(str, str)
    hotkey_triggered_signal = Signal()

    def __init__(self, argv):
        super().__init__(argv)
        self.current_response_window = None
        self._config_lock = threading.Lock()
        logging.debug("Initializing WritingToolApp")

        self.output_ready_signal.connect(self.replace_text)
        self.show_message_signal.connect(self.show_message_box)
        self.hotkey_triggered_signal.connect(self.on_hotkey_pressed)

        self.config = None
        self.config_path = None
        self.load_config()

        # Run any pending config migrations in a single pass.
        self._migrate_config()

        self.options = None
        self.options_path = None
        self.load_options()

        self.onboarding_window = None
        self.popup_window = None
        self.tray_icon = None
        self.tray_menu = None
        self.settings_window = None
        self.about_window = None
        self.registered_hotkey = None
        self.output_queue = ""
        self.hotkey_listener = None
        self.paused = False
        self.toggle_action = None
        self.update_checker = None
        self.current_provider = None

        # Holder and generation counter for async Ctrl+C clipboard capture.
        self.current_text_holder = None
        self._capture_lock = threading.Lock()
        self._capture_generation = 0
        self._clipboard_backup = ""

        self._ = gettext.gettext

        # Initialize the ctrl+c SIGINT listener
        self.ctrl_c_timer = None
        self.setup_ctrl_c_listener()

        # Setup available AI & proofreading providers
        self.providers = [
            GeminiProvider(self),
            OpenAICompatibleProvider(self),
            LlamaCppProvider(self),
            LanguageToolProvider(self),
        ]

        if not self.config:
            logging.debug("No config found, showing onboarding")
            self.show_onboarding()
        else:
            logging.debug("Config found, setting up hotkey and tray icon")

            default_provider_name = self.providers[0].provider_name
            provider_name = self.config.get("provider", default_provider_name)

            self.current_provider = next(
                (p for p in self.providers if p.provider_name == provider_name),
                None,
            )
            if not self.current_provider:
                logging.warning(f"Provider {provider_name} not found. Using default provider.")
                self.current_provider = self.providers[0]
                provider_name = self.current_provider.provider_name

            self.current_provider.load_config(
                self.config.get("providers", {}).get(provider_name, {})
            )

            self.create_tray_icon()
            self.register_hotkey()

            lang = self.config.get("locale")
            self.change_language(lang)

            self.init_update_checker()

        self.recent_triggers = []
        self.TRIGGER_WINDOW = 1.5
        self.MAX_TRIGGERS = 3

    def init_update_checker(self):
        """Initialize and run the async update checker if not already started."""
        if self.update_checker is None:
            self.update_checker = UpdateChecker(self)
            self.update_checker.check_updates_async()

    def setup_translations(self, lang=None):
        if not lang:
            lang = QLocale.system().name().split("_")[0]

        try:
            translation = gettext.translation(
                "messages",
                localedir=get_resource_path("locales"),
                languages=[lang],
            )
        except FileNotFoundError:
            translation = gettext.NullTranslations()

        translation.install()
        self._ = translation.gettext
        about_window._ = self._
        settings_window._ = self._
        response_window._ = self._
        onboarding_window._ = self._
        custom_popup_window._ = self._

    def retranslate_ui(self):
        if self.tray_menu is not None:
            self.update_tray_menu()

    def change_language(self, lang):
        self.setup_translations(lang)
        self.retranslate_ui()

        for widget in QApplication.topLevelWidgets():
            if widget != self and hasattr(widget, "retranslate_ui"):
                widget.retranslate_ui()

    def check_trigger_spam(self):
        """
        Check if hotkey is being triggered too frequently (3+ times in 1.5 seconds).
        Returns True if spam is detected.
        """
        current_time = time.time()
        self.recent_triggers.append(current_time)
        self.recent_triggers = [
            t for t in self.recent_triggers if current_time - t <= self.TRIGGER_WINDOW
        ]
        return len(self.recent_triggers) >= self.MAX_TRIGGERS

    def load_config(self):
        """
        Load the configuration file using UTF-8 encoding.
        """
        self.config_path = os.path.join(get_data_dir(), "config.json")
        logging.debug(f"Loading config from {self.config_path}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                    logging.debug("Config loaded successfully")
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"Failed to read config.json: {e}")
                self.config = None
        else:
            logging.debug("Config file not found")
            self.config = None

    def _migrate_config(self):
        """
        One-shot config migration up to CURRENT_CONFIG_VERSION.
        """
        NEW_DEFAULT_MODEL = "gemini-flash-latest"
        V8_TO_V9_MAP = {
            "gemma-3-27b-it": NEW_DEFAULT_MODEL,
            "gemma-3-4b-it": NEW_DEFAULT_MODEL,
            "gemini-flash-lite-latest": NEW_DEFAULT_MODEL,
            "gemini-2.0-flash": NEW_DEFAULT_MODEL,
            "gemini-2.0-flash-lite": NEW_DEFAULT_MODEL,
            "gemini-1.5-flash": NEW_DEFAULT_MODEL,
        }

        if not self.config:
            logging.debug("No config to migrate (new user)")
            return

        needs_v8 = not self.config.get("is_config_file_updated_for_v8", False)
        needs_v9 = not self.config.get("is_config_file_updated_for_v9", False)

        if not needs_v8 and not needs_v9:
            logging.debug("Config already up-to-date, no migration needed")
            return

        logging.info(f"Running config migration (needs_v8={needs_v8}, needs_v9={needs_v9})...")

        config_changed = False
        providers_cfg = self.config.get("providers", {})
        gemini_config = providers_cfg.get("Gemini (Recommended)")

        if isinstance(gemini_config, dict):
            old_model = gemini_config.get("model_name", "")

            if needs_v8:
                if old_model != NEW_DEFAULT_MODEL:
                    gemini_config["model_name"] = NEW_DEFAULT_MODEL
                    logging.info(f'[v8] Bumped Gemini model "{old_model}" -> "{NEW_DEFAULT_MODEL}"')
                    config_changed = True

                api_key = gemini_config.get("api_key", "")
                if api_key:
                    new_key = obfuscate_api_key(api_key)
                    if new_key != api_key:
                        gemini_config["api_key"] = new_key
                        logging.info("[v8] Obfuscated plaintext Gemini API key")
                        config_changed = True

            elif needs_v9:
                new_model = V8_TO_V9_MAP.get(old_model)
                if new_model is not None and new_model != old_model:
                    gemini_config["model_name"] = new_model
                    logging.info(f'[v9] Bumped Gemini model "{old_model}" -> "{new_model}"')
                    config_changed = True

        # Also obfuscate any legacy plaintext OpenAI-compatible API keys
        openai_config = providers_cfg.get("OpenAI Compatible (For Experts)")
        if isinstance(openai_config, dict):
            api_key = openai_config.get("api_key", "")
            if api_key:
                new_key = obfuscate_api_key(api_key)
                if new_key != api_key:
                    openai_config["api_key"] = new_key
                    logging.info("[v9] Obfuscated plaintext OpenAI-compatible API key")
                    config_changed = True

        # Migrate legacy Ollama provider selection to llama.cpp
        if self.config.get("provider") == "Ollama (For Experts)":
            self.config["provider"] = "llama.cpp (Local LLM)"
            logging.info("[v9] Migrated provider selection from Ollama to llama.cpp (Local LLM)")
            config_changed = True

        for n in range(8, CURRENT_CONFIG_VERSION + 1):
            self.config[f"is_config_file_updated_for_v{n}"] = True

        self.save_config(self.config)
        logging.info("Config migration complete")

        if config_changed:
            logging.info("Migrated config applied in-place; continuing startup.")

    def load_options(self):
        """
        Load options.json using UTF-8 encoding. Auto-restores defaults if missing or corrupt.
        """
        self.options_path = os.path.join(get_data_dir(), "options.json")
        logging.debug(f"Loading options from {self.options_path}")
        if os.path.exists(self.options_path):
            try:
                with open(self.options_path, "r", encoding="utf-8") as f:
                    self.options = json.load(f)
                    logging.debug("Options loaded successfully")
                    return
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"Failed to load options.json ({e}); falling back to defaults.")

        # Restore defaults if missing or unreadable (prefer bundled options.json)
        default_options_path = get_resource_path("options.json")
        if os.path.exists(default_options_path):
            with open(default_options_path, "r", encoding="utf-8") as f:
                self.options = json.load(f)
        else:
            self.options = json.loads(custom_popup_window.DEFAULT_OPTIONS_JSON)
        try:
            with open(self.options_path, "w", encoding="utf-8") as f:
                json.dump(self.options, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logging.warning(f"Could not write default options.json: {e}")

    def save_config(self, config):
        """
        Atomically and thread-safely save config.json with UTF-8 encoding.
        """
        with self._config_lock:
            self.config = config
            if not self.config_path:
                self.config_path = os.path.join(get_data_dir(), "config.json")
            config_dir = os.path.dirname(self.config_path) or "."
            os.makedirs(config_dir, exist_ok=True)
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=config_dir,
                    prefix=".config.",
                    suffix=".tmp",
                    delete=False,
                ) as tmp_file:
                    json.dump(config, tmp_file, indent=4, ensure_ascii=False)
                    tmp_path = tmp_file.name
                os.replace(tmp_path, self.config_path)
                logging.debug("Config saved successfully")
            except Exception as e:
                logging.error(f"Failed to save config.json: {e}")
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def show_onboarding(self):
        """
        Show the onboarding window for first-time users.
        """
        logging.debug("Showing onboarding window")
        self.onboarding_window = onboarding_window.OnboardingWindow(self)
        self.onboarding_window.close_signal.connect(self.exit_app)
        self.onboarding_window.show()

    @staticmethod
    def _to_pynput_hotkey(hotkey_str):
        """
        Convert a user-facing hotkey string ('ctrl+j', 'ctrl+alt+space') to
        pynput's `<ctrl>+j` / `<ctrl>+<alt>+<space>` format.
        """
        parts = [t.strip().lower() for t in hotkey_str.split("+") if t.strip()]
        return "+".join(t if len(t) <= 1 else f"<{t}>" for t in parts)

    def start_hotkey_listener(self):
        """
        Build a single `GlobalHotKeys` listener that handles both the main
        Writing Tools shortcut AND any per-button direct hotkeys defined in
        options.json.
        """
        try:
            if self.hotkey_listener is not None:
                self.hotkey_listener.stop()
                self.hotkey_listener = None

            hotkey_map = {}

            # Global Writing Tools hotkey
            orig_shortcut = (self.config.get("shortcut") or "ctrl+space").strip()
            self.registered_hotkey = orig_shortcut
            try:
                global_parsed = self._to_pynput_hotkey(orig_shortcut)
                pykeyboard.HotKey.parse(global_parsed)

                def on_global_activate():
                    if self.paused:
                        return
                    logging.debug("triggered global hotkey")
                    self.hotkey_triggered_signal.emit()

                hotkey_map[global_parsed] = on_global_activate
                logging.debug(f"Registered global hotkey: {global_parsed}")
            except Exception as e:
                logging.error(f'Failed to parse global hotkey "{orig_shortcut}": {e}')

            # Per-button direct hotkeys
            if self.options:
                for button_name, button_cfg in self.options.items():
                    if button_name == "Custom" or not isinstance(button_cfg, dict):
                        continue
                    raw = (button_cfg.get("hotkey") or "").strip()
                    if not raw:
                        continue
                    try:
                        parsed = self._to_pynput_hotkey(raw)
                        pykeyboard.HotKey.parse(parsed)
                    except Exception as e:
                        logging.error(f'Invalid hotkey "{raw}" for button "{button_name}": {e}')
                        continue
                    if parsed in hotkey_map:
                        logging.warning(
                            f'Hotkey "{raw}" for button "{button_name}" '
                            f"conflicts with an already-registered binding; skipping"
                        )
                        continue
                    hotkey_map[parsed] = self._make_button_hotkey_callback(button_name)
                    logging.debug(f"Registered button hotkey: {parsed} -> {button_name}")

            if not hotkey_map:
                logging.warning("No hotkeys to register")
                return

            self.hotkey_listener = pykeyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
        except Exception as e:
            logging.error(f"Failed to register hotkey listener: {e}")

    def _make_button_hotkey_callback(self, button_name):
        def callback():
            if self.paused:
                return
            logging.debug(f'Direct hotkey fired for button "{button_name}"')
            if self.current_provider:
                self.current_provider.cancel()
                self.output_queue = ""
            # noinspection PyTypeChecker
            QtCore.QMetaObject.invokeMethod(
                self,
                "_fire_button_directly",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, button_name),
            )

        return callback

    @Slot(str)
    def _fire_button_directly(self, button_name):
        logging.debug(f'Firing button "{button_name}" directly')

        if self.popup_window is not None and self.popup_window.isVisible():
            self.popup_window.close()

        if not self.options or button_name not in self.options:
            logging.warning(f'Button "{button_name}" no longer exists; ignoring hotkey')
            return

        self.current_text_holder = _SelectedTextHolder()
        self._fire_ctrl_c_and_capture_async(self.current_text_holder)
        self.process_option(button_name)

    def register_hotkey(self):
        logging.debug("Registering hotkey")
        self.start_hotkey_listener()
        logging.debug("Hotkey registered")

    def on_hotkey_pressed(self):
        logging.debug("Hotkey pressed")

        if self.check_trigger_spam():
            logging.warning("Hotkey spam detected - quitting application")
            self.exit_app()
            return

        if self.current_provider:
            logging.debug("Cancelling current provider's request")
            self.current_provider.cancel()
            self.output_queue = ""

        # noinspection PyTypeChecker
        QtCore.QMetaObject.invokeMethod(
            self, "_show_popup", QtCore.Qt.ConnectionType.QueuedConnection
        )

    @Slot()
    def _show_popup(self):
        logging.debug("Showing popup window")

        self.current_text_holder = _SelectedTextHolder()
        self._fire_ctrl_c_and_capture_async(self.current_text_holder)

        try:
            if self.popup_window is not None:
                if self.popup_window.isVisible():
                    self.popup_window.close()
                self.popup_window = None

            self.popup_window = custom_popup_window.CustomPopupWindow(self)

            icon_path = get_resource_path("icons", "app_icon.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QtGui.QIcon(icon_path))

            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            screen_geometry = screen.geometry()

            self.popup_window.show()
            self.popup_window.adjustSize()
            self.popup_window.activateWindow()
            QtCore.QTimer.singleShot(100, self.popup_window.custom_input.setFocus)

            popup_width = self.popup_window.width()
            popup_height = self.popup_window.height()
            x = cursor_pos.x()
            y = cursor_pos.y() + 20
            if x + popup_width > screen_geometry.right():
                x = screen_geometry.right() - popup_width
            if y + popup_height > screen_geometry.bottom():
                y = cursor_pos.y() - popup_height - 10
            self.popup_window.move(x, y)
            logging.debug(f"Popup window moved to position: ({x}, {y})")
        except Exception as e:
            logging.error(f"Error showing popup window: {e}", exc_info=True)

    @staticmethod
    def _release_interfering_modifiers(kbrd):
        """
        Release Alt/Win/Shift modifiers that may still be physically held from
        the user's activation shortcut so simulated Ctrl+C / Ctrl+V does not turn
        into Ctrl+Alt+C ('₢'), Ctrl+Win+C (Windows color filters), or bare 'c'.
        """
        modifier_names = (
            "alt", "alt_l", "alt_r", "alt_gr",
            "cmd", "cmd_l", "cmd_r",
            "shift", "shift_l", "shift_r",
        )
        for name in modifier_names:
            key = getattr(pykeyboard.Key, name, None)
            if key is not None:
                try:
                    kbrd.release(key)
                except Exception:
                    pass

    @staticmethod
    def _platform_shortcut_key(char: str, windows_vk: int):
        """
        Use Windows virtual key codes (e.g., 0x43 for C, 0x56 for V) so Ctrl+C /
        Ctrl+V works reliably regardless of active non-Latin keyboard layouts.
        """
        if sys.platform.startswith("win32"):
            return pykeyboard.KeyCode.from_vk(windows_vk)
        return char

    @classmethod
    def _simulate_ctrl_chord(cls, char: str, windows_vk: int):
        """Safely inject Ctrl+<key> after clearing interfering modifiers."""
        kbrd = pykeyboard.Controller()
        cls._release_interfering_modifiers(kbrd)
        target_key = cls._platform_shortcut_key(char, windows_vk)
        with kbrd.pressed(pykeyboard.Key.ctrl):
            kbrd.press(target_key)
            kbrd.release(target_key)

    @staticmethod
    def _read_clipboard_on_gui_thread() -> str:
        """
        Read clipboard via Qt's QClipboard on the GUI thread to avoid the Linux
        X11 deadlock where spawning `xclip -o` via pyperclip hangs forever if
        Writing Tools itself currently owns the clipboard.
        """
        try:
            cb = QtWidgets.QApplication.clipboard()
            if cb is not None:
                return cb.text() or ""
        except Exception:
            pass
        try:
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def _fire_ctrl_c_and_capture_async(self, holder):
        """
        Inject Ctrl+C while focus is still on the source app, then poll the
        clipboard in a background thread. Uses a generation counter so rapid
        consecutive hotkey triggers do not clobber each other's clipboard backup.
        """
        with self._capture_lock:
            self._capture_generation += 1
            my_gen = self._capture_generation
            if my_gen == 1 or not getattr(self, "_capture_active", False):
                self._clipboard_backup = self._read_clipboard_on_gui_thread()
                self._capture_active = True

            self.clear_clipboard()

            try:
                self._simulate_ctrl_chord("c", 0x43)
            except Exception as e:
                logging.error(f"Error simulating Ctrl+C: {e}")

        def _poll_clipboard():
            text = ""
            try:
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    if self._capture_generation != my_gen:
                        return
                    try:
                        text = pyperclip.paste() or ""
                    except Exception as e:
                        logging.error(f"Error reading clipboard during poll: {e}")
                        text = ""
                    if text:
                        break
                    time.sleep(0.05)
                holder.text = text
                logging.debug(f"Captured selected text (len={len(text)})")
            finally:
                with self._capture_lock:
                    if self._capture_generation == my_gen:
                        try:
                            pyperclip.copy(self._clipboard_backup)
                        except Exception as e:
                            logging.error(f"Error restoring clipboard: {e}")
                        self._capture_active = False
                holder.ready.set()

        threading.Thread(target=_poll_clipboard, daemon=True).start()

    @staticmethod
    def clear_clipboard():
        try:
            cb = QtWidgets.QApplication.clipboard()
            if cb is not None:
                cb.clear()
                return
        except Exception:
            pass
        try:
            pyperclip.copy("")
        except Exception as e:
            logging.error(f"Error clearing clipboard: {e}")

    def process_option(self, option, custom_change=None):
        logging.debug(f"Processing option: {option}")
        self.current_response_window = None

        threading.Thread(
            target=self.process_option_thread,
            args=(option, custom_change),
            daemon=True,
        ).start()

    @Slot(str, str)
    def _setup_response_window(self, option, selected_text):
        self.current_response_window = self.show_response_window(option, selected_text)
        self.current_response_window.chat_history = [
            {
                "role": "user",
                "content": f"Original text to {option.lower()}:\n\n{selected_text}",
            }
        ]

    def process_option_thread(self, option, custom_change=None):
        logging.debug(f"Starting processing thread for option: {option}")

        if not self.options or option not in self.options:
            self.show_message_signal.emit("Error", f"Option '{option}' is not available.")
            return

        if not self.current_provider:
            self.show_message_signal.emit("Error", "No AI provider configured. Please open Settings.")
            return

        holder = self.current_text_holder
        if holder is None or not holder.ready.wait(timeout=3.0):
            logging.warning("Timed out waiting for selected text capture")
        selected_text = (holder.text if holder else "") or ""

        if not selected_text.strip():
            self.show_message_signal.emit("Error", "Please select text to use this option.")
            return

        option_cfg = self.options[option]
        open_in_window = bool(option_cfg.get("open_in_window", False))

        if open_in_window:
            QtCore.QMetaObject.invokeMethod(
                self,
                "_setup_response_window",
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                QtCore.Q_ARG(str, option),
                QtCore.Q_ARG(str, selected_text),
            )

        try:
            prompt_prefix = option_cfg.get("prefix", "")
            system_instruction = option_cfg.get("instruction", "")
            if getattr(self.current_provider, "is_non_ai", False):
                prompt = selected_text
            elif option == "Custom":
                prompt = f"{prompt_prefix}Described change: {custom_change}\n\nText: {selected_text}"
            else:
                prompt = f"{prompt_prefix}{selected_text}"

            self.output_queue = ""

            if open_in_window:
                response_window = self.current_response_window
                response = self.current_provider.get_response(
                    system_instruction, prompt, return_response=True
                )
                logging.debug(f"Got response of length: {len(response) if response else 0}")

                if response_window is not None and not getattr(response_window, "_closed", False):
                    if response:
                        # noinspection PyTypeChecker
                        QtCore.QMetaObject.invokeMethod(
                            response_window,
                            "set_text",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, response),
                        )
                    else:
                        QtCore.QMetaObject.invokeMethod(
                            response_window,
                            "stop_thinking_animation",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                        )
            else:
                self.current_provider.get_response(system_instruction, prompt)

        except Exception as e:
            logging.error(f"An error occurred: {e}", exc_info=True)
            lower_err = str(e).lower()
            if "resource has been exhausted" in lower_err or "resource_exhausted" in lower_err or "429" in lower_err:
                self.show_message_signal.emit(
                    "Error - Rate Limit Hit",
                    "You have hit the API rate limit. Please try again in a few moments "
                    "or switch models in Settings.",
                )
            else:
                self.show_message_signal.emit("Error", f"An error occurred: {e}")

    @Slot(str, str)
    def show_message_box(self, title, message):
        QMessageBox.warning(None, title, message)

    def show_response_window(self, option, text):
        win = response_window.ResponseWindow(self, f"{option} Result")
        win.selected_text = text
        win.show()
        return win

    @Slot(str)
    def replace_text(self, new_text):
        """
        Replaces the selected text by pasting the LLM-generated text.
        """
        error_message = "ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST"

        if new_text and isinstance(new_text, str):
            self.output_queue += new_text
            current_output = self.output_queue.strip()

            if current_output == error_message:
                self.output_queue = ""
                self.show_message_signal.emit(
                    "Error", "The text is incompatible with the requested change."
                )
                return

            if len(current_output) <= len(error_message):
                clean_current = "".join(current_output.split())
                clean_error = "".join(error_message.split())
                if clean_current == clean_error[: len(clean_current)]:
                    return

            logging.debug("Processing output text")
            try:
                if self.current_response_window is not None:
                    self.current_response_window.set_text(self.output_queue.rstrip("\n"))
                else:
                    clipboard_backup = self._read_clipboard_on_gui_thread()
                    cleaned_text = self.output_queue.rstrip("\n")
                    pyperclip.copy(cleaned_text)

                    self._simulate_ctrl_chord("v", 0x56)

                    time.sleep(0.2)
                    pyperclip.copy(clipboard_backup)

                self.output_queue = ""

            except Exception as e:
                logging.error(f"Error processing output: {e}")
                self.output_queue = ""
        else:
            logging.debug("No new text to process")

    def create_tray_icon(self):
        if self.tray_icon:
            return

        logging.debug("Creating system tray icon")
        icon_path = get_resource_path("icons", "app_icon.png")
        if not os.path.exists(icon_path):
            logging.warning(f"Tray icon not found at {icon_path}")
            self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        else:
            self.tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(icon_path), self)

        self.tray_icon.setToolTip("WritingTools")
        self.tray_menu = QtWidgets.QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.update_tray_menu()
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        """Open the popup window when the user left-clicks the system tray icon."""
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger and not self.paused:
            self._show_popup()

    def update_tray_menu(self):
        if self.tray_menu is None:
            return
        self.tray_menu.clear()
        self.apply_dark_mode_styles(self.tray_menu)

        settings_action = self.tray_menu.addAction(self._("Settings"))
        settings_action.triggered.connect(lambda: self.show_settings(providers_only=False))

        self.toggle_action = self.tray_menu.addAction(
            self._("Resume") if self.paused else self._("Pause")
        )
        self.toggle_action.triggered.connect(self.toggle_paused)

        about_action = self.tray_menu.addAction(self._("About"))
        about_action.triggered.connect(self.show_about)

        exit_action = self.tray_menu.addAction(self._("Exit"))
        exit_action.triggered.connect(self.exit_app)

    def toggle_paused(self):
        self.paused = not self.paused
        if self.toggle_action is not None:
            self.toggle_action.setText(self._("Resume") if self.paused else self._("Pause"))
        logging.debug("App is paused" if self.paused else "App is resumed")

    @staticmethod
    def apply_dark_mode_styles(menu):
        is_dark_mode = darkdetect.isDark()
        palette = menu.palette()

        if is_dark_mode:
            palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#2d2d2d"))
            palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#ffffff"))
        else:
            palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
            palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#000000"))

        menu.setPalette(palette)

    def process_followup_question(self, response_window, question):
        """
        Process a follow-up question in the chat window without duplicating the user turn
        in `chat_history` and routing the response directly to the owning ResponseWindow.
        """
        logging.debug(f"Processing follow-up question (len={len(question)})")

        def process_thread():
            try:
                if not response_window.chat_history:
                    logging.error("No chat history found")
                    self.show_message_signal.emit("Error", "Chat history not found")
                    return

                # Copy history (ResponseWindow.send_message already appended the user message)
                history = list(response_window.chat_history)
                if not history or history[-1].get("role") != "user" or history[-1].get("content") != question:
                    history.append({"role": "user", "content": question})

                system_instruction = (
                    "You are a helpful AI assistant. Provide clear and direct responses, "
                    "maintaining the same format and style as your previous responses. "
                    "If appropriate, use Markdown formatting to make your response more readable."
                )

                # Pydantic AI handles message/role translation uniformly across all providers
                response_text = self.current_provider.get_response(
                    system_instruction,
                    history,
                    return_response=True,
                )

                logging.debug(f"Got follow-up response of length: {len(response_text)}")

                if not getattr(response_window, "_closed", False):
                    # noinspection PyTypeChecker
                    QtCore.QMetaObject.invokeMethod(
                        response_window,
                        "handle_followup_response",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, response_text or ""),
                    )

            except Exception as e:
                logging.error(f"Error processing follow-up question: {e}", exc_info=True)
                self.show_message_signal.emit("Error", f"An error occurred: {e}")
                if not getattr(response_window, "_closed", False):
                    # noinspection PyTypeChecker
                    QtCore.QMetaObject.invokeMethod(
                        response_window,
                        "handle_followup_response",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, "Sorry, an error occurred while processing your question."),
                    )

        threading.Thread(target=process_thread, daemon=True).start()

    def show_settings(self, providers_only=False):
        logging.debug("Showing settings window")
        self.settings_window = settings_window.SettingsWindow(self, providers_only=providers_only)
        self.settings_window.close_signal.connect(self.exit_app)
        self.settings_window.retranslate_ui()
        self.settings_window.show()

    def show_about(self):
        logging.debug("Showing about window")
        if not self.about_window:
            self.about_window = about_window.AboutWindow()
        self.about_window.show()

    def setup_ctrl_c_listener(self):
        signal.signal(signal.SIGINT, self.handle_sigint)
        # Empty timer ensures Python signal handlers run regularly inside Qt's event loop
        self.ctrl_c_timer = QtCore.QTimer()
        self.ctrl_c_timer.start(100)
        self.ctrl_c_timer.timeout.connect(lambda: None)

    def handle_sigint(self, signum, frame):
        logging.info("Received SIGINT. Scheduling graceful exit...")
        QtCore.QTimer.singleShot(0, self.exit_app)

    @Slot()
    def exit_app(self):
        logging.debug("Stopping the listener")
        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception as e:
                logging.debug(f"Error stopping hotkey listener: {e}")
            self.hotkey_listener = None
        logging.debug("Exiting application")
        self.quit()
