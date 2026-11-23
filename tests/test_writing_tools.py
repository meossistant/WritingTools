import json
import os
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Allow headless CI/SSH test runs when no X11 display is available for pynput
try:
    from pynput import keyboard as _pykeyboard  # noqa: F401
except ImportError:
    _mock_pynput = MagicMock()
    _mock_pynput.keyboard.HotKey.parse = MagicMock(return_value=set())
    sys.modules["pynput"] = _mock_pynput
    sys.modules["pynput.keyboard"] = _mock_pynput.keyboard

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402
from pydantic_ai.models.google import GoogleModel  # noqa: E402
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from writing_tools import ai_provider  # noqa: E402
from writing_tools.app import WritingToolApp  # noqa: E402
from writing_tools.autostart import AutostartManager  # noqa: E402
from writing_tools.paths import get_resource_path  # noqa: E402
from writing_tools.ui.about_window import AboutWindow  # noqa: E402
from writing_tools.ui.custom_popup_window import ButtonEditDialog, CustomPopupWindow  # noqa: E402
from writing_tools.ui.onboarding_window import OnboardingWindow  # noqa: E402
from writing_tools.ui.response_window import ResponseWindow  # noqa: E402
from writing_tools.ui.settings_window import SettingsWindow  # noqa: E402
from writing_tools.ui.ui_utils import UIUtils  # noqa: E402
from writing_tools.update_checker import CURRENT_VERSION, CURRENT_VERSION_STRING  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["pytest"])
    return app


class DummySignal:
    def __init__(self):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args)


class DummyApp:
    def __init__(self):
        self.config = {"providers": {}, "shortcut": "ctrl+space", "theme": "gradient", "locale": "it"}
        self.current_response_window = None
        self.output_ready_signal = DummySignal()
        self.show_message_signal = DummySignal()
        self.providers = []
        self.current_provider = None
        self.saved_configs = []
        self.options_reloaded = 0
        self.hotkeys_registered = 0
        self.tray_created = False
        self.update_checker_inited = False
        self.followup_calls = []

    def save_config(self, cfg):
        self.config = cfg
        self.saved_configs.append(json.loads(json.dumps(cfg)))

    def load_options(self):
        self.options_reloaded += 1

    def register_hotkey(self):
        self.hotkeys_registered += 1

    def create_tray_icon(self):
        self.tray_created = True

    def init_update_checker(self):
        self.update_checker_inited = True

    def process_followup_question(self, window, msg):
        self.followup_calls.append((window, msg))

    @staticmethod
    def _to_pynput_hotkey(hotkey_str):
        return WritingToolApp._to_pynput_hotkey(hotkey_str)


def test_api_key_obfuscation_roundtrip_and_corrupt_recovery():
    secret = "AIzaSyTestKey_12345-xyz"
    obf = ai_provider.obfuscate_api_key(secret)
    assert obf.startswith("enc:")
    assert obf != secret
    assert ai_provider.obfuscate_api_key(obf) == obf
    assert ai_provider.deobfuscate_api_key(obf) == secret
    assert ai_provider.deobfuscate_api_key("plain-key") == "plain-key"
    assert ai_provider.deobfuscate_api_key("enc:%%%not-valid-base64%%%") == ""


def test_pydantic_ai_message_conversion_single_and_multiturn():
    single = ai_provider.AIProvider.build_messages("Be concise.", "Proofread this.")
    assert len(single) == 1
    assert isinstance(single[0], ModelRequest)
    assert single[0].instructions == "Be concise."
    assert single[0].parts[0].content == "Proofread this."

    history = [
        {"role": "system", "content": "Ignored when explicit system_instruction is passed"},
        {"role": "user", "content": "Original text"},
        {"role": "assistant", "content": "Summary here"},
        {"role": "user", "content": "Follow-up question"},
    ]
    multi = ai_provider.AIProvider.build_messages("Stay helpful.", history)
    assert len(multi) == 3
    assert isinstance(multi[0], ModelRequest)
    assert isinstance(multi[1], ModelResponse)
    assert isinstance(multi[2], ModelRequest)
    assert multi[2].instructions == "Stay helpful."
    assert multi[1].text == "Summary here"


