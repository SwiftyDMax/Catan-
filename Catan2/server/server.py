import socket
import threading
import sqlite3
import hashlib
import pickle
import random
import string
import smtplib
from email.mime.text import MIMEText
from Catan2.server.database import Database
import os
import pickle
import struct
import time
import uuid



def send_msg(sock, obj):
    data = pickle.dumps(obj)
    # pack length as 4-byte integer
    sock.sendall(struct.pack('!I', len(data)) + data)

def recv_msg(sock):
    # first 4 bytes: length
    raw_len = recvall(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('!I', raw_len)[0]
    # receive the exact message
    return pickle.loads(recvall(sock, msg_len))

def recvall(sock, n):
    """Helper to receive exactly n bytes"""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
db = Database()
# =====================
# Server config
# =====================
HOST = "localhost" #172.16.11.145
PORT = 5502
ADDR = (HOST, PORT)
BUFSIZE = 4096

# =====================
# Database setup
# =====================

def init_db():
    conn = sqlite3.connect("users.db", timeout=5)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()
# =====================
# In-memory game storage
# =====================
rooms = {}   # game_code -> room data
games = {}   # game_code -> game state
dev_card_deck_global = {}
rooms_lock = threading.Lock()
pending_2fa = {}


online_users = set()
online_lock = threading.Lock()
db_lock = threading.Lock()
# =====================
# Helpers
# =====================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def signup(username, email, password):
    with db_lock:
        success, message = db.add_user(username, email, password)
    return {"success": success, "message": message}

def login(username, password):
    with db_lock:
        success, result = db.verify_user(username, password)
    if not success:
        return {"success": False, "message": "Invalid username or password!"}

    code = str(random.randint(100000, 999999))
    pending_2fa[username] = code
    with db_lock:
        email = db.get_email_by_username(username)
    send_verification_email(email, code)

    return {
        "success": True,
        "requires_2fa": True,
        "message": "Verification code sent"
    }


def generate_game_code(length=6):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if code not in rooms:
            return code

def send_verification_email(to_email, code):
    sender_email = "maximmaerov@gmail.com"
    sender_password = "mvrc zjah zayf ozjh"

    msg = MIMEText(f"Your verification code is: {code}")
    msg["Subject"] = "Catan login Verification"
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

def verify_code(username, code):
    if pending_2fa.get(username) != code:
        return {"success": False, "message": "Invalid code"}

    del pending_2fa[username]

    with online_lock:
        online_users.add(username)

    return {"success": True}
import math

def build_vertex_map(hex_positions):
    vertex_map = {}

    HEX_SIZE = 100  # same size you used to draw hexes

    for hx, hy in hex_positions:
        for i in range(6):
            angle = math.pi / 3 * i

            vx = hx + HEX_SIZE * math.cos(angle)
            vy = hy + HEX_SIZE * math.sin(angle)

            v = normalize((vx, vy))

            if v not in vertex_map:
                vertex_map[v] = []

            vertex_map[v].append((hx, hy))

    return vertex_map
# =====================
# Game / Room logic
# =====================
def buy_dev_card(username, game_code):
    game = games.get(game_code)
    if not game:
        return {"success": False}

    # =========================
    # TURN CHECK
    # =========================
    if game.get("current_turn") != username:
        return {
            "success": False,
            "message": "You can only buy development cards on your turn"
        }

    # =========================
    # 🚫 BLOCK SETUP PHASE
    # =========================
    if game.get("phase", "").startswith("setup"):
        return {
            "success": False,
            "message": "You cannot buy development cards during setup"
        }

    # =========================
    # 🚫 MUST ROLL DICE FIRST
    # =========================
    if not game.get("dice_rolled_this_turn", False):
        return {
            "success": False,
            "message": "You must roll the dice before buying a development card"
        }
    if game.get("robber_active", False):
        return {"success": False, "message": "Cannot buy dev cards while robber is active"}

    ensure_player(game, username)
    player = game["player_resources"][username]

    # =========================
    # RESOURCE CHECK
    # =========================
    if player["wheat"] < 1 or player["wool"] < 1 or player["ore"] < 1:
        return {"success": False, "message": "Not enough resources"}

    player["wheat"] -= 1
    player["wool"] -= 1
    player["ore"] -= 1

    deck = game["dev_card_deck"]
    available = [k for k, v in deck.items() if v > 0]

    if not available:
        return {"success": False, "message": "No cards left"}

    card = random.choice(available)
    deck[card] -= 1

    game["player_resources"][username]["dev_cards"].append({
        "type": card,
        "turn_bought": game["turn_number"]
    })

    return {
        "success": True,
        "card": card,
        "dev_cards": game["player_resources"][username]["dev_cards"]
    }
def choose_year_of_plenty(username, game_code, resource):
    game = games.get(game_code)

    if not game:
        return {"success": False, "message": "Game not found"}

    yop = game.get("year_of_plenty_active")

    # =========================
    # VALIDATION
    # =========================
    if not yop or yop["player"] != username:
        return {"success": False, "message": "Year of Plenty not active"}

    if resource not in ["wood", "brick", "wheat", "wool", "ore"]:
        return {"success": False, "message": "Invalid resource"}

    # =========================
    # SAFE ADD
    # =========================
    game["player_resources"][username].setdefault(resource, 0)
    game["player_resources"][username][resource] += 1

    yop["remaining"] -= 1

    # =========================
    # FINISH
    # =========================
    if yop["remaining"] <= 0:
        game.pop("year_of_plenty_active", None)

    return {
        "success": True,
        "resource": resource,
        "remaining": yop.get("remaining", 0)
    }



def use_monopoly(username, game_code, resource):
    game = games.get(game_code)

    total = 0

    for player, res in game["player_resources"].items():
        if player == username:
            continue

        amount = res.get(resource, 0)
        total += amount
        res[resource] = 0

    game["player_resources"][username].setdefault(resource, 0)
    game["player_resources"][username][resource] += total

    return {
        "success": True,
        "gained": total
    }

def use_dev_card(username, game_code, card):
    game = games.get(game_code)

    if not game:
        return {"success": False}

    # =========================
    # MUST BE YOUR TURN
    # =========================
    if game.get("current_turn") != username:
        return {
            "success": False,
            "message": "You can only use development cards on your turn"
        }

    # =========================
    # 🚫 MUST ROLL DICE FIRST
    # =========================
    if not game.get("dice_rolled_this_turn", False):
        return {
            "success": False,
            "message": "You must roll the dice before using a development card"
        }

    # =========================
    # TRACK USED DEV CARD THIS TURN
    # =========================
    used_set = game.setdefault("dev_card_used_this_turn", set())

    if username in used_set:
        return {
            "success": False,
            "message": "You already used a development card this turn"
        }

    player_cards = game["player_resources"][username]["dev_cards"]

    # =========================
    # FIND USABLE CARD (NOT BOUGHT THIS TURN)
    # =========================
    usable_card = None
    for c in player_cards:
        if c["type"] == card and c["turn_bought"] < game["turn_number"]:
            usable_card = c
            break

    if not usable_card:
        return {
            "success": False,
            "message": "No usable card (maybe bought this turn?)"
        }

    # mark player as used dev card this turn
    used_set.add(username)

    # remove card
    player_cards.remove(usable_card)
    game.setdefault("dev_card_discard", []).append(card)

    # =========================
    # EFFECTS
    # =========================
    if card == "knight":
        game["robber_active"] = True
        game["robber_phase"] = "move"

        # 1. Update knight count
        game["knight_count"][username] = game["knight_count"].get(username, 0) + 1
        current_knights = game["knight_count"][username]

        # ✅ FIX: Use f-string to prevent "TypeError: can only concatenate str (not 'int') to str"
        print(f"knight_count: {current_knights}")

        # 2. Largest Army Logic
        if current_knights >= 3:
            holder = game.get("largest_army_owner")
            print(f"Current holder of Largest Army: {holder}")

            # Case A: No one has it yet
            if holder is None:
                game["largest_army_owner"] = username
                game["victory_points"][username] += 2
                print(f"{username} claimed Largest Army for the first time!")

            # Case B: Someone else has it, and I just beat their record
            elif holder != username and current_knights > game["knight_count"].get(holder, 0):
                game["victory_points"][holder] -= 2
                game["largest_army_owner"] = username
                game["victory_points"][username] += 2
                print(f"{username} took Largest Army from {holder}!")
        winner = check_winner(game)

        if winner:
            game["winner"] = winner
        return {"success": True, "action": "move_robber"}



    elif card == "victory_point":

        game["dev_card_used_this_turn"] = set()

        # 1. Add actual victory point

        add_victory_points(game, username, 1)

        # 2. Track VP dev card separately

        game["vp_dev_cards"][username] = game["vp_dev_cards"].get(username, 0) + 1

        # 3. Check winner AFTER updating points

        winner = check_winner(game)

        if winner:
            game["winner"] = winner

        return {

            "success": True,

            "victory_points": game["victory_points"][username],

            "vp_dev_cards": game["vp_dev_cards"][username]

        }

    elif card == "road_building":
        game["road_building_active"] = {
            "player": username,
            "roads_left": 2
        }


    elif card == "year_of_plenty":

        game["year_of_plenty_active"] = {

            "player": username,

            "remaining": 2

        }

        return {

            "success": True,

            "action": "choose_year_of_plenty"

        }


    elif card == "monopoly":

        game["monopoly_active"] = {

            "player": username,

            "active": True

        }

        return {

            "success": True,

            "action": "choose_monopoly_resource"

        }

        # =========================
        # ✅ ALWAYS RETURN SOMETHING
        # =========================
    return {
        "success": True
    }







def choose_monopoly(username, game_code, resource):
    game = games.get(game_code)

    if not game:
        return {"success": False, "message": "Game not found"}

    mono = game.get("monopoly_active")

    if not mono:
        return {"success": False, "message": "Monopoly not active"}

    if mono.get("player") != username:
        return {"success": False, "message": "Not your monopoly turn"}

    if resource not in ["wood", "brick", "wheat", "wool", "ore"]:
        return {"success": False, "message": "Invalid resource"}

    total = 0

    for player, res in game["player_resources"].items():
        if player == username:
            continue

        amount = res.get(resource, 0)
        total += amount
        res[resource] = 0

    game["player_resources"][username].setdefault(resource, 0)
    game["player_resources"][username][resource] += total

    game.pop("monopoly_active", None)

    return {
        "success": True,
        "resource": resource,
        "gained": total
    }

def generate_board():
    W, H = 1820, 980
    cx, cy = W // 2, H // 2

    hexagon_positions = [
        (cx, cy),
        (cx - 100, cy), (cx + 100, cy),
        (cx - 200, cy), (cx + 200, cy),
        (cx - 50, cy - 90), (cx + 50, cy - 90),
        (cx - 150, cy - 90), (cx + 150, cy - 90),
        (cx - 100, cy - 180), (cx, cy - 180), (cx + 100, cy - 180),
        (cx - 50, cy + 90), (cx + 50, cy + 90),
        (cx - 150, cy + 90), (cx + 150, cy + 90),
        (cx - 100, cy + 180), (cx, cy + 180), (cx + 100, cy + 180),
    ]

    resources = (
        ["wood"] * 4 +
        ["brick"] * 3 +
        ["ore"] * 3 +
        ["wheat"] * 4 +
        ["wool"] * 4 +
        ["desert"]
    )

    numbers = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

    random.shuffle(resources)
    random.shuffle(numbers)

    hexagon_resources = {}
    hexagon_numbers = {}

    n_idx = 0
    for pos, res in zip(hexagon_positions, resources):
        hexagon_resources[pos] = res
        if res != "desert":
            hexagon_numbers[pos] = numbers[n_idx]
            n_idx += 1

    return hexagon_positions, hexagon_resources, hexagon_numbers

def generate_ports(hex_positions):
    center_x = sum(x for x, _ in hex_positions) / len(hex_positions)
    center_y = sum(y for _, y in hex_positions) / len(hex_positions)

    raw_ports = [
        ((center_x - 250, center_y - 90), "2:1 wood"),
        ((center_x + 200, center_y - 180), "2:1 ore"),
        ((center_x - 150, center_y - 260), "3:1 any"),
        ((center_x - 150, center_y + 250), "3:1 any"),
        ((center_x + 200, center_y + 180), "2:1 wool"),
        ((center_x + 50, center_y + 260), "3:1 any"),
        ((center_x - 250, center_y + 90), "2:1 brick"),
        ((center_x + 300, center_y), "3:1 any"),
        ((center_x + 40, center_y - 280), "2:1 wheat"),
    ]

    return raw_ports



def create_game(username, players_count, color):
    if players_count not in (3, 4):
        return {"success": False, "message": "Invalid player count"}

    color = color.strip().capitalize()

    game_code = generate_game_code()

    with rooms_lock:
        rooms[game_code] = {
            "host": username,
            "max_players": players_count,
            "players": [username],
            "player_colors": {username: color},
            "started": False
        }

        hex_positions, hex_resources, hex_numbers = generate_board()
        ports = generate_ports(hex_positions)
        # find desert BEFORE creating game
        desert_pos = None
        for pos, res in hex_resources.items():
            if res == "desert":
                desert_pos = pos
                break

        vertex_map = build_vertex_map(hex_positions)

        games[game_code] = {
            "start_time": time.time(),
            "end_time": None,
            "winner": None,
            "hexagon_positions": hex_positions,
            "hexagon_resources": hex_resources,
            "hexagon_numbers": hex_numbers,
            "vertex_to_hexes": vertex_map,

            "ports": ports,
            "settlements": {},
            "roads": {},
            "cities": {},

            "discard_required": {},
            "discard_submitted": {},
            "vp_dev_cards": {},
            "turn_number": 1,
            "victory_points": {},  # username -> points
            "longest_road_owner" : "",

            # ✅ correct robber initialization
            "robber_pos": desert_pos,
            "robber_active": False,
            "robber_pending_steal": None,

            "trades": {},  # trade_id -> trade object
            "trade_counter": 0, # for unique IDs


            "last_settlement": {},
            "player_resources": {},

            "dice_rolled_this_turn": False,

            # setup system
            "phase": "setup_settlement",
            "setup_index": 0,
            "setup_reverse": False,
            "setup_complete": False,
            "dev_card_used_this_turn" : set(),
            "dice": {
                "rolling": False,
                "result": None,
                "last_roll_time": 0
            },
            "dev_card_deck": {
                "knight": 14,
                "victory_point": 5,
                "road_building": 2,
                "year_of_plenty": 2,
                "monopoly": 2
            },
            "knight_count" : {},
            "largest_army_owner" : None,


            "dev_card_discard": [],

            "current_turn": username,
            "setup_order": []
        }

    return {
        "success": True,
        "game_code": game_code,
        "players": [username],
        "max_players": players_count,
        "ready": False
    }


def roll_dice(username, game_code):
    game = games.get(game_code)
    room = rooms.get(game_code)

    print("Trying to roll the dice")

    if not game or not room:
        return {"success": False, "message": "Game not found"}

    if game["current_turn"] != username:
        return {"success": False, "message": "Not your turn"}

    if game["phase"] != "normal":
        return {"success": False, "message": "Can not roll dice at setup"}

    dice = game["dice"]

    if dice["rolling"]:
        return {"success": False, "message": "Already rolling"}

    if game["dice_rolled_this_turn"]:
        return {"success": False, "message": "Can't roll twice"}

    # =========================
    # ROLL
    # =========================
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)

    dice["result"] = (d1, d2)
    total = d1 + d2

    game["dice_rolled_this_turn"] = True  # 🔥 ALWAYS SET THIS
    dice["rolling"] = False

    # =========================
    # 7 CASE (ROBBER)
    # =========================
    if total == 7:
        game["robber_active"] = True

        to_discard = {}

        for player, resources in game["player_resources"].items():
            resource_types = ["wood", "brick", "wheat", "wool", "ore"]

            total_cards = sum(resources.get(r, 0) for r in resource_types)

            if total_cards > 7:
                to_discard[player] = total_cards // 2

        game["discard_required"] = to_discard
        game["discard_submitted"] = {}
        if to_discard :
            game["robber_active"] = False
        return {
            "success": True,
            "dice": dice["result"],
            "total": total,
            "discard_phase": bool(to_discard),
            "players_to_discard": to_discard,
            "robber": not bool(to_discard)
        }

    # =========================
    # NORMAL CASE (2–12 except 7)
    # =========================
    give_resources_from_roll(game, total)

    return {
        "success": True,
        "dice": dice["result"],
        "total": total,
        "robber": False
    }

