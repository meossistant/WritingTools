import os
import shutil
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(ROOT_DIR, "src", "writing_tools", "resources")
ENTRY_SCRIPT = os.path.join(ROOT_DIR, "src", "writing_tools", "main.py")


def _add_data_arg(src: str, dest: str) -> str:
    return f"{src}{os.pathsep}{dest}"


def run_pyinstaller_build() -> None:
    is_windows = sys.platform.startswith("win32")
    icon_file = os.path.join(
        RESOURCES_DIR, "icons", "app_icon.ico" if is_windows else "app_icon.png"
    )

    pyinstaller_command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        f"--icon={icon_file}",
        "--name=Writing Tools",
        "--clean",
        "--noconfirm",
        "--paths", os.path.join(ROOT_DIR, "src"),
        # Bundle runtime resources inside writing_tools/resources
        "--add-data", _add_data_arg(RESOURCES_DIR, os.path.join("writing_tools", "resources")),
        "--collect-submodules", "writing_tools",
        # Ensure dynamic tokenizer encodings, platform backends, and CA certs are bundled in frozen builds
        "--hidden-import", "tiktoken_ext.openai_public",
        "--hidden-import", "tiktoken_ext",
        "--collect-data", "certifi",
        *(
            [
                "--hidden-import", "pynput.keyboard._win32",
                "--hidden-import", "pynput.mouse._win32",
                "--hidden-import", "pynput._util.win32",
                "--hidden-import", "darkdetect._windows_detect",
            ]
            if is_windows
            else [
                "--hidden-import", "pynput.keyboard._xorg",
                "--hidden-import", "pynput.mouse._xorg",
                "--hidden-import", "pynput._util.xorg",
                "--hidden-import", "darkdetect._linux_detect",
                "--collect-submodules", "Xlib",
            ]
        ),
        # Exclude unnecessary modules
        # NOTE: do NOT exclude `unittest` — `logfire_api` (via `pydantic_graph` / `pydantic_ai`) imports it.
        # NOTE: do NOT exclude `cryptography` — google-genai / pydantic-ai auth pulls it in.
        "--exclude-module", "tkinter",
        "--exclude-module", "IPython",
        "--exclude-module", "jedi",
        "--exclude-module", "email_validator",
        "--exclude-module", "psutil",
        "--exclude-module", "pyzmq",
        "--exclude-module", "tornado",
        # Exclude unused PySide6 modules
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtXml",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtQuickWidgets",
        "--exclude-module", "PySide6.QtPrintSupport",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.QtSvg",
        "--exclude-module", "PySide6.QtSvgWidgets",
        "--exclude-module", "PySide6.QtHelp",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtMultimediaWidgets",
        "--exclude-module", "PySide6.QtOpenGL",
        "--exclude-module", "PySide6.QtOpenGLWidgets",
        "--exclude-module", "PySide6.QtPositioning",
        "--exclude-module", "PySide6.QtLocation",
        "--exclude-module", "PySide6.QtSerialPort",
        "--exclude-module", "PySide6.QtWebChannel",
        "--exclude-module", "PySide6.QtWebSockets",
        "--exclude-module", "PySide6.QtNetworkAuth",
        "--exclude-module", "PySide6.QtRemoteObjects",
        "--exclude-module", "PySide6.QtTextToSpeech",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtWebEngine",
        "--exclude-module", "PySide6.QtBluetooth",
        "--exclude-module", "PySide6.QtNfc",
        "--exclude-module", "PySide6.QtWebView",
        "--exclude-module", "PySide6.QtCharts",
        "--exclude-module", "PySide6.QtDataVisualization",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtPdfWidgets",
        "--exclude-module", "PySide6.QtQuick3D",
        "--exclude-module", "PySide6.QtQuickControls2",
        "--exclude-module", "PySide6.QtQuickParticles",
        "--exclude-module", "PySide6.QtQuickTest",
        "--exclude-module", "PySide6.QtSensors",
        "--exclude-module", "PySide6.QtStateMachine",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.Qt3DRender",
        "--exclude-module", "PySide6.Qt3DInput",
        "--exclude-module", "PySide6.Qt3DLogic",
        "--exclude-module", "PySide6.Qt3DAnimation",
        "--exclude-module", "PySide6.Qt3DExtras",
        ENTRY_SCRIPT,
    ]

    try:
        for directory in ("dist", "build"):
            target = os.path.join(ROOT_DIR, directory)
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)

        subprocess.run(pyinstaller_command, cwd=ROOT_DIR, check=True)
        print("Build completed successfully!")

        build_dir = os.path.join(ROOT_DIR, "build")
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir, ignore_errors=True)

    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_pyinstaller_build()
