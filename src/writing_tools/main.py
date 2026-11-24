import logging
import os
import sys
import tempfile

from PySide6 import QtCore

from writing_tools.app import WritingToolApp


def _configure_logging() -> None:
    """
    Configure application logging.
    Defaults to WARNING to protect user privacy; override via WRITING_TOOLS_LOG_LEVEL
    (or legacy WRITINGTOOLS_LOG_LEVEL).
    """
    level_name = (
        os.environ.get("WRITING_TOOLS_LOG_LEVEL")
        or os.environ.get("WRITINGTOOLS_LOG_LEVEL")
        or "WARNING"
    ).upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def acquire_single_instance_lock(lock_path: str | None = None) -> QtCore.QLockFile | None:
    """
    Enforce a single running instance of Writing Tools using a cross-platform
    Qt `QLockFile`. Returns the acquired lock object or None if another instance
    already holds the lock.
    """
    target = lock_path or os.path.join(tempfile.gettempdir(), "writing-tools.lock")
    lock_file = QtCore.QLockFile(target)
    lock_file.setStaleLockTime(0)
    if not lock_file.tryLock(100):
        return None
    return lock_file


def run_smoke_test() -> int:
    """
    Verify that all runtime imports, Pydantic AI model classes, and bundled
    resources load cleanly (used by CI to validate frozen PyInstaller builds).
    """
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
    from pydantic_ai.providers.google import GoogleProvider
    from pydantic_ai.providers.openai import OpenAIProvider

    from writing_tools import diff_utils, hotkey_listener, secrets, window_context  # noqa: F401
    from writing_tools.paths import get_resource_path

    # Instantiate provider/model wrappers without making network requests
    GoogleModel("gemini-flash-latest", provider=GoogleProvider(api_key="smoke-test"))
    OpenAIChatModel("gpt-6-luna", provider=OpenAIProvider(api_key="smoke-test"))
    OpenAIResponsesModel("gpt-6-luna", provider=OpenAIProvider(api_key="smoke-test"))

    required_resources = [
        ("options.json",),
        ("icons", "app_icon.png"),
        ("backgrounds", "background_dark.png"),
    ]
    for parts in required_resources:
        res_path = get_resource_path(*parts)
        if not os.path.exists(res_path):
            raise FileNotFoundError(f"Missing bundled resource: {res_path}")

    print("Writing Tools smoke test passed.")
    return 0


def main() -> None:
    """Main entry point of the application."""
    _configure_logging()
    if "--smoke-test" in sys.argv[1:]:
        sys.exit(run_smoke_test())

    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        logging.warning("Another instance of Writing Tools is already running; exiting.")
        sys.exit(0)

    try:
        app = WritingToolApp(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        sys.exit(app.exec())
    finally:
        instance_lock.unlock()


if __name__ == "__main__":
    main()