def discard_cards(username, game_code, discard_dict):
    game = games.get(game_code)

    if not game:
        return {"success": False, "message": "Game not found"}

    # 🔥 NEVER allow fallback {}
    if "discard_required" not in game:
        return {"success": False, "message": "No discard phase active"}

    required = game["discard_required"]
    submitted = game.setdefault("discard_submitted", {})

    # =========================
    # VALIDATION
    # =========================
    if username not in required:
        return {"success": False, "message": "You don't need to discard"}

    needed = required[username]

    player_res = game["player_resources"].get(username)
    if player_res is None:
        return {"success": False, "message": "Player resources missing"}

    # =========================
    # CLEAN INPUT
    # =========================
    cleaned = {}

    for res, amount in discard_dict.items():
        if isinstance(amount, list):
            amount = amount[0] if amount else 0

        if not isinstance(amount, int) or amount < 0:
            return {"success": False, "message": "Invalid discard"}

        cleaned[res] = amount

    if sum(cleaned.values()) != needed:
        return {"success": False, "message": f"You must discard exactly {needed}"}

    # =========================
    # CHECK RESOURCES
    # =========================
    for res, amount in cleaned.items():
        if player_res.get(res, 0) < amount:
            return {"success": False, "message": f"Not enough {res}"}

    # =========================
    # APPLY
    # =========================
    for res, amount in cleaned.items():
        player_res[res] -= amount

    submitted[username] = True

    # =========================
    # FINAL CHECK (SAFE)
    # =========================
    all_done = all(u in submitted for u in required)

    if all_done:
        game["discard_required"] = {}
        game["discard_submitted"] = {}

        game["robber_active"] = True  # 🔥 IMPORTANT FIX

        return {
            "success": True,
            "all_discarded": True,
            "robber": True,
            "next_phase": "robber"
        }

    return {
        "success": True,
        "waiting": True,
        "submitted": list(submitted.keys())
    }


