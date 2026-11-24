import logging
import os
import sys
import tempfile
import traceback

from PySide6 import QtCore


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


def _parse_smoke_log_path(argv: list[str]) -> str | None:
    for arg in argv:
        if arg.startswith("--smoke-test-log="):
            return arg.split("=", 1)[1].strip() or None
    return None


def _write_smoke_log(log_path: str | None, text: str) -> None:
    if not log_path:
        return
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def run_smoke_test(log_path: str | None = None) -> int:
    """
    Verify that all runtime imports, Pydantic AI model classes, and bundled
    resources load cleanly (used by CI to validate frozen PyInstaller builds).
    Catches all exceptions so Windows `--windowed` builds never block on a modal
    exception dialog during automated CI verification.
    """
    try:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
        from pydantic_ai.providers.google import GoogleProvider
        from pydantic_ai.providers.openai import OpenAIProvider

        from writing_tools import (  # noqa: F401
            app as app_module,
            diff_utils,
            hotkey_listener,
            secrets,
            window_context,
        )
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

        msg = "Writing Tools smoke test passed.\n"
        _write_smoke_log(log_path, msg)
        print(msg, end="")
        return 0
    except BaseException:
        tb = traceback.format_exc()
        _write_smoke_log(log_path, tb)
        sys.stderr.write(tb)
        return 1


def main() -> None:
    """Main entry point of the application."""
    _configure_logging()
    if "--smoke-test" in sys.argv[1:]:
        log_path = _parse_smoke_log_path(sys.argv[1:])
        sys.exit(run_smoke_test(log_path=log_path))

    from writing_tools.app import WritingToolApp

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