def test_gemini_pydantic_ai_model_and_thinking_config():
    app = DummyApp()
    provider = ai_provider.GeminiProvider(app)

    provider.load_config({"api_key": "", "model_name": "gemini-3.8-flash"})
    assert provider.model is None
    assert provider.get_response("sys", "hello") == ""
    assert len(app.output_ready_signal.emissions) == 0
    assert len(app.show_message_signal.emissions) == 1

    provider.load_config({
        "api_key": ai_provider.obfuscate_api_key("AIzaSyFakeKey"),
        "model_name": "gemini-4-hydrogen",
    })
    assert isinstance(provider.model, GoogleModel)
    assert provider.model.model_name == "gemini-4-hydrogen"

    provider.model_name = "gemma-4-31b-it"
    assert "google_thinking_config" not in provider._build_model_settings()

    for m in ("gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3-flash-preview"):
        provider.model_name = m
        assert provider._build_model_settings()["google_thinking_config"] == {"thinking_level": "minimal"}

    for m in ("gemini-4-hydrogen", "gemini-4-neon", "gemini-3.8-flash", "gemini-flash-latest"):
        provider.model_name = m
        assert provider._build_model_settings()["google_thinking_config"] == {"thinking_level": "low"}

    provider.model_name = "gemini-2.5-flash"
    assert provider._build_model_settings()["google_thinking_config"] == {"thinking_budget": 0}
    assert provider._build_model_settings()["max_tokens"] >= 8192


def test_unified_pydantic_ai_execution_cancellation_and_errors():
    app = DummyApp()
    provider = ai_provider.GeminiProvider(app)
    app.replace_text = MagicMock()

    captured_settings = []

    def ok_handler(messages, info):
        captured_settings.append(info.model_settings)
        return ModelResponse(parts=[TextPart(content="  Fixed text\n")])

    provider.model = FunctionModel(ok_handler)
    res = provider.get_response("Fix grammar", "bad text", return_response=False)
    assert res == ""
    assert app.output_ready_signal.emissions == [("Fixed text",)]
    app.replace_text.assert_not_called()
    assert captured_settings[0]["max_tokens"] == 8192

    res_chat = provider.get_response(
        "Be helpful",
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "More?"},
        ],
        return_response=True,
    )
    assert res_chat == "Fixed text"

    app.output_ready_signal.emissions.clear()

    def cancelled_handler(messages, info):
        provider.cancel()
        return ModelResponse(parts=[TextPart(content="Stale text")])

    provider.model = FunctionModel(cancelled_handler)
    assert provider.get_response("sys", "text", return_response=False) == ""
    assert len(app.output_ready_signal.emissions) == 0

    app.show_message_signal.emissions.clear()

    def error_handler(messages, info):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    provider.model = FunctionModel(error_handler)
    assert provider.get_response("sys", "text", return_response=False) == ""
    assert len(app.output_ready_signal.emissions) == 0
    assert len(app.show_message_signal.emissions) == 1
    assert "Rate Limit" in app.show_message_signal.emissions[0][0]