def move_robber(username, game_code, position):
    game = games.get(game_code)
    room = rooms.get(game_code)

    if not game or not room:
        return {"success": False, "message": "Game not found"}
    if game.get("discard_required"):
        return {"success": False, "message": "Players must discard first"}
    if game["current_turn"] != username:
        return {"success": False, "message": "Not your turn"}

    if not game.get("robber_active", False):
        return {"success": False, "message": "Robber not active"}

    pos = normalize(position)

    if same_pos(pos, game.get("robber_pos")):
        return {
            "success": False,
            "message": "Robber is already there",
            "repeatable": True
        }

    # move robber
    game["robber_pos"] = pos

    # =========================
    # FIND PLAYERS ON HEX
    # =========================
    victims = set()

    for s_pos, owner in game["settlements"].items():
        if is_on_hex(s_pos, pos):
            victims.add(owner)

    for c_pos, owner in game["cities"].items():
        if is_on_hex(c_pos, pos):
            victims.add(owner)

    # ❌ HARD EXCLUSION OF SELF (IMPORTANT)
    victims.discard(username)

    victims = list(victims)

    # =========================
    # BUILD TARGETS WITH PFP
    # =========================
    targets = []

    if victims:
        for v in victims:
            profile = db.get_profile(v)   # <-- ACCESS YOUR DB HERE

            targets.append({
                "username": v,
                "profile_picture": profile["profile_picture_data"] if profile else None
            })

        game["robber_pending_steal"] = {
            "by": username,
            "targets": victims
        }

        return {
            "success": True,
            "robber_pos": pos,
            "action": "choose_player_to_steal",
            "targets": targets
        }

    # =========================
    # NO VICTIMS → END ROBBER
    # =========================
    game["robber_active"] = False

    return {
        "success": True,
        "robber_pos": pos
    }

