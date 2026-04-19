# Catan/client/lobby.py

import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QLineEdit, QMessageBox,
    QStackedWidget, QFrame, QApplication
)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt, QTimer, QSize

from Catan2.game.game_launcher import start_game_process
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

class LobbyWindow(QWidget):
    IMAGE_DIR = "images/lobby"

    def __init__(self, username: str, client):
        super().__init__()

        print("[DEBUG] Initializing LobbyWindow...")

        self.username = username
        self.client = client

        self.game_code = None
        self.max_players = None
        self.color = None
        self.is_host = False

        self.timer = None
        self.challenges = None
        self.nav_buttons = {}
        self.page_indices = {}
        self.in_game = False
        self.profile_pic = None
        self.chat_history = {}
        self.init_ui()

    # =========================================================
    # UTILITIES
    # =========================================================

    def dbg(self, where: str, e: Exception):
        import traceback
        print("\n" + "=" * 70)
        print(f"ERROR at: {where}")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()
        print("=" * 70 + "\n")

    def get_icon(self, filename, size=28):
        path = os.path.join(self.IMAGE_DIR, filename)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"[Warning] Missing image: {path}")
            return QIcon()
        return QIcon(
            pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def reset_game_state(self):
        self.game_code = None
        self.max_players = None
        self.color = None
        self.is_host = False

    # =========================================================
    # UI SETUP
    # =========================================================

    def init_ui(self):
        profile_data = self.client.send_request("get_profile",username=self.username)
        if profile_data.get("success"):
            profile = profile_data.get("profile", {})
            self.profile_pic = profile.get("profile_picture_data")
        else:
            print("Failed to fetch profile:", profile_data.get("message"))
        if self.profile_pic == None:
            self.change_picture_default()


        self.setWindowTitle("Catan Adventure Lobby")
        self.resize(720, 720)

        self.setStyleSheet("QWidget { background-color: #1A1A1D; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ---------------- NAVBAR ----------------
        navbar = QHBoxLayout()

        nav_definitions = [
            ("Home", "castle.png"),
            ("Play", "swords.png"),
            ("Friends", "friends.png"),
            ("Shop", "shop.png"),
            ("Challenges", "scroll.png"),
            ("Profile", "profile.png"),
        ]

        for name, icon_file in nav_definitions:
            btn = QPushButton(f"  {name}")
            btn.setIcon(self.get_icon(icon_file))
            btn.setIconSize(QSize(26, 26))
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, n=name: self.on_nav_clicked(n))
            btn.setStyleSheet(self.nav_button_style(False))

            self.nav_buttons[name] = btn
            navbar.addWidget(btn)

        main_layout.addLayout(navbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        main_layout.addWidget(sep)

        # ---------------- CENTER STACK ----------------
        self.center_stack = QStackedWidget()
        main_layout.addWidget(self.center_stack, stretch=1)

        self.page_indices["Home"] = self.center_stack.addWidget(self.build_home_page())
        self.page_indices["Play"] = self.center_stack.addWidget(self.build_play_page())
        self.page_indices["Waiting"] = self.center_stack.addWidget(self.build_waiting_page())
        self.page_indices["Friends"] = self.center_stack.addWidget(self.build_friends_page())
        self.page_indices["Shop"] = self.center_stack.addWidget(self.build_simple_page("Shop"))
        self.page_indices["Challenges"] = self.center_stack.addWidget(self.build_challenges_page())
        self.page_indices["Profile"] =   self.center_stack.addWidget(self.build_profile_page())

        self.on_nav_clicked("Home")

    # =========================================================
    # STYLES
    # =========================================================

    def nav_button_style(self, active):
        if active:
            return """
                QPushButton {
                    background-color: #3b2e1e;
                    color: #FFE9C4;
                    border: 2px solid #d4a654;
                    border-radius: 12px;
                    padding: 10px 18px;
                    font-weight: bold;
                }
            """
        return """
            QPushButton {
                background-color: transparent;
                color: #b8a88f;
                padding: 10px 18px;
            }
        """

    def parchment_box(self):
        return """
        QGroupBox {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #2b241c,
                stop:1 #1c1814
            );
            border: 2px solid #5a4a32;
            border-radius: 18px;
            margin-top: 20px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 6px 14px;
            color: #FFE9C4;
            font-weight: bold;
            background: #1c1814;
            border-radius: 8px;
        }
        """

    # =========================================================
    # PAGES
    # =========================================================
    def copy_game_code(self):
        if not self.game_code:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(self.game_code)

        QMessageBox.information(
            self,
            "Copied",
            f"Game code '{self.game_code}' copied to clipboard!"
        )

    def build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(30)
        layout.setContentsMargins(60, 50, 60, 50)

        # ---------------- HERO ----------------
        title = QLabel("🏰 Welcome to Catan Adventure")
        title.setFont(QFont("Papyrus", 34, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #FFE9C4;
            letter-spacing: 1px;
        """)

        subtitle = QLabel(
            "Build settlements, trade resources,\n"
            "and conquer the island with friends."
        )
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #cdbb9a;
            line-height: 18px;
        """)

        # Decorative divider
        divider = QLabel("────────────── ✦ ──────────────")
        divider.setAlignment(Qt.AlignCenter)
        divider.setStyleSheet("color: #8e7a52;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(divider)

        # ---------------- FEATURE CARDS ----------------
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(25)

        def feature_card(icon, title, text):
            box = QGroupBox()
            box.setStyleSheet(self.parchment_box())

            v = QVBoxLayout(box)
            v.setAlignment(Qt.AlignTop)
            v.setSpacing(10)

            icon_label = QLabel(icon)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setFont(QFont("Segoe UI Emoji", 26))

            t = QLabel(title)
            t.setFont(QFont("Segoe UI", 14, QFont.Bold))
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet("color: #FFE9C4;")

            desc = QLabel(text)
            desc.setFont(QFont("Segoe UI", 10))
            desc.setAlignment(Qt.AlignCenter)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #b9aa87;")

            v.addWidget(icon_label)
            v.addWidget(t)
            v.addWidget(desc)

            return box

        cards_layout.addWidget(
            feature_card(
                "⚔️",
                "Play",
                "Create a new game or join an existing one and begin your conquest."
            )
        )

        cards_layout.addWidget(
            feature_card(
                "👥",
                "Friends",
                "Invite friends, track opponents, and build rivalries."
            )
        )

        cards_layout.addWidget(
            feature_card(
                "🧙",
                "Profile",
                "Customize your identity and view your achievements."
            )
        )

        layout.addLayout(cards_layout)

        # ---------------- FOOTER TIP ----------------
        tip = QLabel("💡 Tip: Use the navigation bar above to explore the lobby.")
        tip.setFont(QFont("Segoe UI", 9))
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("color: #8e7a52;")

        layout.addStretch(1)
        layout.addWidget(tip)

        return page

    def build_play_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(40)
        layout.setContentsMargins(60, 40, 60, 40)

        # =====================================================
        # CREATE GAME CARD
        # =====================================================

        create_box = QGroupBox("🛠️ Create a New Game")
        create_box.setStyleSheet(self.parchment_box())
        create_layout = QVBoxLayout(create_box)
        create_layout.setSpacing(14)

        desc_create = QLabel(
            "Start a new adventure and invite friends.\n"
            "You will be the host."
        )
        desc_create.setStyleSheet("""
            color:#b9aa87;
            font-size:12px;
            line-height:16px;
        """)
        desc_create.setWordWrap(True)

        lbl_players = QLabel("Number of Players")
        lbl_players.setStyleSheet("color:#FFE9C4;")

        self.players_combo = QComboBox()
        self.players_combo.addItems(["3 players", "4 players"])
        self.players_combo.setStyleSheet(
            "background:#1c1814; color:#FFE9C4; padding:6px; border-radius:6px;"
        )

        lbl_color = QLabel("Your Color")
        lbl_color.setStyleSheet("color:#FFE9C4;")

        self.color_combo_create = QComboBox()
        colors = ["Red", "Blue", "White", "Orange"]

        for c in colors:
            self.color_combo_create.addItem(c)

            if c == "Red":
                self.color_combo_create.setItemData(
                    self.color_combo_create.count() - 1,
                    QColor(220, 60, 60),
                    Qt.ForegroundRole
                )
            elif c == "Blue":
                self.color_combo_create.setItemData(
                    self.color_combo_create.count() - 1,
                    QColor(80, 140, 255),
                    Qt.ForegroundRole
                )
            elif c == "White":
                self.color_combo_create.setItemData(
                    self.color_combo_create.count() - 1,
                    QColor(230, 230, 230),
                    Qt.ForegroundRole
                )
            elif c == "Orange":
                self.color_combo_create.setItemData(
                    self.color_combo_create.count() - 1,
                    QColor(255, 150, 50),
                    Qt.ForegroundRole
                )
                self.color_combo_create.setStyleSheet(
            "background:#1c1814; color:#FFE9C4; padding:6px; border-radius:6px;"
        )

        create_btn = QPushButton("Create Game")
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1c56b;
                color: #1c1814;
                padding: 14px;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffd97a;
            }
            QPushButton:pressed {
                background-color: #e0b85e;
            }
        """)

        create_btn.clicked.connect(self.create_game)

        create_layout.addWidget(desc_create)
        create_layout.addSpacing(10)
        create_layout.addWidget(lbl_players)
        create_layout.addWidget(self.players_combo)
        create_layout.addWidget(lbl_color)
        create_layout.addWidget(self.color_combo_create)
        create_layout.addStretch(1)
        create_layout.addWidget(create_btn)

        # =====================================================
        # JOIN GAME CARD
        # =====================================================

        join_box = QGroupBox("🔑 Join an Existing Game")
        join_box.setStyleSheet(self.parchment_box())
        join_layout = QVBoxLayout(join_box)
        join_layout.setSpacing(14)

        desc_join = QLabel(
            "Enter a game code shared by a friend\n"
            "to join their world."
        )
        desc_join.setStyleSheet("color:#d4c5a1; font-size:13px;")
        desc_join.setWordWrap(True)

        lbl_code = QLabel("Game Code")
        lbl_code.setStyleSheet("color:#FFE9C4;")

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("ABCD")
        self.code_input.setMaxLength(6)
        self.code_input.setStyleSheet("""
            QLineEdit {
                background:#1c1814;
                color:#FFE9C4;
                padding:12px;
                border-radius:10px;
                font-weight:bold;
                letter-spacing:4px;
                border: 2px solid #5a4a32;
            }
            QLineEdit:focus {
                border: 2px solid #f1c56b;
                background:#241f1a;
            }
        """)

        lbl_color_join = QLabel("Your Color")
        lbl_color_join.setStyleSheet("color:#FFE9C4;")

        self.color_combo_join = QComboBox()
        for c in colors:
            self.color_combo_join.addItem(c)

            if c == "Red":
                self.color_combo_join.setItemData(
                    self.color_combo_join.count() - 1,
                    QColor(220, 60, 60),
                    Qt.ForegroundRole
                )
            elif c == "Blue":
                self.color_combo_join.setItemData(
                    self.color_combo_join.count() - 1,
                    QColor(80, 140, 255),
                    Qt.ForegroundRole
                )
            elif c == "White":
                self.color_combo_join.setItemData(
                    self.color_combo_join.count() - 1,
                    QColor(230, 230, 230),
                    Qt.ForegroundRole
                )
            elif c == "Orange":
                self.color_combo_join.setItemData(
                    self.color_combo_join.count() - 1,
                    QColor(255, 150, 50),
                    Qt.ForegroundRole
                )
        self.color_combo_join.setStyleSheet(
            "background:#1c1814; color:#FFE9C4; padding:6px; border-radius:6px;"
        )

        join_btn = QPushButton("Join Game")
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.setStyleSheet("""
            QPushButton {
                background-color: #b58d4a;
                color: #1c1814;
                padding: 12px;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d4a654;
            }
        """)

        join_btn.clicked.connect(self.join_game)

        join_layout.addWidget(desc_join)
        join_layout.addSpacing(10)
        join_layout.addWidget(lbl_code)
        join_layout.addWidget(self.code_input)
        join_layout.addWidget(lbl_color_join)
        join_layout.addWidget(self.color_combo_join)
        join_layout.addStretch(1)
        join_layout.addWidget(join_btn)

        # =====================================================
        # ADD TO PAGE
        # =====================================================

        layout.addWidget(create_box, stretch=1)
        layout.addWidget(join_box, stretch=1)

        return page

    def build_waiting_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(80, 60, 80, 60)

        # ---------------- TITLE ----------------
        title = QLabel("⏳ Waiting for Players")
        title.setFont(QFont("Papyrus", 26, QFont.Bold))
        title.setStyleSheet("color:#FFE9C4;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- GAME CODE BOX ----------------
        code_box = QGroupBox("Game Code")
        code_box.setStyleSheet(self.parchment_box())
        code_layout = QHBoxLayout(code_box)

        self.wait_code_input = QLineEdit()
        self.wait_code_input.setReadOnly(True)
        self.wait_code_input.setAlignment(Qt.AlignCenter)
        self.wait_code_input.setFont(QFont("Courier", 18, QFont.Bold))
        self.wait_code_input.setStyleSheet("""
            QLineEdit {
                background:#1c1814;
                color:#FFE9C4;
                padding:10px;
                border-radius:8px;
                letter-spacing:4px;
            }
        """)

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color:#d4a654;
                color:#1c1814;
                padding:8px 16px;
                border-radius:10px;
                font-weight:bold;
            }
            QPushButton:hover {
                background-color:#e8c777;
            }
        """)
        copy_btn.clicked.connect(self.copy_game_code)

        code_layout.addWidget(self.wait_code_input)
        code_layout.addWidget(copy_btn)

        layout.addWidget(code_box)

        # ---------------- PLAYERS LIST ----------------
        self.wait_players_label = QLabel("Players: -")
        self.wait_players_label.setStyleSheet(
            "color:#FFE9C4; font-size:15px;"
        )
        self.wait_players_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.wait_players_label)

        layout.addStretch(1)

        # ---------------- CANCEL BUTTON ----------------
        cancel_btn = QPushButton("Cancel Game")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color:#8B1E1E;
                color:white;
                padding:10px 24px;
                border-radius:12px;
                font-weight:bold;
            }
            QPushButton:hover {
                background-color:#A62727;
            }
        """)
        cancel_btn.clicked.connect(self.cancel_game)

        layout.addWidget(cancel_btn, alignment=Qt.AlignCenter)

        return page

    def build_challenges_page(self):
        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QScrollArea, QFrame
        from PyQt5.QtGui import QFont
        from PyQt5.QtCore import Qt

        page = QWidget()
        page.setStyleSheet("background-color:#1c1814; color:#FFE9C4;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(20)

        # ================= TITLE =================
        title = QLabel("🏆 Challenges Progress")
        title.setFont(QFont("Papyrus", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ================= FETCH CHALLENGES =================
        try:
            response = self.client.send_request("get_challenges", username=self.username)
            if not response.get("success") or not response.get("challenges"):
                raise ValueError("No challenges returned")

            self.challenges = response["challenges"]

            # ================= SCROLL AREA =================
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setSpacing(15)

            for c in self.challenges:
                # Card-like frame for each challenge
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background-color:#2a241d;
                        border:2px solid #d4a654;
                        border-radius:12px;
                    }
                """)
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(15, 10, 15, 10)
                card_layout.setSpacing(5)

                # Challenge name
                name_label = QLabel(c.get("name", "Unnamed Challenge"))
                name_label.setFont(QFont("Arial", 14, QFont.Bold))
                card_layout.addWidget(name_label)

                # Progress bar
                progress = QProgressBar()
                total = c.get("total", 1)
                completed = c.get("completed", 0)
                percent = int((completed / total) * 100)
                progress.setValue(percent)
                progress.setFormat(f"{completed} / {total} ({percent}%)")
                progress.setStyleSheet("""
                    QProgressBar {
                        background-color: #3b3224;
                        color: #FFE9C4;
                        border: 1px solid #a67c3b;
                        border-radius: 6px;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #d4a654;
                        border-radius: 6px;
                    }
                """)
                card_layout.addWidget(progress)

                scroll_layout.addWidget(card)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)

        except Exception as e:
            error_label = QLabel(f"Failed to load challenges: {e}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color:red; font-size:16px;")
            layout.addWidget(error_label)

        return page
    def build_simple_page(self, name):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(name))
        return page

    def on_friend_click(self, item):
        friend_username = item.text().split()[0]
        profile_pic = item.data(Qt.UserRole)
        self.open_friend_page(friend_username, profile_pic)
    def build_friends_page(self):
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QLineEdit, QListWidget, QListWidgetItem, QFrame
        )
        from PyQt5.QtCore import Qt

        page = QWidget()
        page.setStyleSheet("background-color:#1c1814; color:#FFE9C4;")  # dark background, light text
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        title = QLabel("👥 Friends")
        title.setStyleSheet("font-size:26px; font-weight:bold; color:#FFD700;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Send Friend Request ----------------
        send_frame = QFrame()
        send_frame.setStyleSheet("""
            QFrame { 
                background-color:#2a241d; 
                border:2px solid #d4a654; 
                border-radius:12px; 
            }
        """)
        send_layout = QHBoxLayout(send_frame)
        self.friend_input = QLineEdit()
        self.friend_input.setPlaceholderText("Enter username")
        self.friend_input.setStyleSheet("""
            QLineEdit { 
                padding:6px; 
                border-radius:8px; 
                border:1px solid #a67c3b; 
                background-color:#1c1814; 
                color:#FFE9C4;
            }
        """)
        send_btn = QPushButton("Send Request")
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton { 
                background-color:#d4a654; 
                color:#1c1814; 
                padding:6px 12px; 
                border-radius:8px; 
                font-weight:bold;
            }
            QPushButton:hover { background-color:#e8c777; }
        """)
        send_layout.addWidget(self.friend_input)
        send_layout.addWidget(send_btn)
        layout.addWidget(send_frame)

        def send_request():
            username = self.friend_input.text().strip()

            if username == self.username:
                QMessageBox.warning(self, "Error", "You can't send yourself a friends request.")
                return

            # check if already friends
            if username in getattr(self, "current_friends", []):
                QMessageBox.warning(self, "Error", "You are already friends with this user.")
                return

            if username:
                resp = self.client.send_request(
                    "send_friend_request",
                    from_user=self.username,
                    to_user=username
                )

                if resp.get("success"):
                    self.friend_input.clear()
                    load_pending_requests()
                else:
                    QMessageBox.warning(self, "Error", resp.get("message"))

        send_btn.clicked.connect(send_request)

        # ---------------- Pending Requests ----------------
        pending_label = QLabel("Pending Requests")
        pending_label.setStyleSheet("font-weight:bold; font-size:18px; color:#FFD700;")
        layout.addWidget(pending_label)

        self.pending_list = QListWidget()
        self.pending_list.setStyleSheet("""
            QListWidget { 
                background-color:#2a241d; 
                border:1px solid #a67c3b; 
                border-radius:10px; 
                padding:4px;
                color:#FFE9C4;
            }
        """)
        layout.addWidget(self.pending_list)

        def load_pending_requests():
            self.pending_list.clear()
            resp = self.client.send_request("get_pending_requests", username=self.username)
            for u in resp.get("requests", []):
                item = QListWidgetItem()
                widget = QFrame()
                widget.setStyleSheet("QFrame { background-color:#3b3225; border-radius:8px; }")
                h_layout = QHBoxLayout(widget)
                h_layout.setContentsMargins(8, 4, 8, 4)

                h_layout.addWidget(QLabel(u))
                accept_btn = QPushButton("Accept")
                decline_btn = QPushButton("Decline")
                for btn in (accept_btn, decline_btn):
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color:#d4a654; 
                            color:#1c1814; 
                            padding:3px 8px; 
                            border-radius:6px; 
                            font-weight:bold;
                        }
                        QPushButton:hover { background-color:#e8c777; }
                    """)
                h_layout.addWidget(accept_btn)
                h_layout.addWidget(decline_btn)

                def accept(user=u):
                    print("boogiedown")
                    print(user)
                    print(self.username)
                    self.client.send_request("accept_friend_request", from_user=user, to_user=self.username)
                    load_pending_requests()
                    load_friends_list()

                def decline(user=u):
                    self.client.send_request("decline_friend_request", from_user=user, to_user=self.username)
                    load_pending_requests()

                accept_btn.clicked.connect(lambda _, user=u: accept(user))
                decline_btn.clicked.connect(lambda _, user=u: decline(user))

                item.setSizeHint(widget.sizeHint())
                self.pending_list.addItem(item)
                self.pending_list.setItemWidget(item, widget)

        load_pending_requests()
        # create timer but DO NOT start yet
        self.friends_timer = QTimer()
        self.friends_timer.timeout.connect(load_pending_requests)

        # ---------------- Friends List ----------------
        friends_label = QLabel("Friends")
        friends_label.setStyleSheet("font-weight:bold; font-size:18px; color:#FFD700;")
        layout.addWidget(friends_label)

        self.friends_list = QListWidget()
        self.friends_list.itemClicked.connect(self.on_friend_click)
        self.friends_list.setStyleSheet("""
            QListWidget { 
                background-color:#2a241d; 
                border:1px solid #a67c3b; 
                border-radius:10px; 
                padding:4px; 
                color:#FFE9C4;
            }
        """)
        layout.addWidget(self.friends_list)

        from PyQt5.QtGui import QPixmap, QIcon
        from PyQt5.QtWidgets import QListWidgetItem

        def load_friends_list():
            self.friends_list.clear()
            resp = self.client.send_request("get_friends_list", username=self.username)

            self.current_friends = []

            for f in resp.get("friends", []):
                username = f["username"]
                online = f.get("online", False)
                profile_pic_data = f.get("profile_picture_data")  # bytes

                self.current_friends.append(username)

                item_text = f"{username} {'🟢' if online else '⚪'}"
                item = QListWidgetItem(item_text)

                if profile_pic_data:
                    from PyQt5.QtGui import QPixmap, QIcon, QPainter, QBrush

                    pixmap = QPixmap()
                    if pixmap.loadFromData(profile_pic_data):
                        size = 40
                        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        mask = QPixmap(size, size)
                        mask.fill(Qt.transparent)
                        painter = QPainter(mask)
                        painter.setRenderHint(QPainter.Antialiasing)
                        painter.setBrush(QBrush(Qt.white))
                        painter.drawEllipse(0, 0, size, size)
                        painter.end()
                        pixmap.setMask(mask.createMaskFromColor(Qt.transparent))
                        item.setIcon(QIcon(pixmap))

                # Store profile_pic_data in item for later use
                item.setData(Qt.UserRole, profile_pic_data)

                self.friends_list.addItem(item)




        load_friends_list()
        # create timer but DO NOT start yet
        self.friends_timer = QTimer()
        self.friends_timer.timeout.connect(load_pending_requests)
        self.friends_timer.timeout.connect(load_friends_list)
        layout.addStretch()

        return page

    def open_friend_page(self, friend_username, profile_pic_data=None):
        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton
        from PyQt5.QtGui import QPixmap, QPainter, QBrush
        from PyQt5.QtCore import Qt

        # ---------------- Fetch profile picture from server if not provided ----------------
        if profile_pic_data is None:
            try:
                resp = self.client.send_request("get_profile", username=friend_username)
                if resp.get("success"):
                    profile_data = resp.get("profile")
                    profile_pic_data = profile_data.get("profile_picture_data")  # could be bytes or None
            except Exception as e:
                print(f"Error fetching profile picture from server: {e}")

        # ---------------- Create Friend Page ----------------
        self.friend_page = QWidget()
        page = self.friend_page
        page.setStyleSheet("background-color:#1c1814; color:#FFE9C4;")
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        # check if already friends
        is_friend = friend_username in getattr(self, "current_friends", [])
        # ---------------- Profile Picture ----------------
        pic_label = QLabel()
        pic_label.setAlignment(Qt.AlignCenter)
        size = 150

        if profile_pic_data and isinstance(profile_pic_data, bytes):
            pixmap = QPixmap()
            if pixmap.loadFromData(profile_pic_data):
                pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # make circular
                mask = QPixmap(size, size)
                mask.fill(Qt.transparent)
                painter = QPainter(mask)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(QBrush(Qt.white))
                painter.drawEllipse(0, 0, size, size)
                painter.end()
                pixmap.setMask(mask.createMaskFromColor(Qt.transparent))
                pic_label.setPixmap(pixmap)
            else:
                pic_label.setText("No Image")
                pic_label.setStyleSheet("color:#b9aa87;")
        else:
            pic_label.setText("No Image")
            pic_label.setStyleSheet("color:#b9aa87;")

        layout.addWidget(pic_label)

        # ---------------- Username ----------------
        username_label = QLabel(friend_username)
        username_label.setAlignment(Qt.AlignCenter)
        username_label.setStyleSheet("font-size:20px; font-weight:bold; color:#FFD700;")
        layout.addWidget(username_label)
        # ---------------- Friend Request Option ----------------
        if not is_friend:
            add_friend_btn = QPushButton("Send Friend Request")
            add_friend_btn.setCursor(Qt.PointingHandCursor)
            add_friend_btn.setStyleSheet("""
                QPushButton {
                    background-color:#5fa8d3;
                    color:white;
                    padding:6px 16px;
                    border-radius:8px;
                    font-weight:bold;
                }
                QPushButton:hover { background-color:#7fbce0; }
            """)

            def send_friend_request():
                resp = self.client.send_request(
                    "send_friend_request",
                    from_user=self.username,
                    to_user=friend_username
                )

                if resp.get("success"):
                    add_friend_btn.setText("Request Sent ✓")
                    add_friend_btn.setEnabled(False)
                else:
                    QMessageBox.warning(page, "Error", resp.get("message"))

            add_friend_btn.clicked.connect(send_friend_request)
            layout.addWidget(add_friend_btn)
        # ---------------- Chat Area ----------------
        chat_area = QTextEdit()
        chat_area.setReadOnly(True)
        chat_area.setStyleSheet("""
            QTextEdit {
                background-color:#2a241d;
                border:1px solid #a67c3b;
                border-radius:10px;
                padding:8px;
                color:#FFE9C4;
            }
        """)
        layout.addWidget(chat_area)

        # ---------------- Message Input ----------------
        message_input = QTextEdit()
        message_input.setFixedHeight(50)
        message_input.setStyleSheet("""
            QTextEdit {
                background-color:#1c1814;
                border:1px solid #a67c3b;
                border-radius:10px;
                padding:6px;
                color:#FFE9C4;
            }
        """)
        layout.addWidget(message_input)

        # ---------------- Send Button ----------------
        send_btn = QPushButton("Send")
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color:#d4a654;
                color:#1c1814;
                padding:6px 16px;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover { background-color:#e8c777; }
        """)
        layout.addWidget(send_btn)

        # ---------------- Sending Chat ----------------
        def send_message():
            msg = message_input.toPlainText().strip()
            if msg:
                # send to server
                resp = self.client.send_request(
                    "send_message",
                    from_user=self.username,
                    to_user=friend_username,
                    message=msg
                )
                if resp.get("success"):
                    chat_area.append(f"You: {msg}")
                    self.chat_history.setdefault(friend_username, {"messages": []})["messages"].append({
                        "from": self.username,
                        "message": msg
                    })
                    message_input.clear()
                else:
                    chat_area.append(f"Error: {resp.get('message')}")

        send_btn.clicked.connect(send_message)

        # ---------------- Load Previous Messages ----------------
        if friend_username not in self.chat_history:
            print("requesting messages for:", friend_username)

            resp = self.client.send_request(
                "get_messages",
                username=self.username,
                friend_username=friend_username
            )

            self.chat_history[friend_username] = resp or {"messages": []}

        for m in self.chat_history.get(friend_username, {}).get("messages", []):
            sender = m["from"]
            text = m["message"]
            chat_area.append(f"{sender}: {text}")

        page.setWindowTitle(friend_username)
        page.setGeometry(300, 100, 400, 600)
        page.show()

    import os

    import os

    def change_picture_default(self):
        import os
        import random
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt

        # Get base directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(base_dir)

        # Folder with profile pictures
        pictures_dir = os.path.join(base_dir, "images", "ProfilePictures")

        if not os.path.exists(pictures_dir):
            print(f"Profile pictures folder not found: {pictures_dir}")
            return

        # Get all image files
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp")
        pictures = [f for f in os.listdir(pictures_dir) if f.lower().endswith(valid_extensions)]

        if not pictures:
            print("No profile pictures found in folder.")
            return

        # Pick a random picture
        random_picture = random.choice(pictures)
        file_path = os.path.join(pictures_dir, random_picture)

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            print(f"Sending random profile picture ({random_picture}) to server...")

            response = self.client.send_request(
                "update_profile_picture",
                username=self.username,
                file_data=file_data
            )

            if response.get("success"):
                print("Random profile picture updated successfully")
            else:
                print("Failed to update picture:", response.get("message"))

        except Exception as e:
            print("Error updating picture:", e)



    def build_profile_page(self):
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QLabel, QPushButton,
            QFileDialog, QMessageBox, QFrame,
            QHBoxLayout, QTextEdit
        )
        from PyQt5.QtGui import QFont, QPixmap, QPainter, QBrush
        from PyQt5.QtCore import Qt
        import os

        page = QWidget()
        page.setStyleSheet("background-color:#1c1814;")

        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(80, 50, 80, 50)
        main_layout.setSpacing(25)

        try:
            resp = self.client.send_request("get_profile", self.username)

            if not resp.get("success") or not resp.get("profile"):
                raise ValueError("Server did not return a valid profile")

            profile = resp["profile"]

            # ================= TITLE =================
            title = QLabel("👤 Profile")
            title.setFont(QFont("Papyrus", 30, QFont.Bold))
            title.setStyleSheet("color:#FFE9C4; letter-spacing:2px;")
            title.setAlignment(Qt.AlignCenter)

            # ================= CARD CONTAINER =================
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color:#2a241d;
                    border:2px solid #d4a654;
                    border-radius:18px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(40, 30, 40, 30)
            card_layout.setSpacing(20)

            # ================= PROFILE PICTURE =================
            picture_label = QLabel()
            picture_label.setAlignment(Qt.AlignCenter)
            size = 150

            def set_profile_pixmap(image_source):
                """
                image_source: can be a path (str) or raw bytes (bytes)
                """
                if not image_source:
                    picture_label.setText("No Image")
                    picture_label.setStyleSheet("color:#b9aa87;")
                    return

                pixmap = QPixmap()

                # Check if image_source is bytes
                if isinstance(image_source, bytes):
                    if not pixmap.loadFromData(image_source):
                        picture_label.setText("No Image")
                        picture_label.setStyleSheet("color:#b9aa87;")
                        return
                else:
                    if not pixmap.load(image_source):
                        picture_label.setText("No Image")
                        picture_label.setStyleSheet("color:#b9aa87;")
                        return

                pixmap = pixmap.scaled(
                    size,
                    size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )

                # Apply circular mask
                mask = QPixmap(size, size)
                mask.fill(Qt.transparent)

                painter = QPainter(mask)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(QBrush(Qt.white))
                painter.drawEllipse(0, 0, size, size)
                painter.end()

                pixmap.setMask(mask.createMaskFromColor(Qt.transparent))
                picture_label.setPixmap(pixmap)
                picture_label.setStyleSheet("""
                    border:3px solid #d4a654;
                    border-radius:75px;
                """)

            set_profile_pixmap(profile.get("profile_picture_data"))  # load bytes from DB

            # ================= CHANGE BUTTON =================
            change_btn = QPushButton("Change Profile Picture")
            change_btn.setCursor(Qt.PointingHandCursor)
            change_btn.setStyleSheet("""
                QPushButton {
                    background-color:#d4a654;
                    color:#1c1814;
                    padding:8px 18px;
                    border-radius:10px;
                    font-weight:bold;
                }
                QPushButton:hover {
                    background-color:#e8c777;
                }
            """)

            from PyQt5.QtWidgets import QFileDialog, QMessageBox

            def change_picture():
                file_path, _ = QFileDialog.getOpenFileName(
                    page,
                    "Select Profile Picture",
                    "",
                    "Images (*.png *.jpg *.jpeg *.bmp)"
                )

                if not file_path:
                    return

                try:
                    # Read file as bytes
                    with open(file_path, "rb") as f:
                        file_data = f.read()

                    # Send only file_data, no file_name
                    print('lobby hey')
                    print(file_data)
                    response = self.client.send_request(
                        "update_profile_picture",
                        username=self.username,
                        file_data=file_data
                    )

                    if response.get("success"):
                        set_profile_pixmap(file_path)  # display locally
                        QMessageBox.information(page, "Success", "Profile picture updated!")
                    else:
                        QMessageBox.warning(page, "Error", "Failed to update picture.")

                except Exception as e:
                    QMessageBox.critical(page, "Error", str(e))

            change_btn.clicked.connect(change_picture)

            # ================= USER INFO =================
            username_label = QLabel(f"Username: {self.username}")
            username_label.setStyleSheet("color:#FFE9C4; font-size:18px; font-weight:bold;")

            display_label = QLabel(f"Display Name: {profile.get('display_name', '')}")
            display_label.setStyleSheet("color:#d4c5a1; font-size:15px;")

            # ================= BIO SECTION =================
            bio_title = QLabel("Bio")
            bio_title.setStyleSheet("color:#FFE9C4; font-size:16px; font-weight:bold;")

            bio_edit = QTextEdit()
            bio_edit.setText(profile.get("bio", ""))
            bio_edit.setFixedHeight(100)
            bio_edit.setStyleSheet("""
                QTextEdit {
                    background-color:#1c1814;
                    color:#d4c5a1;
                    border:1px solid #a67c3b;
                    border-radius:10px;
                    padding:8px;
                    font-size:14px;
                }
            """)

            save_bio_btn = QPushButton("Save Bio")
            save_bio_btn.setCursor(Qt.PointingHandCursor)
            save_bio_btn.setStyleSheet("""
                QPushButton {
                    background-color:#d4a654;
                    color:#1c1814;
                    padding:6px 16px;
                    border-radius:8px;
                    font-weight:bold;
                }
                QPushButton:hover {
                    background-color:#e8c777;
                }
            """)

            def save_bio():
                new_bio = bio_edit.toPlainText().strip()

                try:
                    response = self.client.send_request(
                        "update_bio",
                        username=self.username,
                        bio=new_bio
                    )

                    if response.get("success"):
                        QMessageBox.information(page, "Success", "Bio updated!")
                    else:
                        QMessageBox.warning(page, "Error", "Failed to update bio.")

                except Exception as e:
                    QMessageBox.critical(page, "Error", str(e))

            save_bio_btn.clicked.connect(save_bio)

            # ================= STATS BOX =================
            stats_box = QFrame()
            stats_box.setStyleSheet("""
                QFrame {
                    background-color:#1c1814;
                    border:1px solid #a67c3b;
                    border-radius:12px;
                }
            """)
            stats_layout = QVBoxLayout(stats_box)
            stats_layout.setContentsMargins(15, 12, 15, 12)

            stats_label = QLabel(
                f"🎮 Games Played: {profile.get('games_played', 0)}\n"
                f"🏆 Games Won: {profile.get('games_won', 0)}"
            )
            stats_label.setStyleSheet("color:#FFE9C4; font-size:14px;")
            stats_layout.addWidget(stats_label)

            # ================= ADD TO CARD =================
            card_layout.addWidget(picture_label, alignment=Qt.AlignCenter)
            card_layout.addWidget(change_btn, alignment=Qt.AlignCenter)
            card_layout.addSpacing(15)
            card_layout.addWidget(username_label)
            card_layout.addWidget(display_label)

            card_layout.addWidget(bio_title)
            card_layout.addWidget(bio_edit)
            card_layout.addWidget(save_bio_btn, alignment=Qt.AlignRight)

            card_layout.addWidget(stats_box)

            # ================= ADD TO MAIN LAYOUT =================
            main_layout.addWidget(title)
            main_layout.addWidget(card, alignment=Qt.AlignCenter)
            main_layout.addStretch(1)

        except Exception as e:
            error_label = QLabel("Failed to load profile")
            error_label.setStyleSheet("color:red; font-size:16px;")
            error_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(error_label)

        return page

    # =========================================================
    # NAVIGATION
    # =========================================================
    def rebuild_challenges_page(self):
        index = self.page_indices["Challenges"]

        old_widget = self.center_stack.widget(index)

        new_widget = self.build_challenges_page()

        self.center_stack.removeWidget(old_widget)
        old_widget.deleteLater()

        self.center_stack.insertWidget(index, new_widget)

    def on_nav_clicked(self, name):

        # Update nav buttons
        for n, btn in self.nav_buttons.items():
            active = (n == name)
            btn.setChecked(active)
            btn.setStyleSheet(self.nav_button_style(active))

        # 🔥 FIX HERE
        if name == "Challenges":
            self.rebuild_challenges_page()

        self.center_stack.setCurrentIndex(self.page_indices[name])

        # Friends timer
        if name == "Friends":
            if hasattr(self, "friends_timer"):
                self.friends_timer.start(4000)
        else:
            if hasattr(self, "friends_timer"):
                self.friends_timer.stop()
    # =========================================================
    # GAME LOGIC
    # =========================================================

    def create_game(self):
        players = int(self.players_combo.currentText().split()[0])
        self.color = self.color_combo_create.currentText()

        resp = self.client.send_request(
            "create_game",
            self.username,
            players_count=players,
            color=self.color
        )

        if not resp.get("success"):
            QMessageBox.warning(self, "Error", resp["message"])
            return

        self.game_code = resp["game_code"]
        self.max_players = players
        self.is_host = True
        self.in_game = True

        self.show_waiting()

    def join_game(self):
        code = self.code_input.text().strip().upper()
        self.code_input.clear()
        if not code:
            return

        self.color = self.color_combo_join.currentText()

        resp = self.client.send_request(
            "join_game",
            self.username,
            game_code=code,
            color=self.color
        )

        if not resp.get("success"):
            QMessageBox.warning(self, "Error", resp["message"])
            return

        self.game_code = code
        self.is_host = False
        self.in_game = True

        self.show_waiting()

    def cancel_game(self):
        if not self.in_game:
            return

        self.client.send_request(
            "cancel_game",
            self.username,
            game_code=self.game_code
        )

        if self.timer:
            self.timer.stop()
            self.timer = None

        self.reset_game_state()
        self.in_game = False

        QMessageBox.information(self, "Game canceled", "You have left the game.")
        self.on_nav_clicked("Play")

    def show_waiting(self):
        self.wait_code_input.setText(self.game_code)
        self.center_stack.setCurrentIndex(self.page_indices["Waiting"])
        self.start_polling()

    def start_polling(self):
        if self.timer:
            self.timer.stop()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_room_status)
        self.timer.start(1500)

    def check_room_status(self):
        resp = self.client.send_request(
            "room_status",
            self.username,
            game_code=self.game_code
        )

        if not resp.get("success"):
            return

        players = resp["players"]
        self.wait_players_label.setText("Players:\n" + "\n".join(players))

        if resp["ready"]:
            self.timer.stop()
            self.start_game()

    def start_game(self):
        print("[DEBUG] Starting game process")

        self.hide()  # 🔥 CLOSE LOBBY FIRST

        start_game_process(
            client=self.client,
            username=self.username,
            game_code=self.game_code,
            parent_window=self
        )

