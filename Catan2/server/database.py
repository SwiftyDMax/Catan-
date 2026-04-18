import sqlite3
import hashlib
import threading
import os
import hmac

DB_PATH = "users.db"
_db_lock = threading.Lock()


class Database:
    def __init__(self):
        self._ensure_tables()

    # -----------------------------
    # Connection helper
    # -----------------------------
    def connect(self):
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # -----------------------------
    # Table setup
    # -----------------------------
    def _ensure_tables(self):
        conn = self.connect()
        try:
            cur = conn.cursor()

            # Users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                ); 
            """)

            # Profiles table
            cur.execute("""
               CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT,
                profile_picture_data BLOB,
                bio TEXT DEFAULT '',
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
                );
            """)

            # ✅ Challenges table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    challenge_name TEXT NOT NULL,
                    completed INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );
            """)
            # Friend requests
            cur.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER NOT NULL,
                to_user INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_user, to_user),
                FOREIGN KEY(from_user) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(to_user) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            # Friends list
            cur.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                user1 INTEGER NOT NULL,
                user2 INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user1, user2),
                FOREIGN KEY(user1) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(user2) REFERENCES users(id) ON DELETE CASCADE
            );
            """)
            # Inside _ensure_tables(self)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER NOT NULL,
                to_user INTEGER NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(from_user) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(to_user) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            conn.commit()
        finally:
            conn.close()

    # -----------------------------
    # Normalization helpers
    # -----------------------------
    def _normalize_username(self, username: str) -> str:
        return username.strip().lower()

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    # -----------------------------
    # Secure password hashing
    # -----------------------------
    def _hash_password(self, password_plain: str, salt=None) -> str:
        if salt is None:
            salt = os.urandom(16)

        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password_plain.encode(),
            salt,
            100000
        )

        return salt.hex() + ":" + hashed.hex()

    def _verify_password(self, password_plain: str, stored_value: str) -> bool:
        salt_hex, hash_hex = stored_value.split(":")
        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password_plain.encode(),
            salt,
            100000
        ).hex()

        return hmac.compare_digest(new_hash, hash_hex)

    # -----------------------------
    # User creation
    # -----------------------------
    def add_user(self, username, email, password_plain):
        if not username or not email or not password_plain:
            return False, "All fields are required"

        username = self._normalize_username(username)
        email = self._normalize_email(email)

        password_hash = self._hash_password(password_plain)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            with _db_lock:
                # Insert user
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash)
                )
                user_id = cur.lastrowid

                # Insert profile
                cur.execute(
                    "INSERT INTO profiles (user_id, display_name) VALUES (?, ?)",
                    (user_id, username)
                )

                # Initialize challenges directly here
                default_challenges = [
                    ("Win 5 games", 0, 5),

                ]
                cur.executemany(
                    "INSERT INTO challenges (user_id, challenge_name, completed, total) VALUES (?, ?, ?, ?)",
                    [(user_id, name, completed, total) for name, completed, total in default_challenges]
                )

                conn.commit()

            return True, "Account created!"

        except sqlite3.IntegrityError:
            if conn:
                conn.rollback()
            return False, "Username or email already exists"

        except Exception as e:
            if conn:
                conn.rollback()
            print("[DB ERROR]", e)
            return False, "Database error"

        finally:
            if conn:
                conn.close()
    # -----------------------------
    # Verify login
    # -----------------------------
    def verify_user(self, username, password_plain):
        username = self._normalize_username(username)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            cur.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,)
            )

            row = cur.fetchone()
            if not row:
                return False, "Username not found"

            user_id, stored_hash = row

            if self._verify_password(password_plain, stored_hash):
                return True, user_id

            return False, "Wrong password"

        finally:
            if conn:
                conn.close()

    # -----------------------------
    # Get profile
    # -----------------------------
    def get_profile(self, username):
        username = self._normalize_username(username)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            cur.execute("""
                SELECT u.username,
                       p.display_name,
                       p.profile_picture_data,
                       p.bio,
                       p.games_played,
                       p.games_won
                FROM profiles p
                JOIN users u ON p.user_id = u.id
                WHERE u.username = ?
            """, (username,))

            row = cur.fetchone()
            if not row:
                return None

            print(row[0])
            return {
                "username": row[0],
                "display_name": row[1],
                "profile_picture_data": row[2],
                "bio": row[3],
                "games_played": row[4],
                "games_won": row[5],
            }

        finally:
            if conn:
                conn.close()

    # -----------------------------
    # Update profile
    # -----------------------------
    def update_profile(self, username, display_name=None, bio=None):

        username = self._normalize_username(username)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            updates = []
            values = []

            if display_name is not None:
                updates.append("display_name = ?")
                values.append(display_name)

            if bio is not None:
                updates.append("bio = ?")
                values.append(bio)

            if not updates:
                return False, "Nothing to update"

            values.append(username)

            query = f"""
                UPDATE profiles
                SET {", ".join(updates)}
                WHERE user_id = (
                    SELECT id FROM users WHERE username = ?
                )
            """

            with _db_lock:
                cur.execute(query, values)
                conn.commit()

            if cur.rowcount == 0:
                return False, "User not found"

            return True, "Profile updated"

        finally:
            if conn:
                conn.close()

    def update_profile_picture(self, username, file_data):
        username = self._normalize_username(username)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            cur.execute("""
                UPDATE profiles
                SET profile_picture_data = ?
                WHERE user_id = (
                    SELECT id FROM users WHERE username = ?
                )
            """, (file_data, username))

            conn.commit()

            return cur.rowcount > 0

        except Exception as e:
            print("DB update_profile_picture error:", e)
            return False

        finally:
            if conn:
                conn.close()

    def update_bio(self, username, bio):
        username = self._normalize_username(username)

        # Optional safety: limit bio length
        if bio is None:
            return False

        bio = bio.strip()

        if len(bio) > 500:  # prevent abuse
            bio = bio[:500]

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            with _db_lock:
                cur.execute("""
                      UPDATE profiles
                      SET bio = ?
                      WHERE user_id = (
                          SELECT id FROM users WHERE username = ?
                      )
                  """, (bio, username))

                conn.commit()

            return cur.rowcount > 0

        except Exception as e:
            print("DB update_bio error:", e)
            return False

        finally:
            if conn:
                conn.close()



    def get_challenges(self, username):
        username = self._normalize_username(username)

        conn = self.connect()
        try:
            cur = conn.cursor()

            # Get user_id
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if not row:
                return []

            user_id = row[0]

            # Fetch challenges
            cur.execute("""
                SELECT challenge_name, completed, total
                FROM challenges
                WHERE user_id = ?
            """, (user_id,))

            challenges = []
            for name, completed, total in cur.fetchall():
                challenges.append({
                    "name": name,
                    "completed": completed,
                    "total": total
                })

            return challenges
        finally:
            conn.close()

    def send_friend_request(self, from_user, to_user):
        conn = self.connect()
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username=?", (from_user,))
            from_id = cur.fetchone()

            cur.execute("SELECT id FROM users WHERE username=?", (to_user,))
            to_id = cur.fetchone()

            if not from_id or not to_id:
                return False, "User not found"

            from_id = from_id[0]
            to_id = to_id[0]

            cur.execute("""
            INSERT OR IGNORE INTO friend_requests (from_user, to_user)
            VALUES (?,?)
            """, (from_id, to_id))

            conn.commit()

            return True, "Request sent"

        except Exception as e:
            print(e)
            return False, "Database error"

        finally:
            conn.close()

    def get_pending_requests(self, username):
        conn = self.connect()
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            user_id = cur.fetchone()[0]

            cur.execute("""
            SELECT u.username
            FROM friend_requests fr
            JOIN users u ON fr.from_user = u.id
            WHERE fr.to_user = ?
            """, (user_id,))

            return [r[0] for r in cur.fetchall()]

        finally:
            conn.close()

    def accept_friend_request(self, from_user, to_user):
        conn = self.connect()
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username=?", (from_user,))
            row = cur.fetchone()
            if not row:
                return False
            from_id = row[0]

            cur.execute("SELECT id FROM users WHERE username=?", (to_user,))
            row = cur.fetchone()
            if not row:
                return False
            to_id = row[0]

            user1, user2 = sorted([from_id, to_id])

            cur.execute("""
            INSERT OR IGNORE INTO friends (user1, user2)
            VALUES (?,?)
            """, (user1, user2))

            cur.execute("""
            DELETE FROM friend_requests
            WHERE from_user=? AND to_user=?
            """, (from_id, to_id))

            conn.commit()

            return True

        finally:
            conn.close()

    def get_friends_list(self, username, online_users):
        conn = self.connect()
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            user_id = cur.fetchone()[0]

            cur.execute("""
            SELECT u.username, p.profile_picture_data
            FROM friends f
            JOIN users u
            ON (u.id = f.user1 OR u.id = f.user2)
            JOIN profiles p
            ON p.user_id = u.id
            WHERE (? IN (f.user1, f.user2))
            AND u.id != ?
            """, (user_id, user_id))

            friends = []

            for r in cur.fetchall():
                friend_name = r[0]
                picture_data = r[1]

                friends.append({
                    "username": friend_name,
                    "profile_picture_data": picture_data,
                    "online": friend_name in online_users
                })

            return friends

        finally:
            conn.close()

    def decline_friend_request(self, from_user, to_user):
        conn = self.connect()
        try:
            cur = conn.cursor()

            cur.execute("""
            DELETE FROM friend_requests
            WHERE from_user = (SELECT id FROM users WHERE username=?)
            AND to_user = (SELECT id FROM users WHERE username=?)
            """, (from_user, to_user))

            conn.commit()

        finally:
            conn.close()

    def get_email_by_username(self, username):
        username = self._normalize_username(username)

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()

            cur.execute(
                "SELECT email FROM users WHERE username = ?",
                (username,)
            )

            row = cur.fetchone()

            if not row:
                return None

            return row[0]

        finally:
            if conn:
                conn.close()

    # -----------------------------
    # Send a chat message
    # -----------------------------
    def send_message(self, from_user, to_user, message):
        if not message:
            return False

        conn = self.connect()
        try:
            cur = conn.cursor()
            # get user ids
            cur.execute("SELECT id FROM users WHERE username=?", (from_user,))
            from_id_row = cur.fetchone()
            cur.execute("SELECT id FROM users WHERE username=?", (to_user,))
            to_id_row = cur.fetchone()

            if not from_id_row or not to_id_row:
                return False

            from_id = from_id_row[0]
            to_id = to_id_row[0]

            with _db_lock:
                cur.execute("""
                    INSERT INTO messages (from_user, to_user, message)
                    VALUES (?, ?, ?)
                """, (from_id, to_id, message))
                conn.commit()
            return True
        except Exception as e:
            print("[DB ERROR send_message]", e)
            return False
        finally:
            conn.close()

    # -----------------------------
    # Get all messages between two users
    # -----------------------------
    def get_messages(self, username, friend_username):
        conn = self.connect()
        try:
            cur = conn.cursor()
            # get ids
            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            user_row = cur.fetchone()
            cur.execute("SELECT id FROM users WHERE username=?", (friend_username,))
            friend_row = cur.fetchone()
            if not user_row or not friend_row:
                return []

            user_id = user_row[0]
            friend_id = friend_row[0]

            cur.execute("""
                SELECT u_from.username, u_to.username, m.message, m.timestamp
                FROM messages m
                JOIN users u_from ON m.from_user = u_from.id
                JOIN users u_to ON m.to_user = u_to.id
                WHERE (m.from_user=? AND m.to_user=?) OR (m.from_user=? AND m.to_user=?)
                ORDER BY m.timestamp ASC
            """, (user_id, friend_id, friend_id, user_id))

            messages = []
            for row in cur.fetchall():
                messages.append({
                    "from": row[0],
                    "to": row[1],
                    "message": row[2],
                    "timestamp": row[3]
                })
            return messages
        finally:
            conn.close()