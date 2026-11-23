import logging
import os
import shlex
import sys

if sys.platform.startswith("win32"):
    import winreg


class AutostartManager:
    """
    Manages autostart functionality for Writing Tools on Windows (Registry Run key)
    and Linux (XDG autostart .desktop entry).
    """

    _WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _LINUX_DESKTOP_FILENAME = "writing-tools.desktop"

    @staticmethod
    def is_compiled() -> bool:
        """Check if running from a PyInstaller compiled binary."""
        return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))

    @staticmethod
    def _get_linux_desktop_path() -> str:
        xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(xdg_config, "autostart", AutostartManager._LINUX_DESKTOP_FILENAME)

    @staticmethod
    def get_startup_path():
        """
        Get the executable/command path used for autostart.
        Returns None if unsupported on the current platform/environment.
        """
        if sys.platform.startswith("win32"):
            if not AutostartManager.is_compiled():
                return None
            return sys.executable

        if sys.platform.startswith("linux"):
            if AutostartManager.is_compiled():
                return sys.executable
            return f"{shlex.quote(sys.executable)} -m writing_tools"

        return None

    @staticmethod
    def set_autostart(enable: bool) -> bool:
        """Enable or disable autostart for Writing Tools."""
        try:
            startup_path = AutostartManager.get_startup_path()
            if not startup_path:
                return False

            if sys.platform.startswith("win32"):
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        AutostartManager._WIN_RUN_KEY,
                        0,
                        winreg.KEY_WRITE,
                    ) as key:
                        if enable:
                            winreg.SetValueEx(key, "WritingTools", 0, winreg.REG_SZ, startup_path)
                        else:
                            try:
                                winreg.DeleteValue(key, "WritingTools")
                            except FileNotFoundError:
                                pass
                    return True
                except OSError as e:
                    logging.error(f"Failed to modify autostart registry: {e}")
                    return False

            if sys.platform.startswith("linux"):
                desktop_path = AutostartManager._get_linux_desktop_path()
                if enable:
                    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
                    content = (
                        "[Desktop Entry]\n"
                        "Type=Application\n"
                        "Name=Writing Tools\n"
                        "Comment=System-wide AI writing assistant\n"
                        f"Exec={startup_path}\n"
                        "Terminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
                    with open(desktop_path, "w", encoding="utf-8") as f:
                        f.write(content)
                else:
                    if os.path.exists(desktop_path):
                        os.remove(desktop_path)
                return True

            return False
        except Exception as e:
            logging.error(f"Error managing autostart: {e}")
            return False

    @staticmethod
    def check_autostart() -> bool:
        """Check whether Writing Tools is currently configured to start automatically."""
        try:
            startup_path = AutostartManager.get_startup_path()
            if not startup_path:
                return False

            if sys.platform.startswith("win32"):
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        AutostartManager._WIN_RUN_KEY,
                        0,
                        winreg.KEY_READ,
                    ) as key:
                        value, _ = winreg.QueryValueEx(key, "WritingTools")
                    return value.lower() == startup_path.lower()
                except OSError:
                    return False

            if sys.platform.startswith("linux"):
                desktop_path = AutostartManager._get_linux_desktop_path()
                if not os.path.exists(desktop_path):
                    return False
                with open(desktop_path, "r", encoding="utf-8") as f:
                    return f"Exec={startup_path}" in f.read()

            return False
        except Exception as e:
            logging.error(f"Error checking autostart status: {e}")
            return False
