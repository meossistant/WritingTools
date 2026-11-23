import logging
import os
import sys

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


def main() -> None:
    """Main entry point of the application."""
    _configure_logging()
    app = WritingToolApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