def steal_from_player(username, game_code, target):
    game = games.get(game_code)

    if not game:
        return {"success": False}

    pending = game.get("robber_pending_steal")

    # =========================
    # VALIDATION
    # =========================
    if not pending:
        return {"success": False, "message": "No steal pending"}

    if username == target:
        return {"success": False, "message": "You cannot steal from yourself"}
    if pending["by"] != username:
        return {"success": False, "message": "Not your steal action"}

    if target not in pending["targets"]:
        return {"success": False, "message": "Invalid target"}

    victim_res = game["player_resources"][target]
    thief_res = game["player_resources"][username]

    # =========================
    # FIND AVAILABLE RESOURCES
    # =========================
    available = []

    for res in ["wood", "brick", "wheat", "wool", "ore"]:
        if victim_res.get(res, 0) > 0:
            available.append(res)

    # =========================
    # NOTHING TO STEAL
    # =========================
    if not available:
        game["robber_active"] = False
        game["robber_pending_steal"] = None

        return {
            "success": True,
            "stolen": None,
            "from": target
        }

    # =========================
    # STEAL RANDOM RESOURCE
    # =========================
    stolen = random.choice(available)

    victim_res[stolen] -= 1
    thief_res[stolen] = thief_res.get(stolen, 0) + 1

    # =========================
    # CLEAN STATE
    # =========================
    game["robber_active"] = False
    game["robber_pending_steal"] = None

    # =========================
    # ADD PFP HERE
    # =========================
    profile = db.get_profile(target)

    return {
        "success": True,
        "stolen": stolen,
        "from": target,
        "profile_picture": profile["profile_picture_data"] if profile else None
    }


def is_on_hex(node_pos, hex_pos):
    # distance-based check (adjust radius if needed)
    return math.dist(node_pos, hex_pos) < 80



def same_pos(a, b):
    return normalize(a) == normalize(b)




def give_resources_from_roll(game, dice_total):
    settlements = game["settlements"]
    cities = game.get("cities", {})  # 🔥 NEW
    hex_positions = game["hexagon_positions"]
    hex_numbers = game["hexagon_numbers"]
    hex_resources = game["hexagon_resources"]
    player_resources = game["player_resources"]

    for hex_pos in hex_positions:
        if hex_numbers.get(hex_pos) != dice_total:
            continue

        # 🚫 ROBBER BLOCK
        robber_pos = game.get("robber_pos")

        if robber_pos and normalize(robber_pos) == normalize(hex_pos):
            continue

        resource = hex_resources.get(hex_pos)

        if resource == "desert" or not resource:
            continue

        # =========================
        # 🏠 SETTLEMENTS (1 resource)
        # =========================
        for settlement_pos, owner in settlements.items():

            dx = settlement_pos[0] - hex_pos[0]
            dy = settlement_pos[1] - hex_pos[1]
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < 120:
                if owner not in player_resources:
                    player_resources[owner] = {}

                player_resources[owner][resource] = \
                    player_resources[owner].get(resource, 0) + 1

        # =========================
        # 🏙️ CITIES (2 resources)
        # =========================
        for city_pos, owner in cities.items():

            dx = city_pos[0] - hex_pos[0]
            dy = city_pos[1] - hex_pos[1]
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < 120:
                if owner not in player_resources:
                    player_resources[owner] = {}

                player_resources[owner][resource] = \
                    player_resources[owner].get(resource, 0) + 2




def ensure_player(game, username):
    if username not in game["player_resources"]:
        game["player_resources"][username] = {
            "wood": 0,
            "brick": 0,
            "wool": 0,
            "wheat": 0,
            "ore": 0,
            "dev_cards": []
        }


def check_winner(game):
    victory_points = game.get("victory_points", {})

    for player, points in victory_points.items():
        if points >= 10:
            return player

    return None

def is_game_over(game):
    return game.get("winner") is not None

def join_game(username, game_code, color):
    with rooms_lock:
        room = rooms.get(game_code)
        if not room:
            return {"success": False, "message": "Game not found"}

        if room["started"]:
            return {"success": False, "message": "Game already started"}

        if username in room["players"]:
            return {
                "success": True,
                "game_code": game_code,
                "players": room["players"],
                "ready": False
            }

        if len(room["players"]) >= room["max_players"]:
            return {"success": False, "message": "Room is full"}

        taken_colors = set(room["player_colors"].values())
        if color in taken_colors:
            return {"success": False, "message": "Color already taken"}

        room["players"].append(username)
        room["player_colors"][username] = color



        ready = len(room["players"]) == room["max_players"]
        if ready:
            room["started"] = True
            players = room["players"]

            setup_order = players + players[::-1]

            game = games[game_code]
            game["setup_order"] = setup_order
            game["setup_index"] = 0
            game["phase"] = "setup_settlement"
            game["current_turn"] = setup_order[0]
            game["settlement_count"] = {p: 0 for p in players}
            game["victory_points"] = {p: 0 for p in players}
            # 🔥 INIT RESOURCES
            game["player_resources"] = {
                p: {
                    "wood":10,
                    "brick": 10,
                    "wool": 0,
                    "wheat": 0,
                    "ore": 0,
                    "dev_cards": []
                }
                for p in players
            }

            game["victory_points"] = {p: 0 for p in players}

        return {
            "success": True,
            "game_code": game_code,
            "players": room["players"],
            "ready": ready
        }

def add_victory_points(game, username, amount):
    if "victory_points" not in game:
        game["victory_points"] = {}

    game["victory_points"][username] = game["victory_points"].get(username, 0) + amount

    if game["victory_points"][username] >= 10:
        game["winner"] = username
        game["phase"] = "finished"




