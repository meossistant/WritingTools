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


def main() -> None:
    """Main entry point of the application."""
    _configure_logging()
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
