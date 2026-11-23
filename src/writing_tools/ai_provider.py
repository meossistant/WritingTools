"""
AI Provider Architecture for Writing Tools (powered by Pydantic AI)
--------------------------------------------------------------------

Uses `pydantic-ai` (`GoogleModel`/`GoogleProvider`, `OpenAIChatModel`/`OpenAIProvider`,
and `OpenAIChatModel` backed by local `llama.cpp` `llama-server`) with
`pydantic_ai.direct.model_request_sync` for unified, type-safe request execution,
message history translation, and model settings across all supported AI providers.
"""

import base64
import binascii
import logging
import re
import threading
import webbrowser
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from openai import AsyncOpenAI
from pydantic_ai.direct import model_request_sync
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from PySide6 import QtWidgets
from PySide6.QtWidgets import QLineEdit, QVBoxLayout

from writing_tools.ui.ui_utils import COLOR_MODE

# Obfuscation prefix to identify obfuscated API keys
_OBFUSCATION_PREFIX = "enc:"
_XOR_KEY = 0x5A  # Lightweight XOR obfuscation key (prevents casual plaintext scanning)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_thinking_tags(text: str) -> str:
    """
    Strip `<think>...</think>` reasoning blocks emitted by reasoning models
    (e.g., DeepSeek R1, QwQ, Qwen3) so raw chain-of-thought is never pasted
    into the user's editor.
    """
    if not text:
        return ""
    cleaned = _THINK_TAG_RE.sub("", text)
    return cleaned.strip()


def parse_max_tokens(raw_value, default: int = 8192) -> int:
    """Parse a positive integer max_tokens setting with a safe default fallback."""
    try:
        parsed = int(str(raw_value).strip())
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return default


def obfuscate_api_key(key: str) -> str:
    """
    Obfuscate an API key using XOR + Base64 encoding.
    Returns the obfuscated string with 'enc:' prefix.
    """
    if not key or key.startswith(_OBFUSCATION_PREFIX):
        return key
    xored = bytes(b ^ _XOR_KEY for b in key.encode("utf-8"))
    return _OBFUSCATION_PREFIX + base64.b64encode(xored).decode("ascii")


def deobfuscate_api_key(obfuscated: str) -> str:
    """
    Deobfuscate an API key that was obfuscated with obfuscate_api_key().
    If the key doesn't have the 'enc:' prefix, returns it as-is (plaintext).
    Gracefully handles malformed values instead of crashing startup.
    """
    if not obfuscated or not obfuscated.startswith(_OBFUSCATION_PREFIX):
        return obfuscated or ""
    encoded = obfuscated[len(_OBFUSCATION_PREFIX):]
    try:
        xored = base64.b64decode(encoded, validate=True)
        return bytes(b ^ _XOR_KEY for b in xored).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        logging.warning(f"Failed to deobfuscate stored API key: {e}")
        return ""


class AIProviderSetting(ABC):
    """
    Abstract base class for a provider setting (e.g., API key, model selection).
    """

    def __init__(
        self,
        name: str,
        display_name: Optional[str] = None,
        default_value: Optional[str] = None,
        description: Optional[str] = None,
        is_secret: bool = False,
    ):
        self.name = name
        self.display_name = display_name if display_name else name
        self.default_value = default_value if default_value is not None else ""
        self.description = description if description else ""
        self.is_secret = is_secret

    @abstractmethod
    def render_to_layout(self, layout: QVBoxLayout):
        """Render the setting widget(s) into the provided layout."""
        pass

    @abstractmethod
    def set_value(self, value):
        """Set the internal value from configuration."""
        pass

    @abstractmethod
    def get_value(self):
        """Return the current value from the widget."""
        pass


