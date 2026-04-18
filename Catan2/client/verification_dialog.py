from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QPropertyAnimation
from PyQt5.QtWidgets import QDialog


class VerificationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.result_code = None

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 280)

        # Fade-in animation
        self.setWindowOpacity(0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

        main = QVBoxLayout(self)
        main.setAlignment(Qt.AlignCenter)

        # ---------- Card ----------
        card = QWidget()
        card.setFixedSize(380, 240)
        card.setStyleSheet("""
            QWidget {
                background-color: #2C3E50;
                border-radius: 18px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(35)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # ---------- Text ----------
        title = QLabel("Two-Step Verification")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #ECF0F1;")

        subtitle = QLabel("Enter the 6-digit code sent to your email")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #95A5A6;")

        # ---------- Input ----------
        self.code_input = QLineEdit()
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.code_input.setFixedHeight(48)
        self.code_input.setStyleSheet("""
            QLineEdit {
                background-color: #34495E;
                border-radius: 12px;
                border: 2px solid #34495E;
                color: #ECF0F1;
                letter-spacing: 6px;
            }
            QLineEdit:focus {
                border: 2px solid #1ABC9C;
            }
        """)

        # ---------- Button ----------
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setCursor(Qt.PointingHandCursor)
        self.verify_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.verify_btn.setFixedHeight(42)
        self.verify_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #12876F; }
        """)

        # ---------- Assemble ----------
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.code_input)
        layout.addSpacing(8)
        layout.addWidget(self.verify_btn)

        main.addWidget(card)

        self.verify_btn.clicked.connect(self._submit)
        self.code_input.returnPressed.connect(self._submit)

    def _submit(self):
        code = self.code_input.text().strip()

        if not code.isdigit() or len(code) != 6:
            self.code_input.setStyleSheet(
                self.code_input.styleSheet() +
                "QLineEdit { border: 2px solid #E74C3C; }"
            )
            return

        self.result_code = code
        self.close()