def room_status(game_code):
    with rooms_lock:
        room = rooms.get(game_code)
        if not room:
            return {"success": False, "message": "Game not found"}

        return {
            "success": True,
            "game_code": game_code,
            "host": room["host"],
            "players": room["players"],
            "max_players": room["max_players"],
            "ready": room["started"]
        }


def get_game_state(game_code):
    game = games.get(game_code)
    room = rooms.get(game_code)
    print("SERVER STATE SEND:")
    print("  settlements:", game["settlements"])
    print("  player_colors:", room["player_colors"])
    print("  player_resources:", game["player_resources"])
    print("  ports:", game["ports"])
    if not game or not room:
        return {"success": False, "message": "Game not found"}

    return {
        "success": True,
        "hexagon_positions": game["hexagon_positions"],
        "hexagon_resources": game["hexagon_resources"],
        "hexagon_numbers": game["hexagon_numbers"],
        "dice": game.get("dice", {
            "rolling": False,
            "result": None
        }),
        "trades": game.get("trades", {}),
        "settlements": game["settlements"],
        "roads": game.get("roads", {}),
        "last_settlement": game.get("last_settlement", {}),
        "phase": game.get("phase", "free"),
        "current_turn": game["current_turn"],
        "player_colors": room.get("player_colors", {}),
        "player_resources": game.get("player_resources", {}),
        "dev_card_deck": game.get("dev_card_deck", {}),
        "dev_card_discard": game.get("dev_card_discard", []),
        "vp_dev_cards": game.get("vp_dev_cards", []),
        "settlement_count": {},
        "cities": game.get("cities", {}),
        "ports": game.get("ports", []),
        "robber_pos": game.get("robber_pos"),
        "robber_active": game.get("robber_active", False),
        "robber_pending_steal": game.get("robber_pending_steal"),
        "largest_army_owner": game.get("largest_army_owner"),
        "longest_road_owner": game.get("longest_road_owner"),
        "victory_points": game.get("victory_points", {}),
        "winner": game.get("winner"),
        "start_time" : game.get("start_time"),
        "turn_number" : game.get("turn_number"),
        "discard_required": game.get("discard_required") or {},
        "discard_submitted": game.get("discard_submitted") or {},
    }


def add_vp_dev_card(game, username):
    game["vp_dev_cards"][username] = game["vp_dev_cards"].get(username, 0) + 1

def normalize(p):
    return (round(p[0], 1), round(p[1], 1))

def next_turn(game, room):

    players = room["players"]
    current = game["current_turn"]

    idx = players.index(current)
    game["current_turn"] = players[(idx + 1) % len(players)]
    if not game["dice_rolled_this_turn"] :
        return {"success": False, "message": "You have got to roll the dice first"}
    # RESET dice lock each turn
    game["dice_rolled_this_turn"] = False

def end_turn(username, game_code):
    game = games.get(game_code)
    room = rooms.get(game_code)

    if not game or not room:
        return {"success": False, "message": "Game not found"}

    # 🚫 block setup
    if game.get("phase", "").startswith("setup"):
        return {"success": False, "message": "Cannot end turn during setup"}

    # 🚫 only current player
    if game["current_turn"] != username:
        return {"success": False, "message": "Not your turn"}

    # 🚫 must roll dice
    if not game.get("dice_rolled_this_turn", False):
        return {"success": False, "message": "You must roll the dice first"}
    # 🚫 must resolve robber first
    if game.get("robber_active") or game.get("robber_pending_steal"):
        return {"success": False, "message": "You must finish robber action"}
    # ✅ advance turn
    game["dev_card_used_this_turn"] = set()
    game["turn_number"] += 1

    next_turn(game, room)

    return {
        "success": True,
        "current_turn": game["current_turn"]
    }

def place_road(username, game_code, edge):

    game = games.get(game_code)
    room = rooms.get(game_code)

    if not game or not room:
        return {"success": False, "message": "Game not found"}

    a, b = edge
    a, b = normalize(a), normalize(b)
    edge = tuple(sorted((a, b)))

    if edge in game["roads"]:
        return {"success": False, "message": "Road exists"}

    is_setup = game["phase"].startswith("setup")

    # =========================
    # TURN / SETUP VALIDATION
    # =========================
    if is_setup:
        last = game["last_settlement"].get(username)

        if not last:
            return {"success": False, "message": "Place settlement first"}

        if last not in edge:
            return {"success": False, "message": "Road must connect to settlement"}

    else:
        if game["current_turn"] != username:
            return {"success": False, "message": "Not your turn"}

        if not game.get("dice_rolled_this_turn", False):
            return {"success": False, "message": "Roll dice first"}

    # =========================
    # 🔥 ROAD BUILDING DEV CARD
    # =========================
    ignore_cost = False

    rb = game.get("road_building_active")
    if rb and rb["player"] == username:
        ignore_cost = True

        rb["roads_left"] -= 1
        if rb["roads_left"] <= 0:
            game["road_building_active"] = None

    # =========================
    # 🔥 RESOURCE COST CHECK
    # =========================
    player_res = game["player_resources"].get(username, {})

    if not is_setup and not ignore_cost:

        missing = []

        if player_res.get("wood", 0) < 1:
            missing.append("wood")

        if player_res.get("brick", 0) < 1:
            missing.append("brick")

        if missing:
            return {
                "success": False,
                "error": "missing_resources",
                "missing": missing
            }

        # deduct resources
        player_res["brick"] -= 1
        player_res["wood"] -= 1

    # =========================
    # PLACE ROAD
    # =========================
    game["roads"][edge] = username

    lr_update = update_longest_road_owner(game)



    # =========================
    # SETUP PROGRESSION
    # =========================
    if is_setup:
        setup_order = game["setup_order"]
        game["setup_index"] += 1

        if game["setup_index"] >= len(setup_order):
            game["phase"] = "normal"
            game["current_turn"] = setup_order[0]
        else:
            game["phase"] = "setup_settlement"
            game["current_turn"] = setup_order[game["setup_index"]]

    return {
        "success": True,
        "longest_road_update": lr_update
    }
def build_player_road_graph(game, username):
    graph = {}

    for (a, b), owner in game["roads"].items():
        if owner != username:
            continue

        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)

    return graph

def is_blocked_vertex(game, vertex, username):
    owner = game["settlements"].get(vertex) or game["cities"].get(vertex)

    return owner is not None and owner != username

