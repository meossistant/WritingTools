import os
import sys

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_PACKAGE_DIR))


def get_data_dir() -> str:
    """
    Return the writable directory for user config and options files.
    - When frozen with PyInstaller: directory alongside the executable.
    - When running from a source checkout: the repository root directory.
    - When installed into site-packages: platform user config directory.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    if os.path.exists(os.path.join(_PROJECT_ROOT, "pyproject.toml")):
        return _PROJECT_ROOT
    if sys.platform.startswith("win32"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    data_dir = os.path.join(base, "writing-tools")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_resource_path(*parts: str) -> str:
    """
    Resolve a read-only bundled resource path inside `writing_tools/resources/`.
    Checks PyInstaller's `_MEIPASS` bundle directory first when frozen.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "writing_tools", "resources", *parts)
        if os.path.exists(bundled):
            return bundled
    return os.path.join(_PACKAGE_DIR, "resources", *parts)
