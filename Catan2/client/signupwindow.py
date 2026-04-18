from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame,
    QGraphicsDropShadowEffect, QWidget, QHBoxLayout
)
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtCore import Qt, QSize, QPoint, QPropertyAnimation
from Catan2.client.Client import Client
import re


class SignupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.client = Client()
        self.setWindowTitle("Create Account")
        self.setFixedSize(460, 520)
        self.setStyleSheet("background-color: #1E272E;")

        self._animations = []  # 🔑 prevent GC
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # ---------- Card ----------
        card = QFrame()
        card.setFixedSize(360, 420)
        card.setStyleSheet("""
            QFrame {
                background-color: #2C3E50;
                border-radius: 18px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(18)

        # ---------- Title ----------
        title = QLabel("Create Account")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #ECF0F1;")

        subtitle = QLabel("Use a Gmail address to sign up")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #95A5A6;")

        # ---------- Inputs ----------
        self.username = self._styled_input("Username")
        self.email = self._styled_input("Gmail address (@gmail.com)")
        self.password = self._styled_input("Password", password=True)
        self.confirm = self._styled_input("Confirm password", password=True)

        self.password.field.textChanged.connect(self._update_password_strength)

        self.password_strength = QLabel("")
        self.password_strength.setFont(QFont("Segoe UI", 9))
        self.password_strength.setStyleSheet("color: #95A5A6;")

        # ---------- Button ----------
        signup_btn = QPushButton("Create Account")
        signup_btn.setCursor(Qt.PointingHandCursor)
        signup_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        signup_btn.setFixedHeight(42)
        signup_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover { background-color: #2980B9; }
            QPushButton:pressed { background-color: #2471A3; }
        """)
        signup_btn.clicked.connect(self.signup)

        # ---------- Assemble ----------
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(18)

        layout.addWidget(self.username)
        layout.addWidget(self.email)
        layout.addSpacing(12)
        layout.addWidget(self.password)
        layout.addWidget(self.password_strength)
        layout.addWidget(self.confirm)
        layout.addSpacing(22)
        layout.addWidget(signup_btn)

        main_layout.addWidget(card)

        # ---------- ENTER submits ----------
        for field in (self.username, self.email, self.password, self.confirm):
            field.field.returnPressed.connect(self.signup)

    def _styled_input(self, placeholder, password=False):
        container = QWidget()
        container.setFixedHeight(48)

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
            eye.setFocusPolicy(Qt.NoFocus)

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
            QWidget:focus-within {
                border: 2px solid #1ABC9C;
                background-color: #3B4A59;
            }
        """)

        container.field = field
        return container

    def _update_password_strength(self, text):
        score = sum([
            len(text) >= 8,
            bool(re.search(r"[A-Z]", text)),
            bool(re.search(r"[a-z]", text)),
            bool(re.search(r"[0-9]", text)),
            bool(re.search(r"[!@#$%^&*]", text)),
        ])

        if score <= 2:
            self.password_strength.setText("Password strength: Weak")
            self.password_strength.setStyleSheet("color:#E74C3C;")
        elif score <= 4:
            self.password_strength.setText("Password strength: Medium")
            self.password_strength.setStyleSheet("color:#F1C40F;")
        else:
            self.password_strength.setText("Password strength: Strong")
            self.password_strength.setStyleSheet("color:#2ECC71;")

    def _shake(self, widget):
        anim = QPropertyAnimation(widget, b"pos")
        start = widget.pos()
        anim.setDuration(300)
        anim.setKeyValueAt(0, start)
        anim.setKeyValueAt(0.25, start + QPoint(-8, 0))
        anim.setKeyValueAt(0.5, start + QPoint(8, 0))
        anim.setKeyValueAt(0.75, start + QPoint(-8, 0))
        anim.setKeyValueAt(1, start)
        anim.start()
        self._animations.append(anim)

    def signup(self):
        try:
            u = self.username.field.text().strip()
            e = self.email.field.text().strip()
            p = self.password.field.text()
            c = self.confirm.field.text()

            if not all([u, e, p, c]):
                QMessageBox.warning(self, "Error", "All fields required")
                self._shake(self)
                return

            if p != c:
                QMessageBox.warning(self, "Error", "Passwords do not match")
                self._shake(self)
                return

            import re

            if not re.fullmatch(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", e):
                QMessageBox.warning(self, "Error", "Enter a valid email address")
                return

            response = self.client.send_request("signup", username=u, email=e, password=p)

            if response.get("success"):
                QMessageBox.information(self, "Success", "Account created!")
                self.accept()
            else:
                QMessageBox.warning(self, "Signup Failed", response.get("message"))

        except Exception as ex:
            print("[SIGNUP ERROR]", ex)
            QMessageBox.critical(self, "Error", "Server error")