def dfs_longest_path(game, graph, current, visited_edges, username):
    max_length = 0

    for neighbor in graph.get(current, []):
        edge = tuple(sorted((current, neighbor)))

        if edge in visited_edges:
            continue

        # ❌ can't pass through enemy settlement
        if is_blocked_vertex(game, neighbor, username):
            continue

        visited_edges.add(edge)

        length = 1 + dfs_longest_path(
            game,
            graph,
            neighbor,
            visited_edges,
            username
        )

        max_length = max(max_length, length)

        visited_edges.remove(edge)

    return max_length

def calculate_longest_road(game, username):
    graph = build_player_road_graph(game, username)

    longest = 0

    for vertex in graph:
        if is_blocked_vertex(game, vertex, username):
            continue

        length = dfs_longest_path(game, graph, vertex, set(), username)
        longest = max(longest, length)

    return longest

def update_longest_road_owner(game):
    best_player = None
    best_length = 0

    for player in game["player_resources"].keys():
        length = calculate_longest_road(game, player)

        if length >= 5 and length > best_length:
            best_length = length
            best_player = player

    prev_owner = game.get("longest_road_owner")

    # remove previous bonus
    if prev_owner and prev_owner != best_player:
        game["victory_points"][prev_owner] -= 2

    # assign new bonus
    if best_player and best_player != prev_owner:
        game["victory_points"].setdefault(best_player, 0)
        game["victory_points"][best_player] += 2

    game["longest_road_owner"] = best_player

    return {
        "longest_road_owner": best_player,
        "longest_road_length": best_length,
        "previous_owner": prev_owner
    }



def is_adjacent(settlement, hex_pos):
    sx, sy = settlement
    hx, hy = hex_pos

    dx = hx - sx
    dy = hy - sy * 1.15  # keep your distortion fix

    dist = math.sqrt(dx*dx + dy*dy)

    # 1. basic radius filter (tight)
    if dist > 135:
        return False

    return True
import math

def direction(settlement, hex_pos):
    sx, sy = settlement
    hx, hy = hex_pos

    return math.atan2(hy - sy, hx - sx)
def weighted_distance(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]

    # compensate for stretched y spacing in your layout
    dy *= 1.15   # tuning factor (VERY important)

    return (dx*dx + dy*dy) ** 0.5


def get_player_ports(player, settlements, cities, ports):
    player_nodes = set()

    for pos, owner in settlements.items():
        if owner == player:
            player_nodes.add(pos)

    for pos, owner in cities.items():
        if owner == player:
            player_nodes.add(pos)

    owned_ports = []

    for port_pos, port_type in ports:
        for node in player_nodes:
            if math.dist(port_pos, node) < 80:
                owned_ports.append(port_type)
                break

    return owned_ports

def distance(a, b):
    return ((a[0] - b[0])**2 + (a[1] - b[1])**2) ** 0.5

# ports = [((x, y), "2:1 wood"), ((x, y), "3:1 any"), ...]

def get_trade_ratio(username, give_resource, settlements, cities, ports):
    player_vertices = set()

    # collect all player nodes
    for pos, owner in settlements.items():
        if owner == username:
            player_vertices.add(tuple(map(float, pos)))

    for pos, owner in cities.items():
        if owner == username:
            player_vertices.add(tuple(map(float, pos)))

    best_ratio = 4  # default (bank)

    for port_pos, port_type in ports:
        port_pos = tuple(map(float, port_pos))

        ratio_str, resource = port_type.split()  # "2:1 wood"
        ratio = int(ratio_str.split(":")[0])

        for v in player_vertices:
            # check if player touches port
            if distance(v, port_pos) < 80:  # tweak if needed

                # ✅ specific port (2:1)
                if ratio == 2 and resource == give_resource:
                    return 2

                # ✅ generic port (3:1)
                if resource == "any":
                    best_ratio = min(best_ratio, 3)

    return best_ratio

def trade_with_bank(username, game_code, give_resource, receive_resource):
    game = games.get(game_code)

    if not game:
        return {"success": False, "message": "Game not found"}

    # =========================
    # 🚫 BLOCK SETUP PHASE
    # =========================
    if game.get("phase", "").startswith("setup"):
        return {"success": False, "message": "Cannot trade during setup phase"}

    # =========================
    # 🚫 NOT YOUR TURN CHECK
    # =========================
    current_turn = game.get("current_turn")

    if current_turn != username:
        return {"success": False, "message": "Not your turn"}
        # =========================
        # 🚫 MUST ROLL DICE FIRST
        # =========================
    if not game.get("dice_rolled_this_turn", False):
        return {
            "success": False,
            "message": "You must roll the dice before trading"
        }
    player_resources = game.get("player_resources", {})
    settlements = game.get("settlements", {})
    cities = game.get("cities", {})
    ports = game.get("ports", [])

    # ✅ normalize username (prevents bugs)
    username = str(username)

    if username not in player_resources:
        print("[TRADE ERROR] username:", username)
        print("[TRADE ERROR] players:", list(player_resources.keys()))
        return {"success": False, "message": "Player not found"}

    resources = player_resources[username]

    # =========================
    # VALIDATION
    # =========================
    if give_resource == receive_resource:
        return {"success": False, "message": "Cannot trade same resource"}

    if give_resource not in resources:
        return {"success": False, "message": "Invalid give resource"}

    # =========================
    # GET TRADE RATIO
    # =========================
    ratio = get_trade_ratio(
        username,
        give_resource,
        settlements,
        cities,
        ports
    )

    # =========================
    # CHECK RESOURCES
    # =========================
    if resources.get(give_resource, 0) < ratio:
        return {
            "success": False,
            "message": f"Need {ratio} {give_resource} (ratio {ratio}:1)"
        }

    # =========================
    # PERFORM TRADE
    # =========================
    resources[give_resource] -= ratio
    resources[receive_resource] = resources.get(receive_resource, 0) + 1

    # =========================
    # SUCCESS RESPONSE
    # =========================
    return {
        "success": True,
        "message": f"Traded {ratio} {give_resource} → 1 {receive_resource}",
        "ratio": ratio,
        "give": give_resource,
        "receive": receive_resource
    }