def test_openai_pydantic_ai_model_settings_and_headers():
    app = DummyApp()
    provider = ai_provider.OpenAICompatibleProvider(app)

    provider.load_config({
        "api_key": ai_provider.obfuscate_api_key("sk-test-123"),
        "api_base": "https://api.openai.com/v1",
        "api_organisation": "",
        "api_project": "",
        "api_model": "gpt-6-luna",
    })
    assert isinstance(provider.model, OpenAIChatModel)
    assert provider.model.model_name == "gpt-6-luna"
    assert "temperature" not in provider._build_model_settings()
    assert provider._build_model_settings()["max_tokens"] == 8192

    provider.api_model = "gpt-4.1-mini"
    provider.max_tokens = "2048"
    assert provider._build_model_settings()["temperature"] == 0.5
    assert provider._build_model_settings()["max_tokens"] == 2048

    # Issue #263: Groq & trailing /chat/completions normalization
    assert (
        ai_provider.OpenAICompatibleProvider._normalize_base_url("https://api.groq.com/openai")
        == "https://api.groq.com/openai/v1"
    )
    assert (
        ai_provider.OpenAICompatibleProvider._normalize_base_url(
            "https://api.openai.com/v1/chat/completions"
        )
        == "https://api.openai.com/v1"
    )

    with patch("writing_tools.ai_provider.AsyncOpenAI") as mock_async_openai:
        mock_async_openai.return_value = MagicMock()
        provider.load_config({
            "api_key": "sk-test-org",
            "api_base": "https://api.openai.com/v1",
            "api_organisation": "org-123",
            "api_project": "proj-456",
            "api_model": "gpt-5.4-mini",
        })
        mock_async_openai.assert_called_once_with(
            api_key="sk-test-org",
            base_url="https://api.openai.com/v1",
            organization="org-123",
            project="proj-456",
        )


def test_llamacpp_pydantic_ai_model_gemma4_e2b_and_url_normalization():
    app = DummyApp()
    provider = ai_provider.LlamaCppProvider(app)

    assert provider.provider_name == "llama.cpp (Local LLM)"
    assert provider.api_model == "gemma-4-E2B-it"
    assert provider._normalize_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080/v1"
    assert provider._normalize_base_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080/v1"
    assert provider._normalize_base_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"

    provider.load_config({
        "api_base": "http://127.0.0.1:8080",
        "api_model": "gemma-4-E2B-it",
        "api_key": "",
    })
    assert isinstance(provider.model, OpenAIChatModel)
    assert provider.model.model_name == "gemma-4-E2B-it"
    settings = provider._build_model_settings()
    assert settings["temperature"] == 0.5
    assert settings["max_tokens"] == 4096

    provider.load_config({
        "api_base": "http://127.0.0.1:8080/v1",
        "api_model": "ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M",
        "api_key": ai_provider.obfuscate_api_key("local-secret"),
    })
    assert provider.api_key == "local-secret"
    assert provider.model.model_name == "ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M"


def test_uiutils_clear_layout_handles_spacer(qapp):
    w = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(w)
    layout.addWidget(QtWidgets.QLabel("hello"))
    layout.addStretch()
    UIUtils.clear_layout(layout)
    assert layout.count() == 0


def test_settings_window_deobfuscates_key_and_preserves_locale(qapp):
    app = DummyApp()
    gemini = ai_provider.GeminiProvider(app)
    openai_p = ai_provider.OpenAICompatibleProvider(app)
    llamacpp_p = ai_provider.LlamaCppProvider(app)
    app.providers = [gemini, openai_p, llamacpp_p]
    app.config["provider"] = gemini.provider_name
    app.config["providers"][gemini.provider_name] = {
        "api_key": ai_provider.obfuscate_api_key("my-real-secret-key"),
        "model_name": "gemini-4-hydrogen",
    }

    win = SettingsWindow(app, providers_only=False)
    assert gemini.settings[0].input.text() == "my-real-secret-key"
    assert gemini.settings[0].input.echoMode() == QtWidgets.QLineEdit.EchoMode.Password

    win.save_settings()

    assert app.config["locale"] == "it"
    assert app.config["is_config_file_updated_for_v8"] is True
    assert app.config["is_config_file_updated_for_v9"] is True
    stored_key = app.config["providers"][gemini.provider_name]["api_key"]
    assert stored_key.startswith("enc:")
    assert ai_provider.deobfuscate_api_key(stored_key) == "my-real-secret-key"
    assert isinstance(app.current_provider.model, GoogleModel)
    win.close()


