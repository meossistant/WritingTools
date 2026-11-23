import webbrowser

from PySide6 import QtCore, QtGui, QtWidgets

from writing_tools.ui.ui_utils import COLOR_MODE, UIUtils
from writing_tools.update_checker import CURRENT_VERSION_STRING

_ = lambda x: x


class AboutWindow(QtWidgets.QWidget):
    """
    The about window for the application.
    """

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(" ")
        self.setGeometry(300, 300, 650, 720)

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        UIUtils.setup_window_and_layout(self)

        self.setWindowFlags(
            (
                self.windowFlags()
                & ~QtCore.Qt.WindowType.WindowMinimizeButtonHint
                & ~QtCore.Qt.WindowType.WindowSystemMenuHint
            )
            | QtCore.Qt.WindowType.WindowCloseButtonHint
            | QtCore.Qt.WindowType.WindowTitleHint
        )

        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        self.setWindowIcon(QtGui.QIcon(pixmap))

        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        title_label = QtWidgets.QLabel(_("About Writing Tools"))
        title_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        content_layout.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        about_text = (
            "<p style='text-align: center;'>"
            + _(
                "Writing Tools is a free & lightweight tool that helps you improve your writing with AI, similar to Apple's Apple Intelligence feature. It works with an extensive range of AI LLMs, both online and locally run."
            )
            + "<br></p>"
            + "<p style='text-align: center;'>"
            + "<b>"
            + _("Created with care by Jesai, a high school student.")
            + "</b><br><br>"
            + _("Feel free to check out my other AI app")
            + ', <a href="https://play.google.com/store/apps/details?id=com.jesai.blissai"><b>Bliss AI</b></a>. '
            + _("It's a novel AI tutor that's free on the Google Play Store :)")
            + "<br><br>"
            + "<b>"
            + _("Contact me")
            + ":</b> jesaitarun@gmail.com<br><br>"
            + "</p>"
            + "<p style='text-align: center;'>"
            + "<b>"
            + _("Writing Tools would not be where it is today without its <u>amazing</u> contributors")
            + ":</b><br>"
            + '<b>1. <a href="https://github.com/momokrono">momokrono</a>:</b><br>'
            + _(
                "Added Linux support, switched to the pynput API to improve Windows stability. Added Ollama API support, core logic for customizable buttons, and localization. Fixed misc. bugs and added graceful termination support by handling SIGINT signal."
            )
            + "<br>"
            + '<b>2. <a href="https://github.com/CameronRedmore">Cameron Redmore (CameronRedmore)</a>:</b><br>'
            + _(
                "Extensively refactored Writing Tools and added OpenAI Compatible API support, streamed responses, and the text generation mode when no text is selected."
            )
            + "<br>"
            + '<b>3. <a href="https://github.com/Soszust40">Soszust40 (Soszust40)</a>:</b><br>'
            + _("Helped add dark mode, the plain theme, tray menu fixes, and UI improvements.")
            + "<br>"
            + '<b>4. <a href="https://github.com/arsaboo">Alok Saboo (arsaboo)</a>:</b><br>'
            + _("Helped improve the reliability of text selection.")
            + "<br>"
            + '<b>5. <a href="https://github.com/raghavdhingra24">raghavdhingra24</a>:</b><br>'
            + _("Made the rounded corners anti-aliased & prettier.")
            + "<br>"
            + '<b>6. <a href="https://github.com/ErrorCatDev">ErrorCatDev</a>:</b><br>'
            + _(
                "Significantly improved the About window, making it scrollable and cleaning things up. Also improved our .gitignore & requirements.txt."
            )
            + "<br>"
            + '<b>7. <a href="https://github.com/Vadim-Karpenko">Vadim Karpenko</a>:</b><br>'
            + _("Helped add the start-on-boot setting.")
            + "</p>"
            + f"<p style='text-align: center;'><b>Version:</b> {CURRENT_VERSION_STRING}</p>"
        )

        about_label = QtWidgets.QLabel(about_text)
        about_label.setStyleSheet(
            f"font-size: 16px; color: {'#ffffff' if COLOR_MODE == 'dark' else '#333333'};"
        )
        about_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        about_label.setWordWrap(True)
        about_label.setOpenExternalLinks(True)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(about_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background: transparent;")

        content_layout.addWidget(scroll_area)

        update_button = QtWidgets.QPushButton(_("Check for updates"))
        update_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                font-size: 16px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        update_button.clicked.connect(self.check_for_updates)
        content_layout.addWidget(update_button)

    def check_for_updates(self):
        webbrowser.open("https://github.com/theJayTea/WritingTools/releases")