def create_trade(username, game_code, to_player, offer, request):
    game = games.get(game_code)
    if not game:
        return {"success": False, "message": "Game not found"}

    # =========================
    # 🚫 BLOCK SETUP PHASE
    # =========================
    if game.get("phase", "").startswith("setup"):
        return {"success": False, "message": "Cannot trade during setup phase"}

    # =========================
    # 🚫 NOT YOUR TURN CHECK
    # =========================
    current_turn = game.get("current_turn")

    if current_turn != username:
        return {"success": False, "message": "Not your turn"}
        # =========================
        # 🚫 MUST ROLL DICE FIRST
        # =========================
    if not game.get("dice_rolled_this_turn", False):
        return {
            "success": False,
            "message": "You must roll the dice before trading"
        }
    # =========================
    # CREATE TRADE
    # =========================
    trade_id = game["trade_counter"]
    game["trade_counter"] += 1

    trade = {
        "id": trade_id,
        "from": username,
        "to": to_player,
        "offer": offer or {},
        "request": request or {},
        "status": "pending",
        "sender_confirmed": False,
        "receiver_confirmed": False
    }

    game["trades"][trade_id] = trade

    return {"success": True, "trade": trade}


def respond_trade(username, game_code, trade_id, accept):
    game = games.get(game_code)
    if not game:
        return {"success": False}

    trade = game["trades"].get(trade_id)
    if not trade:
        return {"success": False}

    if trade["to"] != username:
        return {"success": False, "message": "Not your trade"}

    if not accept:
        trade["status"] = "declined"
        return {"success": True}

    trade["status"] = "accepted"
    trade["receiver_confirmed"] = True

    return {"success": True, "trade": trade}



def confirm_trade(username, game_code, trade_id):
    game = games.get(game_code)
    if not game:
        return {"success": False}

    trade = game["trades"].get(trade_id)
    if not trade:
        return {"success": False}

    if trade["from"] != username:
        return {"success": False, "message": "Not your trade"}

    if trade["status"] != "accepted":
        return {"success": False, "message": "Trade not accepted yet"}

    trade["sender_confirmed"] = True

    # 💥 EXECUTE TRADE
    if trade["sender_confirmed"] and trade["receiver_confirmed"]:
        execute_trade(game, trade)
        trade["status"] = "finalized"

    return {"success": True}



def execute_trade(game, trade):
    p1 = trade["from"]
    p2 = trade["to"]

    res = game["player_resources"]

    # check resources exist
    for r, amount in trade["offer"].items():
        if res[p1].get(r, 0) < amount:
            return False

    for r, amount in trade["request"].items():
        if res[p2].get(r, 0) < amount:
            return False

    # perform trade
    for r, amount in trade["offer"].items():
        res[p1][r] -= amount
        res[p2][r] = res[p2].get(r, 0) + amount

    for r, amount in trade["request"].items():
        res[p2][r] -= amount
        res[p1][r] = res[p1].get(r, 0) + amount

    return True

def give_starting_resources(game, settlement_pos, username):
    candidates = []

    sx, sy = settlement_pos

    for hex_pos in game["hexagon_positions"]:
        hx, hy = hex_pos

        dx = hx - sx
        dy = (hy - sy) * 1.15

        dist = (dx*dx + dy*dy) ** 0.5

        if dist <= 135:
            candidates.append((dist, hex_pos))

    # 🔥 THIS IS THE IMPORTANT PART
    # keep ONLY natural cluster (not stray 3rd hex)

    candidates.sort(key=lambda x: x[0])

    final_hexes = []

    for dist, hex_pos in candidates:
        # accept first 3 only if they are not too far apart
        if len(final_hexes) == 0:
            final_hexes.append(hex_pos)
        else:
            # ensure it's part of same cluster
            if dist - candidates[0][0] < 35:
                final_hexes.append(hex_pos)

    for hex_pos in final_hexes:
        resource = game["hexagon_resources"][hex_pos]
        if resource != "desert":
            game["player_resources"][username][resource] += 1

def place_settlement(username, game_code, position):
    game = games.get(game_code)
    room = rooms.get(game_code)

    if not game or not room:
        return {"success": False, "message": "Game not found"}

    pos = normalize(position)

    if game["current_turn"] != username:
        return {"success": False, "message": "Not your turn"}

    # 🚫 prevent double settlement
    if game["phase"] == "setup_road":
        return {"success": False, "message": "Place road first"}

    if game["phase"] == "normal" and not game.get("dice_rolled_this_turn", False):
        return {"success": False, "message": "Roll dice first"}

    if pos in game["settlements"]:
        return {"success": False, "message": "Spot already taken"}

    # =========================
    # 🔥 RESOURCE COST (ONLY NORMAL GAME)
    # =========================
    player_res = game["player_resources"].get(username, {})

    if game["phase"] == "normal":
        missing = []

        if player_res.get("wood", 0) < 1:
            missing.append("wood")
        if player_res.get("brick", 0) < 1:
            missing.append("brick")
        if player_res.get("wheat", 0) < 1:
            missing.append("wheat")
        if player_res.get("wool", 0) < 1:
            missing.append("wool")

        if missing:
            return {
                "success": False,
                "error": "missing_resources",
                "missing": missing
            }

        # deduct resources
        player_res["wood"] -= 1
        player_res["brick"] -= 1
        player_res["wheat"] -= 1
        player_res["wool"] -= 1

    # =========================
    # PLACE SETTLEMENT
    # =========================

    game["settlements"][pos] = username
    game["settlement_count"][username] += 1

    # starting resources (setup only)
    if game["phase"].startswith("setup") and game["settlement_count"][username] == 2:
        give_starting_resources(game, pos, username)

    game["last_settlement"][username] = pos

    # 🔥 MOVE TO ROAD PHASE (setup only)
    if game["phase"].startswith("setup"):
        game["phase"] = "setup_road"
    add_victory_points(game, username, 1)
    winner = check_winner(game)

    if winner:
        game["winner"] = winner

    return {"success": True}

def upgrade_city(username, game_code, position):
    game = games.get(game_code)
    room = rooms.get(game_code)

    if not game or not room:
        return {"success": False, "message": "Game not found"}

    pos = normalize(position)

    if game["current_turn"] != username:
        return {"success": False, "message": "Not your turn"}

    if not game.get("dice_rolled_this_turn", False):
        return {"success": False, "message": "Roll dice first"}

    if pos not in game["settlements"]:
        return {"success": False, "message": "No settlement here"}

    if game["settlements"][pos] != username:
        return {"success": False, "message": "Not your settlement"}

    # 🔥 COST: 3 ore + 2 wheat
    player_res = game["player_resources"][username]

    missing = []
    if player_res.get("ore", 0) < 3:
        missing.append("ore")
    if player_res.get("wheat", 0) < 2:
        missing.append("wheat")

    if missing:
        return {
            "success": False,
            "error": "missing_resources",
            "missing": missing
        }

    # deduct
    player_res["ore"] -= 3
    player_res["wheat"] -= 2

    # 🔥 upgrade
    del game["settlements"][pos]

    if "cities" not in game:
        game["cities"] = {}

    game["cities"][pos] = username
    add_victory_points(game, username, 1)  # city = +1 over settlement
    winner = check_winner(game)

    if winner:
        game["winner"] = winner
    return {"success": True}