class TextSetting(AIProviderSetting):
    """
    A text-based setting (for API keys, URLs, etc.).
    Supports masked input with a Show/Hide toggle when `is_secret=True`.
    """

    def __init__(
        self,
        name: str,
        display_name: Optional[str] = None,
        default_value: Optional[str] = None,
        description: Optional[str] = None,
        is_secret: bool = False,
    ):
        super().__init__(name, display_name, default_value, description, is_secret=is_secret)
        self.internal_value = self.default_value
        self.input: Optional[QtWidgets.QLineEdit] = None
        self._toggle_btn: Optional[QtWidgets.QPushButton] = None

    def render_to_layout(self, layout: QVBoxLayout):
        row_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(self.display_name)
        label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        row_layout.addWidget(label)

        self.input = QtWidgets.QLineEdit(self.internal_value or "")
        self.input.setStyleSheet(
            f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
            color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
            border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
        """
        )
        self.input.setPlaceholderText(self.description)
        if self.is_secret:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
        row_layout.addWidget(self.input)

        if self.is_secret:
            self._toggle_btn = QtWidgets.QPushButton("Show")
            self._toggle_btn.setCheckable(True)
            self._toggle_btn.setFixedWidth(60)
            self._toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    font-size: 13px;
                    padding: 5px;
                    background-color: {'#444' if COLOR_MODE == 'dark' else '#f0f0f0'};
                    color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                    border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
                    border-radius: 4px;
                }}
            """
            )
            self._toggle_btn.toggled.connect(self._on_toggle_visibility)
            row_layout.addWidget(self._toggle_btn)

        layout.addLayout(row_layout)

    def _on_toggle_visibility(self, checked: bool):
        if self.input is not None:
            self.input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        if self._toggle_btn is not None:
            self._toggle_btn.setText("Hide" if checked else "Show")

    def set_value(self, value):
        self.internal_value = "" if value is None else str(value)

    def get_value(self):
        if self.input is None:
            return (self.internal_value or "").strip()
        return self.input.text().strip()