def test_response_window_parent_lookup_zoom_and_no_duplicate_history(qapp):
    app = DummyApp()
    app.config["response_window_zoom"] = 1.6
    win = ResponseWindow(app, "Summary Result")
    win.selected_text = "Some long article text."

    assert win.chat_area.get_response_window() is win

    win.set_text("Here is a summary:\n\n```python\nprint(1)\n```")
    assert win.current_text_display is not None
    assert win.current_text_display.zoom_factor == pytest.approx(1.6)

    win.input_field.setText("Tell me more")
    win.send_message()
    user_msgs = [m for m in win.chat_history if m["content"] == "Tell me more"]
    assert len(user_msgs) == 1
    assert len(app.followup_calls) == 1

    win.zoom_all_messages("in")
    expected_zoom = win.current_text_display.zoom_factor
    win.close()
    assert win._closed is True
    assert app.config["response_window_zoom"] == pytest.approx(expected_zoom)


def test_custom_popup_and_button_edit_dialog(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("writing_tools.ui.custom_popup_window.get_data_dir", lambda: str(tmp_path))
    opts = CustomPopupWindow.load_options()
    assert "Proofread" in opts
    assert "\\'" not in opts["Custom"]["instruction"]

    # Verify snake_case icon assets exist
    assert os.path.exists(get_resource_path("icons", "magnifying_glass_dark.png"))
    assert os.path.exists(get_resource_path("icons", "smiley_face_light.png"))
    assert os.path.exists(get_resource_path("icons", "provider_llamacpp.png"))
    assert os.path.exists(get_resource_path("backgrounds", "background_dark.png"))

    proofread_data = dict(opts["Proofread"])
    proofread_data["name"] = "Proofread"
    dlg = ButtonEditDialog(None, proofread_data)
    updated = dlg.get_button_data()
    assert updated["icon"] == "icons/magnifying_glass"
    assert updated["prefix"] == "Proofread this:\n\n"
    dlg.close()

    app = DummyApp()
    popup = CustomPopupWindow(app)
    ok_empty, _ = popup._validate_button_name("")
    ok_custom, _ = popup._validate_button_name("Custom")
    ok_valid, _ = popup._validate_button_name("Translate")
    assert ok_empty is False
    assert ok_custom is False
    assert ok_valid is True
    popup.close()


def test_about_and_onboarding_windows_and_version_alignment(qapp):
    assert CURRENT_VERSION == 9
    assert CURRENT_VERSION_STRING == "9.0"
    with open(os.path.join(ROOT_DIR, "version.txt"), "r", encoding="utf-8") as f:
        assert int(f.read().strip()) == CURRENT_VERSION

    about = AboutWindow()
    about.close()

    app = DummyApp()
    onboarding = OnboardingWindow(app)
    onboarding.self_close = True
    onboarding.close()


def test_linux_autostart_roundtrip(tmp_path, monkeypatch):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-only XDG autostart test")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert AutostartManager.get_startup_path() is not None
    assert AutostartManager.check_autostart() is False
    assert AutostartManager.set_autostart(True) is True
    assert AutostartManager.check_autostart() is True
    assert AutostartManager.set_autostart(False) is True
    assert AutostartManager.check_autostart() is False


def test_config_migration_and_utf8_atomic_save(tmp_path):
    class _MinimalApp:
        def __init__(self):
            self._config_lock = threading.Lock()
            self.config_path = str(tmp_path / "config.json")
            self.config = {
                "provider": "Ollama (For Experts)",
                "shortcut": "ctrl+space",
                "locale": "vi",
                "providers": {
                    "Gemini (Recommended)": {
                        "api_key": "plain-gemini-key",
                        "model_name": "gemini-2.0-flash",
                    },
                    "OpenAI Compatible (For Experts)": {
                        "api_key": "plain-openai-key",
                        "api_model": "gpt-4o-mini",
                    },
                },
                "custom_note": "Tiếng Việt UTF-8",
            }

        save_config = WritingToolApp.save_config
        _migrate_config = WritingToolApp._migrate_config

    app = _MinimalApp()
    app._migrate_config()

    assert app.config["is_config_file_updated_for_v8"] is True
    assert app.config["is_config_file_updated_for_v9"] is True
    assert app.config["provider"] == "llama.cpp (Local LLM)"
    assert app.config["providers"]["Gemini (Recommended)"]["model_name"] == "gemini-flash-latest"
    assert app.config["providers"]["Gemini (Recommended)"]["api_key"].startswith("enc:")
    assert app.config["providers"]["OpenAI Compatible (For Experts)"]["api_key"].startswith("enc:")

    with open(app.config_path, "r", encoding="utf-8") as f:
        persisted = json.load(f)
    assert persisted["custom_note"] == "Tiếng Việt UTF-8"
    assert WritingToolApp._to_pynput_hotkey("Ctrl + Shift + P") == "<ctrl>+<shift>+p"


def test_strip_thinking_tags_for_reasoning_models():
    # Issue #109: DeepSeek R1 / QwQ style <think>...</think> blocks
    raw = "<think>\nLet me analyze the grammar carefully...\n</think>\n\nCorrected sentence."
    assert ai_provider.strip_thinking_tags(raw) == "Corrected sentence."
    assert ai_provider.strip_thinking_tags("Normal output") == "Normal output"


def test_response_window_copy_latest_markdown(qapp):
    # Issues #249 & #170: Copy as Markdown must copy latest response, not only first
    app = DummyApp()
    win = ResponseWindow(app, "Summary Result")
    win.selected_text = "Original text"
    win.set_text("First summary")
    win.input_field.setText("Give me more detail")
    win.send_message()
    win.handle_followup_response("Second follow-up answer")
    assert win.get_first_response_text() == "First summary"
    assert win.get_latest_response_text() == "Second follow-up answer"
    win.copy_latest_response()
    assert QtWidgets.QApplication.clipboard().text() == "Second follow-up answer"
    win.close()


def test_single_instance_lock_enforcement(tmp_path):
    # Issue #233: Single instance enforcement via QLockFile
    from writing_tools.main import acquire_single_instance_lock

    lock_path = str(tmp_path / "wt-test.lock")
    first = acquire_single_instance_lock(lock_path)
    assert first is not None
    second = acquire_single_instance_lock(lock_path)
    assert second is None
    first.unlock()
    third = acquire_single_instance_lock(lock_path)
    assert third is not None
    third.unlock()


def test_gui_clipboard_avoids_pyperclip_deadlock_and_vk_shortcuts(qapp, monkeypatch):
    # Issue #288: GUI-thread clipboard read must use QClipboard, not pyperclip.paste()
    QtWidgets.QApplication.clipboard().setText("qt-owned-text")
    with patch("writing_tools.app.pyperclip.paste", side_effect=AssertionError("must not call pyperclip.paste on GUI thread")):
        assert WritingToolApp._read_clipboard_on_gui_thread() == "qt-owned-text"

    # Issues #270 & #275: Windows virtual key codes for non-Latin layouts
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("writing_tools.app.pykeyboard.KeyCode.from_vk", side_effect=lambda vk: f"VK_{vk:#x}"):
        assert WritingToolApp._platform_shortcut_key("c", 0x43) == "VK_0x43"
        assert WritingToolApp._platform_shortcut_key("v", 0x56) == "VK_0x56"

    monkeypatch.setattr(sys, "platform", "linux")
    assert WritingToolApp._platform_shortcut_key("c", 0x43) == "c"

    # Issues #195, #185, #183: interfering modifiers released before Ctrl chord
    mock_ctrl = MagicMock()
    with patch("writing_tools.app.pykeyboard.Controller", return_value=mock_ctrl):
        WritingToolApp._simulate_ctrl_chord("c", 0x43)
        assert mock_ctrl.release.call_count >= 1
        mock_ctrl.pressed.assert_called_once()


def test_popup_window_has_tool_flag_no_taskbar_entry(qapp, tmp_path, monkeypatch):
    # Issue #142: popup window should not flash a taskbar button
    from PySide6 import QtCore

    monkeypatch.setattr("writing_tools.ui.custom_popup_window.get_data_dir", lambda: str(tmp_path))
    app = DummyApp()
    popup = CustomPopupWindow(app)
    assert bool(popup.windowFlags() & QtCore.Qt.WindowType.Tool)
    popup.close()
