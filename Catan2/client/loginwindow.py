from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QHBoxLayout,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QSize
from Catan2.client.Client import Client
from Catan2.client.verification_dialog import VerificationDialog
import re
import traceback
from PyQt5.QtWidgets import QDialog


class LoginWindow(QWidget):
    def __init__(self):
        try:
            super().__init__()
            self.client = Client()
            self.going_to_lobby = False
            self._animations = []
            self.init_ui()
        except Exception as e:
            self._fatal_error("Initialization failed", e)

    # --------------------------------------------------
    # UI SETUP
    # --------------------------------------------------

    def init_ui(self):
        try:
            # Fade in
            self.setWindowOpacity(0)
            fade = QPropertyAnimation(self, b"windowOpacity")
            fade.setDuration(500)
            fade.setStartValue(0)
            fade.setEndValue(1)
            fade.start()
            self._animations.append(fade)

            self.setWindowTitle("Catan")
            self.setFixedSize(420, 420)
            self.setStyleSheet("background-color: #1E272E;")

            main_layout = QVBoxLayout(self)
            main_layout.setAlignment(Qt.AlignCenter)

            # -------- Card --------
            card = QWidget()
            card.setFixedSize(340, 340)
            card.setStyleSheet("""
                QWidget {
                    background-color: #2C3E50;
                    border-radius: 18px;
                }
            """)

            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(30)
            shadow.setOffset(0, 6)
            shadow.setColor(QColor(0, 0, 0, 150))
            card.setGraphicsEffect(shadow)

            layout = QVBoxLayout(card)
            layout.setContentsMargins(28, 28, 28, 28)
            layout.setSpacing(18)

            # -------- Title --------
            title = QLabel("Welcome Back")
            title.setAlignment(Qt.AlignCenter)
            title.setFont(QFont("Segoe UI", 22, QFont.Bold))
            title.setStyleSheet("color: #ECF0F1;")

            subtitle = QLabel("Log in to your Catan account")
            subtitle.setAlignment(Qt.AlignCenter)
            subtitle.setFont(QFont("Segoe UI", 10))
            subtitle.setStyleSheet("color: #95A5A6;")

            # -------- Inputs --------
            self.username_input = self._styled_input("Username")
            self.password_input = self._styled_input("Password", password=True)

            # Caps lock warning
            self.caps_label = QLabel("Caps Lock is ON")
            self.caps_label.setStyleSheet("color: #F39C12; font-size: 9px;")
            self.caps_label.hide()

            self.password_input.field.textChanged.connect(self._check_caps_lock)

            # -------- Buttons --------
            self.login_btn = QPushButton("Login")
            self.login_btn.setCursor(Qt.PointingHandCursor)
            self.login_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.login_btn.setFixedHeight(42)
            self.login_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1ABC9C;
                    color: white;
                    border-radius: 12px;
                }
                QPushButton:hover { background-color: #16A085; }
                QPushButton:pressed { background-color: #12876F; }
            """)

            self.signup_btn = QPushButton("Create account")
            self.signup_btn.setCursor(Qt.PointingHandCursor)
            self.signup_btn.setFont(QFont("Segoe UI", 10))
            self.signup_btn.setStyleSheet("""
                QPushButton {
                    color: #3498DB;
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    color: #5DADE2;
                    text-decoration: underline;
                }
            """)

            self.loading_label = QLabel("Logging in...")
            self.loading_label.setAlignment(Qt.AlignCenter)
            self.loading_label.setStyleSheet("color: #95A5A6;")
            self.loading_label.hide()

            # -------- Assemble --------
            layout.addWidget(title)
            layout.addWidget(subtitle)
            layout.addSpacing(8)
            layout.addWidget(self.username_input)
            layout.addWidget(self.password_input)
            layout.addWidget(self.caps_label)
            layout.addSpacing(6)
            layout.addWidget(self.login_btn)
            layout.addWidget(self.signup_btn)
            layout.addWidget(self.loading_label)

            main_layout.addWidget(card)

            # -------- Signals --------
            self.login_btn.clicked.connect(self.login)
            self.signup_btn.clicked.connect(self.signup)
            self.username_input.field.returnPressed.connect(self.login)
            self.password_input.field.returnPressed.connect(self.login)

        except Exception as e:
            self._fatal_error("UI setup failed", e)

    # --------------------------------------------------
    # INPUT BUILDER
    # --------------------------------------------------

    def _styled_input(self, placeholder, password=False):
        container = QWidget()
        container.setFixedHeight(44)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 12, 0)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFont(QFont("Segoe UI", 11))
        field.setStyleSheet("border:none; background:transparent; color:#ECF0F1;")

        if password:
            field.setEchoMode(QLineEdit.Password)
            eye = QPushButton()
            eye.setIcon(QIcon("images/login/eye-off.png"))
            eye.setIconSize(QSize(22, 22))
            eye.setFixedSize(36, 36)
            eye.setFlat(True)
            eye.setFocusPolicy(Qt.NoFocus)  # 🔑 prevents Enter stealing
            eye.setCursor(Qt.PointingHandCursor)

            def toggle():
                if field.echoMode() == QLineEdit.Password:
                    field.setEchoMode(QLineEdit.Normal)
                    eye.setIcon(QIcon("images/login/eye.png"))
                else:
                    field.setEchoMode(QLineEdit.Password)
                    eye.setIcon(QIcon("images/login/eye-off.png"))

            eye.clicked.connect(toggle)
            layout.addWidget(field)
            layout.addWidget(eye)
        else:
            layout.addWidget(field)

        container.setStyleSheet("""
            QWidget {
                border-radius: 12px;
                border: 2px solid #34495E;
                background-color: #34495E;
            }
            QWidget:hover {
                border: 2px solid #5DADE2;
            }
            QWidget:focus-within {
                border: 2px solid #1ABC9C;
                background-color: #3B4A59;
            }
        """)

        container.field = field
        return container

    # --------------------------------------------------
    # LOGIN LOGIC
    # --------------------------------------------------

    def login(self):
        try:


            self.login_btn.setEnabled(False)
            self.loading_label.show()

            username = self.username_input.field.text().strip()
            self.open_lobby(username)


            password = self.password_input.field.text()

            if not username or not password:
                #QMessageBox.warning(self, "Missing Fields", "Username and password are required.")
                self._shake()
                return

            response = self.client.send_request("login", username, password)

            if not response.get("success"):
                self._shake()
                QMessageBox.warning(self, "Login Failed", response.get("message"))
                return

            if response.get("requires_2fa"):
                self.prompt_verification_code(username)
                return

            self.open_lobby(username)

        except Exception as e:
            self._error("Login failed", e)

        finally:
            self.login_btn.setEnabled(True)
            self.loading_label.hide()

    # --------------------------------------------------
    # 2FA
    # --------------------------------------------------

    def prompt_verification_code(self, username):
        dialog = VerificationDialog(self)
        dialog.move(self.geometry().center() - dialog.rect().center())
        dialog.exec_()

        if not dialog.result_code:
            return

        response = self.client.send_request(
            "verify_code",
            username=username,
            code=dialog.result_code
        )

        if not response.get("success"):
            QMessageBox.warning(self, "Verification Failed", response.get("message"))
            return

        self.open_lobby(username)
    # --------------------------------------------------
    # EFFECTS
    # --------------------------------------------------

    def _shake(self):
        anim = QPropertyAnimation(self, b"pos")
        pos = self.pos()
        anim.setDuration(300)
        anim.setKeyValueAt(0, pos)
        anim.setKeyValueAt(0.25, pos + QPoint(-10, 0))
        anim.setKeyValueAt(0.5, pos + QPoint(10, 0))
        anim.setKeyValueAt(0.75, pos + QPoint(-10, 0))
        anim.setKeyValueAt(1, pos)
        anim.start()
        self._animations.append(anim)

    def _check_caps_lock(self):
        text = self.password_input.field.text()
        self.caps_label.setVisible(text.isupper() and len(text) > 1)

    # --------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------

    def signup(self):
        from Catan2.client.signupwindow import SignupDialog
        SignupDialog(self).exec_()

    def open_lobby(self, username):
        from Catan2.client.lobby import LobbyWindow
        self.going_to_lobby = True
        self.lobby = LobbyWindow(username, self.client)
        self.lobby.show()
        self.close()

    # --------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------

    def _error(self, title, error):
        print("\n" + "=" * 60)
        print(f"[ERROR] {title}")
        traceback.print_exc()
        print("=" * 60)
        QMessageBox.critical(self, title, str(error))

    def _fatal_error(self, title, error):
        self._error(title, error)
        self.close()