# =====================
# Client handler
# =====================
def handle_client(client_socket):
    username = None
    try:
        while True:
            request = recv_msg(client_socket)

            if not request:
                break  # client disconnected safely

            action = request.get("action")
            response = {"success": False, "message": "Unknown action"}
            print(action)
            if action == "signup":
                response = signup(
                    request.get("username"),
                    request.get("email"),
                    request.get("password")
                )
            elif action == "login":
                response = login(
                    request.get("username"),
                    request.get("password")
                )

            elif action == "create_game":
                    response = create_game(
                        request.get("username"),
                        int(request.get("players_count", 4)),
                        request.get("color", "Red")
                    )

            elif action == "join_game":
                response = join_game(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("color", "Red").capitalize()
                )

            elif action == "room_status":
                response = room_status(request.get("game_code"))

            elif action == "game_state":
                response = get_game_state(request.get("game_code"))
            elif action == "place_settlement":
                print("server side place ")
                response = place_settlement(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("position")
                )
            elif action == "place_road":
                print("hellllloooooo the server is tryin the place_road")
                response = place_road(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("edge")
                )
                print(response)
            elif action == "verify_code":
                username = request.get("username")
                response = verify_code(username, request.get("code"))

            elif action == "get_profile":
                with db_lock:
                    profile = db.get_profile(request.get("username"))

                if not profile:
                    response = {"success": False, "message": "Profile not found"}
                    print(response)
                else:
                    response = {"success": True, "profile": profile}







            elif action == "update_profile_picture":
                print("server hey")
                username = request.get("username")

                file_data = request.get("file_data")  # no file_name needed
                with db_lock:
                    success = db.update_profile_picture(username, file_data)

                if success:

                    response = {"success": True}

                else:

                    response = {"success": False, "message": "Failed to update profile picture"}
            elif action == "update_bio":
                with db_lock:
                    success = db.update_bio(
                        request.get("username"),
                        request.get("bio")
                    )

                print(success)

                if success:
                    response = {"success": True}
                else:
                    response = {
                        "success": False,
                        "message": "Failed to update bio"
                    }
            elif action == "get_challenges":
                # Fetch challenges for a specific user
                username = request.get("username")
                with db_lock:
                    challenges = db.get_challenges(username)  # Implement this in your DB layer
                if not challenges:
                    response = {"success": False, "message": "No challenges found"}
                else:
                    # Return as a list of dicts with completed/total
                    response = {"success": True, "challenges": challenges}


            elif action == "send_friend_request":
                with db_lock:
                    success, msg = db.send_friend_request(

                        request.get("from_user"),

                        request.get("to_user")

                    )

                response = {

                    "success": success,

                    "message": msg

                }

            elif action == "get_pending_requests":
                with db_lock:
                    requests = db.get_pending_requests(
                        request.get("username")
                    )

                response = {
                    "success": True,
                    "requests": requests
                }
            elif action == "accept_friend_request":
                print(request.get("from_V user"))
                with db_lock:
                    success = db.accept_friend_request(
                        request.get("from_user"),
                        request.get("to_user")
                    )


                response = {"success": success}
            elif action == "decline_friend_request":
                with db_lock:
                    db.decline_friend_request(
                        request.get("from_user"),
                        request.get("to_user")
                    )

                response = {"success": True}


            elif action == "get_friends_list":
                with db_lock:
                    friends = db.get_friends_list(

                        request.get("username"),

                        online_users

                    )

                response = {

                    "success": True,

                    "friends": friends

                }
            elif action == "send_message":
                from_user = request.get("from_user")
                to_user = request.get("to_user")
                message = request.get("message")

                if from_user and to_user and message:
                    with db_lock:
                        success = db.send_message(from_user, to_user, message)
                    response = {"success": success}
                else:
                    response = {"success": False, "message": "Invalid parameters"}

            elif action == "get_messages":
                username = request.get("username")
                friend_username = request.get("friend_username")

                if username and friend_username:
                    messages = db.get_messages(username, friend_username)
                    response = {"success": True, "messages": messages}
                else:
                    response = {"success": False, "messages": []}
            elif action == "end_turn":
                response = end_turn(
                    request.get("username"),
                    request.get("game_code")
                )
            elif action == "roll_dice":
                response = roll_dice(
                    request.get("username"),
                    request.get("game_code")
                )
            elif action == "upgrade_city":
                response = upgrade_city(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("position")
                )
            elif action == "move_robber":
                response = move_robber(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("position")
                )
            elif action == "steal_from_player":
                response = steal_from_player(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("target")
                )

            elif action == "buy_dev_card":
                response = buy_dev_card(
                    request.get("username"),
                    request.get("game_code")
                )

            elif action == "use_dev_card":
                response = use_dev_card(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("card")
                )
            elif action == "choose_monopoly":
                response = choose_monopoly(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("resource")
                )
            elif action == "choose_year_of_plenty":
                response = choose_year_of_plenty(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("resource")
                )
            elif action == "trade_with_bank":
                response = trade_with_bank(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("give_resource"),
                    request.get("receive_resource")
                )
            elif action == "create_trade":
                response = create_trade(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("to_player"),
                    request.get("offer"),
                    request.get("request")
                )

            elif action == "respond_trade":
                response = respond_trade(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("trade_id"),
                    request.get("accept")
                )

            elif action == "confirm_trade":
                response = confirm_trade(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("trade_id")
                )
            elif action == "discard_cards":
                response = discard_cards(
                    request.get("username"),
                    request.get("game_code"),
                    request.get("discard_dict")
                )

            send_msg(client_socket, response)

    except Exception as e:
        print("[CLIENT ERROR]", e)
    finally:
        if username:
            with online_lock:
                online_users.discard(username)
        client_socket.close()


# =====================
# Main server loop
# =====================
def main():
    init_db()   # ✅ SAFE
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDR)
    server.listen()
    print(f"[SERVER] Listening on {HOST}:{PORT}")

    while True:
        client, addr = server.accept()
        print("[CONNECTED]", addr)
        threading.Thread(
            target=handle_client,
            args=(client,),
            daemon=True
        ).start()


if __name__ == "__main__":
    main()