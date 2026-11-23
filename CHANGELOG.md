# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

Baseline comparison against upstream [`theJayTea/WritingTools@0839d8c`](https://github.com/theJayTea/WritingTools/commit/0839d8c) (`Win_v9`).

### Added
- **`uv` Package Management**: Added `pyproject.toml` (PEP 621 with `hatchling` build backend), `.python-version` (`3.12`), and deterministic `uv.lock`, with separated `dev` (`pytest`) and `build` (`pyinstaller`) dependency groups and `writing-tools` CLI entry point.
- **Pydantic AI Provider Architecture**: Unified all AI providers under `pydantic-ai-slim[google,openai]>=2.71.0` using `pydantic_ai.direct.model_request_sync`, `ModelRequest`/`ModelResponse`, and typed `ModelSettings`.
- **`llama.cpp` Local LLM Provider (`LlamaCppProvider`)**: Added native `llama-server` support backed by Pydantic AI (`OpenAIChatModel` + `OpenAIProvider`), defaulting to **Gemma 4 E2B IT** (`gemma-4-E2B-it`, with `ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M` and `gemma-4-E4B-it` presets), automatic `/v1` base URL normalization, and optional secret API key support.
- **Configurable Max Output Tokens**: Added `Max Output Tokens` setting across Gemini, OpenAI Compatible, and `llama.cpp` providers (resolves `theJayTea/WritingTools#220`).
- **Single-Instance Enforcement**: Added cross-platform Qt `QLockFile` guard in `main.py` so duplicate background instances exit cleanly (resolves `theJayTea/WritingTools#233`).
- **System Tray Click-to-Open**: Left-clicking the system tray icon now opens the Writing Tools popup (resolves `theJayTea/WritingTools#83`).
- **Linux XDG Autostart**: Added `~/.config/autostart/writing-tools.desktop` support in `AutostartManager` alongside Windows Registry autostart.
- **Resource & Data Path Abstraction**: Added `src/writing_tools/paths.py` (`get_data_dir()`, `get_resource_path()`) supporting source checkouts, installed wheels, and PyInstaller `_MEIPASS` bundles (resolves `theJayTea/WritingTools#150`).
- **Secret Input Masking**: Added masked password mode with Show/Hide toggle for API key fields across all providers (resolves `theJayTea/WritingTools#251`).
- **Live Button & Hotkey Reload**: Adding, editing, deleting, reordering, or resetting popup buttons now reloads options and hotkeys live without forcing the application to quit.
- **GitHub Actions CI & Release Builds**: Added `.github/workflows/ci.yml` (cross-platform lint/compile/pytest on `ubuntu-latest` and `windows-latest`) and `.github/workflows/build.yml` (PyInstaller builds for Windows `.zip` and Linux `.tar.gz`, with automatic GitHub Release upload on `v*` tags).
- **Automated Test Suite**: Added `tests/test_writing_tools.py` (18 headless Qt + Pydantic AI tests covering providers, upstream bug regressions, config migration, UI widgets, zoom persistence, single-instance locking, and autostart).

### Changed
- **Repository Structure & Naming Conventions**:
  - Flattened `Windows_and_Linux/` into standard `src/writing_tools/` Python package layout at the repository root.
  - Renamed all Python modules and scripts to PEP 8 `snake_case` (`app.py`, `ai_provider.py`, `autostart.py`, `paths.py`, `ui/about_window.py`, `ui/custom_popup_window.py`, `ui/onboarding_window.py`, `ui/response_window.py`, `ui/settings_window.py`, `ui/ui_utils.py`, `scripts/build_pyinstaller.py`, `scripts/update_translations.sh`).
  - Standardized internal constants (`colorMode` -> `COLOR_MODE`) and resource filenames (`src/writing_tools/resources/{backgrounds,icons,locales}`, `magnifying_glass_*`, `rotate_left_*`, `smiley_face_*`, `provider_llamacpp.png`).
  - Renamed documentation and version files to kebab-case (`docs/running-from-source.md`, `docs/building.md`, `docs/media-coverage.md`, `docs/media/demo*.mp4`, `version.txt`).
- **Updated Default & Preset Models** (resolves `theJayTea/WritingTools#289`, `#153`):
  - **Gemini**: Updated presets to `gemini-flash-latest` (default), `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-4-hydrogen`, `gemini-4-neon`, `gemma-4-31b-it`, and `gemma-4-26b-a4b-it`, with `max_tokens=8192` default and automatic migration from retired Gemini 2.0 / Gemma 3 presets.
  - **OpenAI Compatible**: Replaced retiring `gpt-4o-mini` with a dropdown + custom field defaulting to `gpt-6-luna` (presets: `gpt-6-luna`, `gpt-5.4-mini`, `gpt-4.1-mini`).
  - **Local LLM**: Replaced Ollama (`llama3.1:8b`) with `llama.cpp` defaulting to `gemma-4-E2B-it` (with automatic migration for existing Ollama configs).
- **Updated Dependencies**: Bumped minimum versions to `PySide6>=6.12.0`, `pydantic-ai-slim[google,openai]>=2.71.0`, `markdown2>=2.5.5`, `pynput>=1.8.2`, `pyperclip>=1.11.0`, `darkdetect>=0.8.0`, `pyinstaller>=6.22.3`, and `pytest>=9.0.0`.
- **Privacy-Safe Default Logging**: Changed default log level in `main.py` from `DEBUG` to `WARNING` (overridable via `WRITING_TOOLS_LOG_LEVEL`) and stopped logging raw follow-up questions.
- **Version Alignment**: Unified application version to `9.0` (`CURRENT_VERSION = 9`) across `update_checker.py`, `about_window.py`, `pyproject.toml`, and `version.txt` (resolves `theJayTea/WritingTools#268`, `#270`).

### Fixed
- **Linux X11 Clipboard Deadlock**: Switched GUI-thread clipboard backup/clear calls from `pyperclip.paste()` (`xclip -o`) to Qt's `QClipboard`, eliminating permanent freezes when pressing a hotkey after copying from `ResponseWindow` (resolves `theJayTea/WritingTools#288`).
- **Non-Latin Keyboard Layout Copy/Paste on Windows**: Switched simulated `Ctrl+C`/`Ctrl+V` on Windows to virtual key codes (`0x43` / `0x56`) so selection capture and paste work regardless of active keyboard layout (resolves `theJayTea/WritingTools#270`, `#275`).
- **Held Modifier Interference on Hotkey Trigger**: Released interfering `Alt`/`Win`/`Shift` modifiers before injecting `Ctrl+C`/`Ctrl+V` via `kbrd.pressed(Key.ctrl)`, preventing spurious `₢` character insertion, Windows color filter inversion (`Ctrl+Win+C`), or replacing selected text with `c` (resolves `theJayTea/WritingTools#195`, `#185`, `#183`).
- **Copy as Markdown in Follow-Up Conversations**: Updated `ResponseWindow` "Copy as Markdown" button to copy the latest assistant response instead of always copying the first response (resolves `theJayTea/WritingTools#249`, `#170`).
- **Reasoning Model `<think>` Block Leakage**: Added `strip_thinking_tags()` to remove `<think>...</think>` chain-of-thought blocks emitted by DeepSeek R1 / QwQ / Qwen3 models before pasting or displaying (resolves `theJayTea/WritingTools#109`).
- **OpenAI-Compatible Base URL Cleanup**: Stripped accidental trailing `/chat/completions` paths and slashes from custom OpenAI-compatible `base_url` entries while keeping dependencies lean on `pydantic-ai-slim[google,openai]`.
- **Popup Taskbar Flash**: Added `Qt.WindowType.Tool` flag to `CustomPopupWindow` so the floating popup does not create a taskbar entry (resolves `theJayTea/WritingTools#142`).
- **Data Loss & Double-Call on Provider Responses**: Removed invalid worker-thread `replace_text(True)` call in `GeminiProvider` and routed all provider errors to `show_message_signal` instead of `output_ready_signal`, preventing error text from overwriting selected text in the user's editor.
- **Gemini `ThinkingConfig` Compatibility**: Replaced unconditional `thinking_level="minimal"` with model-aware configuration (`minimal` only on models supporting it, `low` on Gemini 4 / 3.8 Flash / Pro / `gemini-flash-latest`, `thinking_budget=0` on 2.5 Flash, omitted on Gemma 4), preventing HTTP 400 errors and response truncation (resolves `theJayTea/WritingTools#282`, `#189`).
- **PySide6 6.12 Compatibility**: Replaced all 8 removed `.exec_()` calls (`QDrag`, `QMessageBox`, `QDialog`) with `.exec()` and migrated legacy unscoped Qt enums to scoped Qt6 enums.
- **ResponseWindow Parent Lookup, Zoom Persistence & Leaks**: Fixed `ChatContentScrollArea` walking up past `ThemeBackground` to locate `ResponseWindow`, fixed `dict`-based `response_window_zoom` restoration (`"response_window_zoom" in config` instead of `hasattr`), removed duplicate user message appends in follow-up chat history, eliminated global signal leaks across closed windows, and enabled Markdown `fenced-code-blocks`.
- **SettingsWindow API Key Corruption & Migration Loop**: Deobfuscated stored API keys before rendering inputs (fixing raw `enc:...` display), obfuscated OpenAI-compatible & `llama.cpp` API keys on save, preserved user `locale`, removed duplicate `scroll_content` widget creation, and stamped all migration flags up to v9.
- **OpenAI Reasoning Model & Header Compatibility**: Omitted `temperature` on reasoning families (`o1`/`o3`/`o4`/`gpt-5`/`gpt-6`), converted empty organization/project strings to `None`, and added null-safe response content extraction.
- **Provider Cancellation & Concurrency**: Enforced `threading.Event` cancellation so cancelled slow requests discard stale output; added generation-guarded clipboard backup/restore, atomic lock-protected UTF-8 `config.json` writes, and queued `QTimer.singleShot` POSIX `SIGINT` shutdown.
- **CustomPopupWindow & Options Robustness**: Fixed `UnboundLocalError` when `options.json` is missing, preserved built-in button icons/prefixes when editing, validated empty/reserved (`Custom`) button names, and cleaned literal `\'` escape artifacts in default prompts.
- **UIUtils & Build Script Fixes**: Fixed `UIUtils.clear_layout()` crash on `QSpacerItem`, cached `ThemeBackground` pixmaps instead of reloading from disk every paint event, replaced Windows-only `WindowsError` with `OSError`, and fixed `scripts/build_pyinstaller.py` to use cross-platform `shutil.rmtree` and bundle `writing_tools/resources` via `--add-data`.

### Removed
- **macOS Native Swift Port**: Stripped the `macOS/` directory (115 files, ~9.0 MB) along with macOS/Xcode references in `README.md`, `docs/building.md`, `about_window.py`, and `.gitignore`.
- **Legacy Packaging & Ollama Provider**: Removed `Windows_and_Linux/requirements.txt`, tracked `pot_files/`, `OllamaProvider`, and the standalone `ollama` SDK dependency.