class DropdownSetting(AIProviderSetting):
    """
    A dropdown setting (e.g., for selecting a model).
    Optionally supports a "Custom" option that reveals a text input for arbitrary values.
    """

    _CUSTOM_SENTINEL = "__custom__"

    def __init__(
        self,
        name: str,
        display_name: Optional[str] = None,
        default_value: Optional[str] = None,
        description: Optional[str] = None,
        options: Optional[list] = None,
        allow_custom: bool = False,
        custom_placeholder: str = "Enter custom value",
    ):
        super().__init__(name, display_name, default_value, description)
        self.options = options if options else []
        self.internal_value = self.default_value
        self.dropdown: Optional[QtWidgets.QComboBox] = None
        self.allow_custom = allow_custom
        self.custom_placeholder = custom_placeholder
        self.custom_input: Optional[QtWidgets.QLineEdit] = None
        self.custom_input_container: Optional[QtWidgets.QWidget] = None

    def render_to_layout(self, layout: QVBoxLayout):
        row_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(self.display_name)
        label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        row_layout.addWidget(label)

        self.dropdown = QtWidgets.QComboBox()
        self.dropdown.setStyleSheet(
            f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
            color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
            border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
        """
        )

        for option, value in self.options:
            self.dropdown.addItem(option, value)

        if self.allow_custom:
            self.dropdown.addItem("Custom...", self._CUSTOM_SENTINEL)

        index = self.dropdown.findData(self.internal_value)
        if index != -1:
            self.dropdown.setCurrentIndex(index)
        elif self.allow_custom and self.internal_value:
            custom_index = self.dropdown.findData(self._CUSTOM_SENTINEL)
            if custom_index != -1:
                self.dropdown.setCurrentIndex(custom_index)

        row_layout.addWidget(self.dropdown)
        layout.addLayout(row_layout)

        if self.allow_custom:
            self.custom_input_container = QtWidgets.QWidget()
            custom_row_layout = QtWidgets.QHBoxLayout(self.custom_input_container)
            custom_row_layout.setContentsMargins(0, 5, 0, 0)

            self.custom_input = QtWidgets.QLineEdit()
            self.custom_input.setPlaceholderText(self.custom_placeholder)
            self.custom_input.setStyleSheet(
                f"""
                font-size: 16px;
                padding: 5px;
                background-color: {'#444' if COLOR_MODE == 'dark' else 'white'};
                color: {'#ffffff' if COLOR_MODE == 'dark' else '#000000'};
                border: 1px solid {'#666' if COLOR_MODE == 'dark' else '#ccc'};
            """
            )

            if self.dropdown.currentData() == self._CUSTOM_SENTINEL and self.internal_value:
                self.custom_input.setText(self.internal_value)

            custom_row_layout.addWidget(self.custom_input)
            layout.addWidget(self.custom_input_container)

            self.dropdown.currentIndexChanged.connect(self._on_dropdown_changed)
            self._update_custom_input_visibility()

    def _on_dropdown_changed(self):
        self._update_custom_input_visibility()

    def _update_custom_input_visibility(self):
        if self.custom_input_container and self.dropdown:
            is_custom = self.dropdown.currentData() == self._CUSTOM_SENTINEL
            self.custom_input_container.setVisible(is_custom)
            if is_custom and self.custom_input:
                self.custom_input.setFocus()

    def set_value(self, value):
        self.internal_value = self.default_value if value is None else str(value)

    def get_value(self):
        if self.dropdown is None:
            return (self.internal_value or self.default_value or "").strip()
        if self.allow_custom and self.dropdown.currentData() == self._CUSTOM_SENTINEL:
            custom_val = self.custom_input.text().strip() if self.custom_input else ""
            return custom_val or self.default_value
        return self.dropdown.currentData()


class AIProvider(ABC):
    """
    Abstract base class for AI providers backed by Pydantic AI `Model` instances.

    Subclasses construct a `pydantic_ai.models.Model` in `_build_model()` and
    optionally return provider-specific `ModelSettings` from `_build_model_settings()`.
    Request execution, chat history formatting, cancellation, and error dispatch are
    handled uniformly here.
    """

    def __init__(
        self,
        app,
        provider_name: str,
        settings: List[AIProviderSetting],
        description: str = "An unfinished AI provider!",
        logo: str = "generic",
        button_text: str = "Go to URL",
        button_action: Optional[Callable] = None,
    ):
        self.provider_name = provider_name
        self.settings = settings
        self.app = app
        self.description = description if description else "An unfinished AI provider!"
        self.logo = logo
        self.button_text = button_text
        self.button_action = button_action
        self.model: Optional[Model] = None
        self._cancel_event = threading.Event()
        self.close_requested = False

    @staticmethod
    def build_messages(system_instruction: str, prompt: str | list) -> list[ModelMessage]:
        """
        Convert a plain user prompt or an OpenAI-style chat history list into
        Pydantic AI `ModelMessage` objects with `instructions` attached.
        """
        if isinstance(prompt, str):
            return [
                ModelRequest(
                    parts=[UserPromptPart(content=prompt)],
                    instructions=system_instruction or None,
                )
            ]

        messages: list[ModelMessage] = []
        effective_instruction = system_instruction or ""
        for item in prompt:
            role = item.get("role", "user")
            content = str(item.get("content", ""))
            if role == "system":
                if not effective_instruction:
                    effective_instruction = content
                continue
            if role == "assistant":
                messages.append(ModelResponse(parts=[TextPart(content=content)]))
            else:
                messages.append(
                    ModelRequest(
                        parts=[UserPromptPart(content=content)],
                        instructions=effective_instruction or None,
                    )
                )

        if not messages:
            messages.append(
                ModelRequest(
                    parts=[UserPromptPart(content="")],
                    instructions=effective_instruction or None,
                )
            )
        return messages

    @abstractmethod
    def _build_model(self) -> Optional[Model]:
        """Construct and return the configured Pydantic AI `Model`, or None if unconfigured."""
        pass

    def _build_model_settings(self) -> Optional[ModelSettings]:
        """Return provider-specific Pydantic AI `ModelSettings` for each request."""
        return None

    def _missing_config_message(self) -> tuple[str, str]:
        return (
            "Provider Not Configured",
            f"Please configure {self.provider_name} in Settings before using Writing Tools.",
        )

    def _format_error(self, error: Exception) -> tuple[str, str]:
        error_str = str(error)
        lower_err = error_str.lower()
        if any(tok in lower_err for tok in ("429", "resource_exhausted", "rate limit", "exceeded", "quota")):
            return (
                "Rate Limit Hit",
                f"You have hit the {self.provider_name} API rate or quota limit. "
                "Please wait a moment or switch models in Settings.",
            )
        return (
            f"{self.provider_name} Error",
            f"An error occurred while contacting {self.provider_name}:\n{error_str}",
        )

    def get_response(
        self, system_instruction: str, prompt: str | list, return_response: bool = False
    ) -> str:
        """
        Execute a synchronous Pydantic AI model request and either return the text
        (for window/chat mode) or emit it via `output_ready_signal` (for inline replacement).
        """
        self.close_requested = False
        self._cancel_event.clear()

        if self.model is None:
            title, body = self._missing_config_message()
            self.app.show_message_signal.emit(title, body)
            return ""

        try:
            messages = self.build_messages(system_instruction, prompt)
            model_settings = self._build_model_settings()

            response = model_request_sync(
                self.model,
                messages,
                model_settings=model_settings,
            )

            if self._cancel_event.is_set():
                logging.debug(f"{self.provider_name} request was cancelled; discarding response.")
                return ""

            response_text = strip_thinking_tags(response.text or "")

            if not return_response and self.app.current_response_window is None:
                self.app.output_ready_signal.emit(response_text)
                return ""
            return response_text
        except Exception as e:
            if self._cancel_event.is_set():
                return ""
            logging.error(f"Error in {self.provider_name}: {e}")
            title, body = self._format_error(e)
            self.app.show_message_signal.emit(title, body)
            return ""
        finally:
            self.close_requested = False

    def get_setting_display_value(self, setting: AIProviderSetting, stored_value):
        """
        Convert a persisted config value into the plain value suitable for displaying in Settings UI.
        """
        if stored_value is None:
            return setting.default_value
        if setting.is_secret:
            return deobfuscate_api_key(str(stored_value))
        return stored_value

    def load_config(self, config: dict):
        """
        Load configuration settings into the provider, automatically deobfuscating secret settings.
        """
        config = config or {}
        for setting in self.settings:
            raw_val = config.get(setting.name, setting.default_value)
            val = self.get_setting_display_value(setting, raw_val)
            setattr(self, setting.name, val)
            setting.set_value(val)
        self.after_load()

    def save_config(self):
        """
        Save provider configuration settings into the main config file,
        automatically obfuscating secret settings.
        """
        config = {}
        for setting in self.settings:
            value = setting.get_value()
            if setting.is_secret and value:
                value = obfuscate_api_key(value)
            config[setting.name] = value
        self.app.config.setdefault("providers", {})[self.provider_name] = config
        self.app.save_config(self.app.config)

    def after_load(self):
        self.model = self._build_model()

    def before_load(self):
        self.model = None

    def cancel(self):
        """Cancel any ongoing API request."""
        self.close_requested = True
        self._cancel_event.set()


class GeminiProvider(AIProvider):
    """
    Google Gemini provider managed via Pydantic AI (`GoogleModel` + `GoogleProvider`).
    """

    _SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    # Models documented to accept thinking_level="minimal"
    _MINIMAL_THINKING_MODELS = {
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
        "gemini-flash-lite-latest",
    }

    # Model families/aliases that accept thinking_level="low" (where "minimal" is unsupported)
    _LOW_THINKING_PREFIXES = (
        "gemini-4-",
        "gemini-3.8-",
        "gemini-3.7-",
        "gemini-3.5-flash",
        "gemini-3.1-pro",
        "gemini-flash-latest",
        "gemini-pro-latest",
    )

    def __init__(self, app):
        self.api_key = ""
        self.model_name = "gemini-flash-latest"
        self.max_tokens = "8192"

        settings = [
            TextSetting(
                name="api_key",
                display_name="API Key",
                description="Paste your Gemini API key here",
                is_secret=True,
            ),
            DropdownSetting(
                name="model_name",
                display_name="Model",
                default_value="gemini-flash-latest",
                description="Select Gemini model to use",
                options=[
                    ("Gemini Flash Latest (fast | Google-managed alias)", "gemini-flash-latest"),
                    ("Gemini 3.8 Flash (flagship Flash)", "gemini-3.8-flash"),
                    ("Gemini 3.5 Flash-Lite (ultra-fast | lowest cost)", "gemini-3.5-flash-lite"),
                    ("Gemini 4 Hydrogen (fast frontier intelligence)", "gemini-4-hydrogen"),
                    ("Gemini 4 Neon (frontier balanced)", "gemini-4-neon"),
                    ("Gemma 4 31B (slower | unlimited free tier)", "gemma-4-31b-it"),
                    ("Gemma 4 26B A4B (slower | unlimited free tier)", "gemma-4-26b-a4b-it"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., gemini-4-argon, gemini-3.6-flash",
            ),
            TextSetting(
                name="max_tokens",
                display_name="Max Output Tokens",
                default_value="8192",
                description="Maximum response tokens (e.g., 2048, 4096, 8192)",
            ),
        ]
        super().__init__(
            app,
            "Gemini (Recommended)",
            settings,
            "• Google's Gemini provides fast, high-quality AI writing assistance.\n"
            "• An API key from Google AI Studio is required.\n"
            "• Click the button below to get your API key.",
            "gemini",
            "Get API Key",
            lambda: webbrowser.open("https://aistudio.google.com/app/apikey"),
        )

    def _build_thinking_config(self) -> Optional[dict]:
        """
        Choose the lowest-latency Google ThinkingConfig dict supported by the active model.
        Returns None when `google_thinking_config` should be omitted (e.g., Gemma models).
        """
        model = (self.model_name or "").strip().lower()
        if not model or "gemma" in model:
            return None
        if model in self._MINIMAL_THINKING_MODELS:
            return {"thinking_level": "minimal"}
        if model.startswith(self._LOW_THINKING_PREFIXES):
            return {"thinking_level": "low"}
        if model.startswith("gemini-2.5-flash"):
            return {"thinking_budget": 0}
        return None

    def _build_model_settings(self) -> GoogleModelSettings:
        settings: GoogleModelSettings = {
            "max_tokens": parse_max_tokens(self.max_tokens, default=8192),
            "google_safety_settings": self._SAFETY_SETTINGS,
        }
        thinking_cfg = self._build_thinking_config()
        if thinking_cfg is not None:
            settings["google_thinking_config"] = thinking_cfg
        return settings

    def _missing_config_message(self) -> tuple[str, str]:
        return (
            "Gemini API Key Missing",
            "Please configure your Gemini API key in Settings before using Writing Tools.",
        )

    def _build_model(self) -> Optional[Model]:
        key = (self.api_key or "").strip()
        model_name = (self.model_name or "gemini-flash-latest").strip()
        if not key:
            logging.warning("Gemini API key is empty; Pydantic AI GoogleModel not initialized.")
            return None
        try:
            provider = GoogleProvider(api_key=key)
            return GoogleModel(model_name, provider=provider)
        except Exception as e:
            logging.error(f"Failed to initialize Pydantic AI GoogleModel: {e}")
            return None


class OpenAICompatibleProvider(AIProvider):
    """
    OpenAI and OpenAI-compatible provider managed via Pydantic AI
    (`OpenAIChatModel` + `OpenAIProvider`).
    """

    # Reasoning-capable OpenAI families that reject custom `temperature` values
    _NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")

    def __init__(self, app):
        self.api_key = ""
        self.api_base = "https://api.openai.com/v1"
        self.api_organisation = ""
        self.api_project = ""
        self.api_model = "gpt-6-luna"
        self.max_tokens = "8192"

        settings = [
            TextSetting(
                name="api_key",
                display_name="API Key",
                description="API key for the OpenAI-compatible API",
                is_secret=True,
            ),
            TextSetting(
                "api_base",
                "API Base URL",
                "https://api.openai.com/v1",
                "E.g. https://api.openai.com/v1",
            ),
            TextSetting("api_organisation", "API Organisation", "", "Leave blank if not applicable"),
            TextSetting("api_project", "API Project", "", "Leave blank if not applicable"),
            DropdownSetting(
                name="api_model",
                display_name="API Model",
                default_value="gpt-6-luna",
                description="Select or enter an OpenAI-compatible model ID",
                options=[
                    ("GPT-6 Luna (fast & ultra-efficient)", "gpt-6-luna"),
                    ("GPT-5.4 Mini (fast reasoning & coding)", "gpt-5.4-mini"),
                    ("GPT-4.1 Mini (fast non-reasoning)", "gpt-4.1-mini"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., gpt-6-sol, claude-sonnet, deepseek-chat",
            ),
            TextSetting(
                name="max_tokens",
                display_name="Max Output Tokens",
                default_value="8192",
                description="Maximum response tokens (e.g., 2048, 4096, 8192)",
            ),
        ]
        super().__init__(
            app,
            "OpenAI Compatible (For Experts)",
            settings,
            "• Connect to ANY OpenAI-compatible API (v1/chat/completions).\n"
            "• You must abide by the service's Terms of Service.",
            "openai",
            "Get OpenAI API Key",
            lambda: webbrowser.open("https://platform.openai.com/account/api-keys"),
        )

    @staticmethod
    def _normalize_base_url(raw_url: str) -> Optional[str]:
        """
        Clean common OpenAI-compatible base URL mistakes (such as trailing
        `/chat/completions` or Groq's `https://api.groq.com/openai` missing `/v1`).
        """
        url = (raw_url or "").strip().rstrip("/")
        if not url:
            return None
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")].rstrip("/")
        if url.lower() == "https://api.groq.com/openai":
            url = "https://api.groq.com/openai/v1"
        return url

    def _supports_temperature(self) -> bool:
        model = (self.api_model or "").strip().lower()
        return not model.startswith(self._NO_TEMPERATURE_PREFIXES)

    def _build_model_settings(self) -> OpenAIChatModelSettings:
        settings: OpenAIChatModelSettings = {
            "max_tokens": parse_max_tokens(self.max_tokens, default=8192),
        }
        if self._supports_temperature():
            settings["temperature"] = 0.5
        return settings

    def _missing_config_message(self) -> tuple[str, str]:
        return (
            "API Configuration Missing",
            "Please configure your API Key and Base URL in Settings before using Writing Tools.",
        )

    def _build_model(self) -> Optional[Model]:
        key = (self.api_key or "").strip()
        base = self._normalize_base_url(self.api_base)
        org = (self.api_organisation or "").strip() or None
        project = (self.api_project or "").strip() or None
        model_name = (self.api_model or "gpt-6-luna").strip()

        if not key and (base is None or "api.openai.com" in base):
            logging.warning("OpenAI API key is empty; Pydantic AI OpenAIChatModel not initialized.")
            return None

        try:
            # Pass AsyncOpenAI directly when org/project are set so headers are honored
            if org or project:
                client = AsyncOpenAI(
                    api_key=key or "not-required",
                    base_url=base,
                    organization=org,
                    project=project,
                )
                provider = OpenAIProvider(openai_client=client)
            else:
                provider = OpenAIProvider(base_url=base, api_key=key or "not-required")
            return OpenAIChatModel(model_name, provider=provider)
        except Exception as e:
            logging.error(f"Failed to initialize Pydantic AI OpenAIChatModel: {e}")
            return None


class LlamaCppProvider(AIProvider):
    """
    Local/remote llama.cpp server (`llama-server`) provider managed via Pydantic AI
    (`OpenAIChatModel` + `OpenAIProvider`), defaulting to Gemma 4 E2B IT.
    """

    def __init__(self, app):
        self.api_base = "http://127.0.0.1:8080/v1"
        self.api_model = "gemma-4-E2B-it"
        self.api_key = ""
        self.max_tokens = "4096"

        settings = [
            TextSetting(
                "api_base",
                "Server Base URL",
                "http://127.0.0.1:8080/v1",
                "E.g. http://127.0.0.1:8080/v1",
            ),
            DropdownSetting(
                name="api_model",
                display_name="Model",
                default_value="gemma-4-E2B-it",
                description="Select or enter the model served by llama-server",
                options=[
                    ("Gemma 4 E2B IT (recommended | fast ~2B effective)", "gemma-4-E2B-it"),
                    (
                        "Gemma 4 E2B IT GGUF (Hugging Face repo ID)",
                        "ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M",
                    ),
                    ("Gemma 4 E4B IT (higher quality ~4B effective)", "gemma-4-E4B-it"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., gemma-4-E2B-it, ggml-org/gemma-4-E2B-it-GGUF",
            ),
            TextSetting(
                name="max_tokens",
                display_name="Max Output Tokens",
                default_value="4096",
                description="Maximum response tokens (e.g., 2048, 4096, 8192)",
            ),
            TextSetting(
                name="api_key",
                display_name="API Key (Optional)",
                default_value="",
                description="Leave blank unless llama-server --api-key is set",
                is_secret=True,
            ),
        ]
        super().__init__(
            app,
            "llama.cpp (Local LLM)",
            settings,
            "• Connect to a local llama.cpp server (llama-server) running Gemma 4 E2B or any GGUF model.\n"
            "• Quick start: llama-server -hf ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M --port 8080",
            "llamacpp",
            "llama.cpp Set-up Guide",
            lambda: webbrowser.open("https://github.com/ggml-org/llama.cpp"),
        )

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        """
        Ensure llama-server's OpenAI-compatible `/v1` suffix is present so both
        `http://127.0.0.1:8080` and `http://127.0.0.1:8080/v1` work seamlessly.
        """
        url = (raw_url or "http://127.0.0.1:8080/v1").strip().rstrip("/")
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        return url

    def _build_model_settings(self) -> OpenAIChatModelSettings:
        return OpenAIChatModelSettings(
            temperature=0.5,
            max_tokens=parse_max_tokens(self.max_tokens, default=4096),
        )

    def _missing_config_message(self) -> tuple[str, str]:
        return (
            "llama.cpp Not Configured",
            "Please configure your llama-server Base URL and Model in Settings, "
            "and ensure llama-server is running.",
        )

    def _build_model(self) -> Optional[Model]:
        base_url = self._normalize_base_url(self.api_base)
        model_name = (self.api_model or "gemma-4-E2B-it").strip()
        key = (self.api_key or "").strip() or "no-key-required"
        try:
            provider = OpenAIProvider(base_url=base_url, api_key=key)
            return OpenAIChatModel(model_name, provider=provider)
        except Exception as e:
            logging.error(f"Failed to initialize Pydantic AI llama.cpp model: {e}")
            return None
