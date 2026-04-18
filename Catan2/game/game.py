import pygame
import threading
import time
import math
from Catan2.game.Board import render_map, load_resource_icons
import random
import io
import pygame
# =====================
# WINDOW CONFIG
# =====================
W, H = 1820, 980
BG_COLOR = (24, 22, 18)


def normalize(p):
    return (round(p[0], 1), round(p[1], 1))
class CatanGame:
    def __init__(self, client, username, game_code, parent_window=None):
        pygame.init()
        self.W = W
        self.H = H
        self.parent_window = parent_window
        self.current_turn = None
        self.client = client
        self.username = username
        self.game_code = game_code
        self.running = True
        self.player_resources = {}
        self.player_rects = {}
        self.hovered_road = None
        self.dice = {"rolling": False, "result": None}
        self.roll_button = pygame.Rect(W // 2 - 80, H - 80, 160, 50)
        self.dice_animation = (1, 1)
        # -----------------------------
        # WINDOW
        # -----------------------------
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Catan")
        self.clock = pygame.time.Clock()
        self.last_settlement = " "
        # -----------------------------
        # GAME STATE
        # -----------------------------
        self.game_over_screen = False
        self.winner = None
        self.largest_army_owner = None
        self.longest_road_owner = None
        self.game_stats = {}
        self.lobby_button_rect = pygame.Rect(700, 800, 400, 80)
        self.hexagon_positions = []
        self.hexagon_resources = {}
        self.hexagon_numbers = {}
        self.settlements = {}
        self.cities = {}
        self.placed_roads = {}
        self.phase = None
        self.current_turn = None
        self.my_turn = False
        self.robber_pos = None
        self.robber_active = False
        self.robber_already_moved = False
        self.show_robber_select = False
        self.ports = []
        self.monopoly_selecting = False
        self.monopoly_selecting = False
        self.year_of_plenty_selecting = False
        self.yop_remaining = 0
        self.player_points = {}
        self.steal_selecting = False
        self.steal_targets = []
        self.player_pfps = {}  # username -> pygame.Surface
        self.trade_offers = []  # incoming trades
        self.active_trade = None  # trade you are creating
        self.trade_ui_open = False
        self.trade_create_mode = False
        self.player_trade_give_amount = 0
        self.player_trade_receive_amount = 0
        self.trade_response_pending = None
        self.trade_response_menu = False
        self.discard_required = {}
        self.my_discard_amount = 0
        self.discarding = False
        self.discard_selection = {
            "wood": 0,
            "brick": 0,
            "wheat": 0,
            "wool": 0,
            "ore": 0
        }
        self.discard_submitted = {}
        self.discard_buttons = {}
        self.discard_plus_buttons = {}
        self.discard_minus_buttons = {}
        self.discard_confirm_rect = None
        self.discard_flash = None
        # =========================
        # TRADE UI STATE
        # =========================
        self.player_trade_menu_open = False

        self.player_trade_give = None
        self.player_trade_receive = None
        self.trade_target = None

        self.trades = {}
        self.incoming_trades = []
        self.outgoing_trades = []

        # UI rects (initialized later)

        self.player_trade_button = pygame.Rect(50, 100, 150, 50)
        self.trade_confirm_rect = None

        self.accept_trade_rect = None
        self.decline_trade_rect = None
        self.final_confirm_rect = None
        # -----------------------------
        # RENDER DATA
        # -----------------------------

        self.resource_icons = load_resource_icons()
        self.player_colors = {}
        self.dev_card_rects = {}
        self.buy_dev_card_rect = None
        self.selected_dev_card = None
        self.road_button_rect = pygame.Rect(270, H - 80, 200, 50)
        self.end_turn_button = pygame.Rect(W - 250, H - 80, 200, 50)
        self.city_button_rect = pygame.Rect(500, H - 80, 200, 50)
        self.dev_card_button_rect = pygame.Rect(730, H - 80, 200, 50)
        self.trade_button = pygame.Rect(50, 200, 160, 50)
        self.bank_trade_confirm_rect = pygame.Rect(420, 550, 150, 50)
        self.longest_road_img = pygame.image.load("Images/game/longest_road.png").convert_alpha()
        self.largest_army_img = pygame.image.load("Images/game/largest_army.png").convert_alpha()

        # optional resize
        self.longest_road_img = pygame.transform.smoothscale(self.longest_road_img, (52, 52))
        self.largest_army_img = pygame.transform.smoothscale(self.largest_army_img, (52, 52))
        self.trade_offer_give = {}
        self.trade_offer_receive = {}
        self.trade_selected_target = None
        self.trade_buttons = []
        self.trade_menu_open = False
        self.trade_give = None
        self.trade_receive = None
        self.show_dev_cards = False
        self.selected_dev_card = None
        self.show_road_spots = False
        self.show_city_spots = False
        self.valid_spots = set()
        self.valid_roads = set()
        self.road_error_message = ""
        self.road_error_time = 0
        self.road_error_type = None
        self.road_error_message = ""
        self.dev_card_error = ""
        self.dev_card_error_time = 0
        self.missing_resources = []
        self.longest_road_popup = None
        self.longest_road_popup_time = 0
        pygame.init()
        pygame.font.init()
        self.font = pygame.font.Font(None, 32)
        # -----------------------------
        # INITIAL FETCH
        # -----------------------------
        self.fetch_initial_state()
        self.fetch_player_profiles()
        # -----------------------------
        # SYNC THREAD
        # -----------------------------
        threading.Thread(
            target=self.sync_loop,
            daemon=True
        ).start()

    # ==================================================
    # RESOURCE COLORS
    # ==================================================

    def resource_colors(self):
        return {
            "wood": (34, 139, 34),
            "brick": (178, 34, 34),
            "ore": (128, 128, 128),
            "wheat": (255, 215, 0),
            "wool": (245, 245, 245),
            "desert": (210, 180, 140),
        }

    # ==================================================
    # INITIAL STATE
    # ==================================================

    def fetch_initial_state(self):
        try:

            r = self.client.send_request(
                "game_state",
                game_code=self.game_code
            )

            if not r or not r.get("success"):
                raise RuntimeError("Failed to fetch initial game state")

            self.hexagon_positions = r.get("hexagon_positions", [])
            self.player_resources = r.get("player_resources", {})
            self.hexagon_resources = {
                tuple(map(float, k)): v
                for k, v in r.get("hexagon_resources", {}).items()
            }

            self.hexagon_numbers = {
                tuple(map(float, k)): v
                for k, v in r.get("hexagon_numbers", {}).items()
            }

            self.settlements = {
                tuple(map(float, k)): v
                for k, v in r.get("settlements", {}).items()
            }

            self.current_turn = r.get("current_turn")
            self.my_turn = (self.current_turn == self.username)
            self.ports = r.get("ports", [])
            self.player_colors = r.get("player_colors", {})
            for user, res in self.player_resources.items():
                dev_list = res.get("dev_cards", [])
                res["dev_cards_raw"] = dev_list  # keep raw list
            if "trades" in r:
                self.trades = r["trades"]

                self.incoming_trades = [
                    t for t in self.trades.values()
                    if t["to"] == self.username and t["status"] == "pending"
                ]

                self.outgoing_trades = [
                    t for t in self.trades.values()
                    if t["from"] == self.username and t["status"] == "accepted"
                ]
        except Exception as e:
            print("[FETCH STATE ERROR]", e)
            self.running = False

    # ==================================================
    # SERVER SYNC LOOP
    # ==================================================

    def sync_loop(self):

        while self.running:

            try:

                r = self.client.send_request(
                    "game_state",
                    game_code=self.game_code
                )

                if not r or not r.get("success"):
                    time.sleep(0.3)
                    continue

                if "settlements" in r:
                    self.settlements = {
                        tuple(map(float, k)): v
                        for k, v in r["settlements"].items()
                    }

                if "current_turn" in r:
                    self.current_turn = r["current_turn"]
                    self.my_turn = (self.current_turn == self.username)

                if "player_colors" in r:
                    self.player_colors = r["player_colors"]

                if "roads" in r:
                    self.placed_roads = {
                        tuple(tuple(map(float, p)) for p in edge): owner
                        for edge, owner in r["roads"].items()
                    }
                if "player_resources" in r:
                    self.player_resources = r["player_resources"]

                    for user, res in self.player_resources.items():
                        dev_list = res.get("dev_cards", [])
                        res["dev_cards_raw"] = dev_list
                        res["dev_cards"] = self.count_dev_cards(dev_list)
                if "phase" in r:
                    self.phase = r["phase"]
                if "dice" in r:
                    self.dice = r["dice"]
                if "cities" in r:
                    self.cities = {
                        tuple(map(float, k)): v
                        for k, v in r["cities"].items()
                    }
                if "robber_pos" in r:
                    self.robber_pos = tuple(map(float, r["robber_pos"]))

                if r.get("robber_active") and self.my_turn:
                    if not self.show_robber_select and not self.steal_selecting and not self.robber_already_moved:
                        self.show_robber_select = True
                if "victory_points" in r:
                    self.player_points = r["victory_points"]
                    print("POINTS UPDATE:", r.get("victory_points"))
                if "ports" in r:
                    self.ports = r["ports"]
                if "trades" in r:
                    self.trades = r["trades"]

                    # =========================
                    # INCOMING (you are receiver)
                    # =========================
                    self.incoming_trades = [
                        t for t in self.trades.values()
                        if t["to"] == self.username and t["status"] == "pending"
                    ]

                    # =========================
                    # OUTGOING (you are sender, waiting confirm)
                    # =========================
                    self.outgoing_trades = [
                        t for t in self.trades.values()
                        if t["from"] == self.username and t["status"] == "accepted"
                    ]
                if "trades" in r:
                    print("TRADES UPDATE:", r["trades"])
                if "robber_pending_steal" in r:
                    pending = r["robber_pending_steal"]

                    if pending and pending.get("by") == self.username:
                        self.steal_selecting = True
                        self.steal_targets = pending.get("targets", [])
                    else:
                        self.steal_selecting = False
                        self.steal_targets = []
                if "discard_required" in r:

                    self.discard_required = r.get("discard_required") or {}
                    print(f"self.discard_required :  {self.discard_required}")
                    self.my_discard_amount = self.discard_required.get(self.username, 0)
                    print(f"self.my_discard_amount :  {self.my_discard_amount}")
                    self.discarding = self.my_discard_amount > 0 and r["discard_required"].get(self.username, 0) > 0
                    print(f"self.discarding : {self.discarding}")
                if "discard_submitted" in r:
                    self.discard_submitted = r["discard_submitted"]
                if "winner" in r and r["winner"] and not self.game_over_screen:
                    self.winner = r["winner"]
                    self.game_over_screen = True
                if "largest_army" in r:
                    self.largest_army_owner = r["largest_army"]

                if "longest_road" in r:
                    self.longest_road_owner = r["longest_road"]

                    self.game_stats = self.build_game_stats(r)

                    print("GAME OVER STATS:")
                    print(self.game_stats)

            except Exception as e:
                print("[SYNC ERROR]", e)

            time.sleep(0.2)

    def build_game_stats(self, r):

        settlements = {}
        cities = {}
        points = r.get("victory_points", {})
        largest_army = r.get("largest_army_owner")
        vp_dev_cards = r.get("vp_dev_cards", {})
        print("largest army owner")
        print(largest_army)
        # =========================
        # COUNT SETTLEMENTS
        # =========================
        for pos, owner in r.get("settlements", {}).items():
            settlements[owner] = settlements.get(owner, 0) + 1

        # =========================
        # COUNT CITIES
        # =========================
        for pos, owner in r.get("cities", {}).items():
            cities[owner] = cities.get(owner, 0) + 1

        # =========================
        # TURN + TIME INFO
        # =========================
        total_turns = r.get("turn_number", 0)

        start_time = r.get("start_time", None)
        end_time = time.time()

        duration = None
        if start_time and end_time:
            duration = end_time - start_time

        # =========================
        # BUILD PER PLAYER BREAKDOWN
        # =========================
        players = set(list(points.keys()) + list(settlements.keys()) + list(cities.keys()))

        breakdown = {}

        for p in players:
            settlement_count = settlements.get(p, 0)
            city_count = cities.get(p, 0)
            vp = points.get(p, 0)
            vp_dev = vp_dev_cards.get(p, 0)

            breakdown[p] = {
                "points": vp,
                "settlements": settlement_count,
                "cities": city_count,
                "vp_dev_cards": vp_dev,
                "army": 1 if largest_army == p else 0
            }

        return {
            "breakdown": breakdown,
            "largest_army": largest_army,
            "turns": total_turns,
            "duration": duration
        }
    # ==================================================
    # SETTLEMENT
    # ==================================================

    def try_place_settlement(self, mouse_pos):

        if not self.my_turn:
            return

        for spot in self.valid_spots:

            if pygame.math.Vector2(spot).distance_to(mouse_pos) < 20:
                try:
                    self.client.send_request(
                        "place_settlement",
                        username=self.username,
                        game_code=self.game_code,
                        position=spot
                    )

                    self.last_settlement = spot

                    return
                except Exception as e:
                    print(e)


    # ==================================================
    # ROAD
    # ==================================================

    def try_place_road(self, mouse_pos):

        if not self.hovered_road:
            return {"success": False, "error": "no_selection"}

        a, b = self.hovered_road
        edge = (normalize(a), normalize(b))

        if edge not in self.valid_roads:
            return {"success": False, "error": "invalid_location"}

        try:
            response = self.client.send_request(
                "place_road",
                username=self.username,
                game_code=self.game_code,
                edge=edge
            )

            if not response:
                return {"success": False, "error": "empty_response"}

            if not response.get("success"):
                return {
                    "success": False,
                    "error": response.get("error", "unknown_error")
                }

            data = response.get("longest_road_update")

            if data:
                self.longest_road_owner = data.get("longest_road_owner")
                self.largest_army_owner = data.get("largest_army_owner")  # if you send it later

            # safe check
            if data and isinstance(data, dict):
                new_owner = data.get("longest_road_owner")
                prev_owner = data.get("previous_owner")

                if new_owner and new_owner != prev_owner:
                    self.longest_road_popup = {
                        "owner": new_owner,
                        "previous": prev_owner,
                        "length": data.get("longest_road_length", 0)
                    }
                    self.longest_road_popup_time = time.time()

            self.show_road_spots = False
            self.hovered_road = None

            return response

        except Exception as e:
            print("[ROAD PLACE ERROR]", e)
            return {"success": False, "error": "network_error"}

    def draw_longest_road_popup(self, surface):
        if not self.longest_road_popup:
            return

        # auto disappear after 3 seconds
        if time.time() - self.longest_road_popup_time > 3:
            self.longest_road_popup = None
            return

        data = self.longest_road_popup

        # =========================
        # BACKGROUND BOX
        # =========================
        rect = pygame.Rect(500, 300, 800, 250)

        alpha = min(255, int((time.time() - self.longest_road_popup_time) * 400))

        popup_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        popup_surface.fill((40, 30, 20, alpha))

        surface.blit(popup_surface, rect.topleft)
        pygame.draw.rect(surface, (200, 170, 120), rect, 4, border_radius=15)

        # =========================
        # TITLE
        # =========================
        font_big = pygame.font.Font(None, 60)
        title = font_big.render("LONGEST ROAD!", True, (255, 215, 0))
        surface.blit(title, title.get_rect(center=(rect.centerx, rect.y + 50)))

        # =========================
        # MESSAGE
        # =========================
        font_mid = pygame.font.Font(None, 40)

        owner = data["owner"]
        prev = data["previous"]
        length = data["length"]

        if prev and prev != owner:
            msg = f"{owner} took Longest Road from {prev}!"
        else:
            msg = f"{owner} now has the Longest Road!"

        text = font_mid.render(msg, True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=(rect.centerx, rect.y + 120)))

        # =========================
        # LENGTH + POINTS
        # =========================
        font_small = pygame.font.Font(None, 32)

        info = f"Length: {length}   (+2 Victory Points)"
        info_text = font_small.render(info, True, (220, 220, 220))
        surface.blit(info_text, info_text.get_rect(center=(rect.centerx, rect.y + 180)))
    def try_upgrade_city(self, mouse_pos):

        if not self.my_turn:
            return

        for pos, owner in self.settlements.items():
            if owner != self.username:
                continue

            if pygame.math.Vector2(pos).distance_to(mouse_pos) < 20:
                try:
                    response = self.client.send_request(
                        "upgrade_city",
                        username=self.username,
                        game_code=self.game_code,
                        position=pos
                    )

                    print("city response:", response)

                    if response.get("success"):
                        self.show_city_spots = False  # exit mode

                    return
                except Exception as e:
                    print(e)

    def draw_city_previews(self, surface):

        if not self.show_city_spots:
            return

        for pos, owner in self.settlements.items():
            if owner == self.username:
                pygame.draw.circle(surface, (255, 255, 100), pos, 18, 3)
    # ==================================================
    # DRAW ROADS
    # ==================================================

    def draw_placed_roads(self, surface):

        for edge, owner in self.placed_roads.items():

            a, b = normalize(edge[0]), normalize(edge[1])
            color = self.player_colors.get(owner, (200, 200, 200))

            pygame.draw.line(surface, color, a, b, 12)

    def draw_road_previews(self, surface):

        if not self.show_road_spots:
            return

        mouse = pygame.mouse.get_pos()
        self.hovered_road = None

        closest_edge = None
        closest_dist = float("inf")

        for edge in self.valid_roads:
            a, b = edge

            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            d = math.dist(mid, mouse)

            if d < 40 and d < closest_dist:
                closest_dist = d
                closest_edge = edge

        self.hovered_road = closest_edge

        for edge in self.valid_roads:

            a, b = edge

            if edge == self.hovered_road:

                pygame.draw.line(surface, (255, 255, 200), a, b, 16)
                pygame.draw.line(surface, (255, 220, 120), a, b, 10)

            else:

                pygame.draw.line(surface, (180, 180, 180), a, b, 4)

    # ==================================================
    # DICE
    # ==================================================
    import pygame
    import math
    import random
    import time

    def play_dice_roll_overlay(self,screen, clock, dice_result=None, width=1820, height=980):
        """
        Plays a full-screen dice roll animation:
          1. Dims the screen (fade to dark)
          2. Animates two rolling dice
          3. Shows the final result
          4. Fades back in (undims)

        Args:
            screen: the pygame display surface
            clock: pygame clock for tick control
            dice_result: (d1, d2) tuple for final result. If None, picks randomly.
            width, height: screen dimensions
        """
        print("play_dice_roll_overlay")
        print(dice_result)
        if dice_result is None:
            return

        # ── dot layouts per face value ──────────────────────────────────────────
        DOT_LAYOUTS = {
            1: [(0.5, 0.5)],
            2: [(0.25, 0.25), (0.75, 0.75)],
            3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
            4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
            5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
            6: [(0.25, 0.2), (0.75, 0.2), (0.25, 0.5), (0.75, 0.5), (0.25, 0.8), (0.75, 0.8)],
        }

        def draw_die(surface, cx, cy, size, value, alpha=255, angle=0.0):
            """Draw a single die centered at (cx, cy)."""
            die_surf = pygame.Surface((size, size), pygame.SRCALPHA)

            # body
            body_color = (245, 240, 225, alpha)
            border_color = (80, 60, 40, alpha)
            pygame.draw.rect(die_surf, body_color, (0, 0, size, size), border_radius=size // 8)
            pygame.draw.rect(die_surf, border_color, (0, 0, size, size), 3, border_radius=size // 8)

            # dots
            dot_radius = max(4, size // 12)
            dot_color = (40, 30, 20, alpha)
            for rx, ry in DOT_LAYOUTS.get(value, []):
                dx = int(rx * size)
                dy = int(ry * size)
                pygame.draw.circle(die_surf, dot_color, (dx, dy), dot_radius)

            # rotate
            rotated = pygame.transform.rotate(die_surf, angle)
            rect = rotated.get_rect(center=(cx, cy))
            surface.blit(rotated, rect)

        def draw_overlay_frame(dim_alpha, d1_val, d2_val, die_angle, die_offset_y, result_alpha):
            """Composite one frame onto the screen."""
            # dim layer
            dim = pygame.Surface((width, height), pygame.SRCALPHA)
            dim.fill((0, 0, 0, int(dim_alpha)))
            screen.blit(dim, (0, 0))

            cx = width // 2
            cy = height // 2 + int(die_offset_y)
            die_size = 120
            gap = 80

            draw_die(screen, cx - gap, cy, die_size, d1_val, angle=die_angle)
            draw_die(screen, cx + gap, cy, die_size, d2_val, angle=-die_angle)

            # show total when fading in result
            if result_alpha > 0:
                font = pygame.font.Font(None, 72)
                total = dice_result[0] + dice_result[1]
                label = font.render(f"{total}", True, (255, 220, 100))
                label.set_alpha(int(result_alpha))
                label_rect = label.get_rect(center=(cx, cy + 120))
                screen.blit(label, label_rect)

                sub_font = pygame.font.Font(None, 36)
                sub = sub_font.render("total", True, (200, 180, 140))
                sub.set_alpha(int(result_alpha))
                screen.blit(sub, sub.get_rect(center=(cx, cy + 165)))

        # ── Phase timings (seconds) ─────────────────────────────────────────────
        FADE_IN_DIM = 0.25  # screen dims
        ROLL_DURATION = 1.2  # dice spinning
        SETTLE = 0.3  # dice slow to final value
        RESULT_SHOW = 0.4  # result label fades in
        HOLD = 0.6  # hold on result
        FADE_OUT_DIM = 0.35  # screen brightens

        total_time = FADE_IN_DIM + ROLL_DURATION + SETTLE + RESULT_SHOW + HOLD + FADE_OUT_DIM

        start = time.time()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return  # let caller handle quit

            elapsed = time.time() - start
            if elapsed >= total_time:
                break

            # ── compute per-phase values ────────────────────────────────────────
            t = elapsed

            # dim alpha  (0 → 180 during fade-in, stays 180, 180 → 0 during fade-out)
            fade_out_start = total_time - FADE_OUT_DIM
            if t < FADE_IN_DIM:
                dim_alpha = 180 * (t / FADE_IN_DIM)
            elif t > fade_out_start:
                dim_alpha = 180 * (1.0 - (t - fade_out_start) / FADE_OUT_DIM)
            else:
                dim_alpha = 180

            # rolling phase
            roll_start = FADE_IN_DIM
            roll_end = FADE_IN_DIM + ROLL_DURATION

            if t < roll_start:
                d1_val, d2_val = random.randint(1, 6), random.randint(1, 6)
                die_angle = 0
                die_offset_y = 0
            elif t < roll_end:
                roll_t = (t - roll_start) / ROLL_DURATION
                # rapid random faces during roll
                d1_val = random.randint(1, 6)
                d2_val = random.randint(1, 6)
                die_angle = math.sin(roll_t * math.pi * 8) * 35  # wobble
                die_offset_y = math.sin(roll_t * math.pi * 3) * 18  # bounce
            elif t < roll_end + SETTLE:
                settle_t = (t - roll_end) / SETTLE
                # ease into final values
                if settle_t < 0.5:
                    d1_val = random.randint(1, 6)
                    d2_val = random.randint(1, 6)
                else:
                    d1_val, d2_val = dice_result
                die_angle = math.sin((1 - settle_t) * math.pi * 2) * 15 * (1 - settle_t)
                die_offset_y = 0
            else:
                d1_val, d2_val = dice_result
                die_angle = 0
                die_offset_y = 0

            # result fade-in alpha
            result_start = roll_end + SETTLE
            result_end = result_start + RESULT_SHOW
            if t < result_start:
                result_alpha = 0
            elif t < result_end:
                result_alpha = 255 * ((t - result_start) / RESULT_SHOW)
            elif t < fade_out_start:
                result_alpha = 255
            else:
                result_alpha = 255 * (1.0 - (t - fade_out_start) / FADE_OUT_DIM)

            draw_overlay_frame(dim_alpha, d1_val, d2_val, die_angle, die_offset_y, result_alpha)
            pygame.display.flip()
            clock.tick(60)

    def roll_dice(self):
        if not self.my_turn:
            return

        response = self.client.send_request(
            "roll_dice",
            username=self.username,
            game_code=self.game_code
        )

        # 🔥 SAFETY CHECK (CRITICAL)
        if not response:
            print("[ERROR] No response from server")
            return

        if not response.get("success"):
            print("[ERROR]", response.get("message"))
            return

        result = response.get("dice")

        if result:
            self.play_dice_roll_overlay(self.screen, self.clock, dice_result=result)

        # =========================
        # 🔥 FIX: DON'T TRIGGER ROBBER HERE
        # =========================
        if response.get("discard_phase"):
            print("Entering discard phase")
            self.show_robber_select = False
            return

        if response.get("robber"):
            print("Robber active")
            self.show_robber_select = True
            self.steal_selecting = False
            self.steal_targets = []
        #print(response)
       # if response:
       #     print( response and response.get("dice"))
       #     if response and response.get("dice") == True:
       #         print("hello")
       #         result = response["dice"]
       #         print(type(response["dice"]))
        #    self.play_dice_roll_overlay(self.screen, self.clock, dice_result=result)
    # ==================================================
    # NODES
    # ==================================================

    def get_my_nodes(self):
        nodes = set()

        # settlements
        for pos, owner in self.settlements.items():
            if owner == self.username:
                nodes.add(normalize(pos))

        # 🔥 ADD THIS — cities
        for pos, owner in self.cities.items():
            if owner == self.username:
                nodes.add(normalize(pos))

        # roads
        for (a, b), owner in self.placed_roads.items():
            if owner == self.username:
                nodes.add(normalize(a))
                nodes.add(normalize(b))

        return nodes

    def count_dev_cards(self, dev_card_list):
        counts = {
            "knight": 0,
            "victory_point": 0,
            "monopoly": 0,
            "road_building": 0,
            "year_of_plenty": 0
        }

        for card in dev_card_list:
            counts[card["type"]] += 1

        return counts

    # ==================================================
    # PLAYERS PANEL
    # ==================================================

    def load_pfp_surface(self, blob):

        if not blob:
            return None

        try:
            # 🔥 FORCE correct type
            if isinstance(blob, memoryview):
                blob = blob.tobytes()

            if isinstance(blob, str):
                blob = blob.encode()

            import io
            image = pygame.image.load(io.BytesIO(blob)).convert_alpha()

            return pygame.transform.smoothscale(image, (28, 28))

        except Exception as e:
            print("[PFP LOAD ERROR]", e)
            return None

    def fetch_player_profiles(self):
        print("hello")
        for username in self.player_colors.keys():
            try:
                response = self.client.send_request(
                    "get_profile",
                    username=username
                )

                if not response or not response.get("success"):
                    continue

                profile = response.get("profile", {})
                blob = profile.get("profile_picture_data")
                print(blob)
                self.player_pfps[username] = self.load_pfp_surface(blob)
            except Exception as e:
                print(e)

    def draw_end_turn_button(self, surface):
        mouse = pygame.mouse.get_pos()

        color = (80, 140, 80) if self.end_turn_button.collidepoint(mouse) else (60, 110, 60)

        pygame.draw.rect(surface, color, self.end_turn_button, border_radius=8)

        font = pygame.font.Font(None, 28)
        text = font.render("End Turn", True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=self.end_turn_button.center))

    def draw_players_panel(self, surface):
        mouse_pos = pygame.mouse.get_pos()

        panel_rect = pygame.Rect(W - 320, 10, 310, 260)

        pygame.draw.rect(surface, (25, 20, 15), panel_rect, border_radius=14)
        pygame.draw.rect(surface, (46, 36, 24), panel_rect, 1, border_radius=14)

        small_font = pygame.font.Font(None, 20)
        font = pygame.font.Font(None, 24)

        x_start = W - 305
        y = 22

        # Header
        header_font = pygame.font.Font(None, 19)
        header = header_font.render("PLAYERS", True, (107, 90, 66))
        surface.blit(header, (x_start, y))

        round_text = header_font.render(f"{self.current_turn}'s turn", True, (90, 74, 52))
        surface.blit(round_text, (panel_rect.right - round_text.get_width() - 14, y))

        y += 22
        pygame.draw.line(surface, (46, 36, 24), (x_start, y), (panel_rect.right - 14, y), 1)
        y += 10

        self.player_rects.clear()

        for username in self.player_colors.keys():

            # =========================
            # PLAYER STATE
            # =========================
            is_active = (username == self.current_turn)
            points = self.player_points.get(username, 0)
            player_color = self.player_colors[username]

            # =========================
            # ROW RECT
            # =========================
            row_rect = pygame.Rect(x_start - 6, y - 4, 298, 44)

            if is_active:
                pygame.draw.rect(surface, (18, 32, 14), row_rect, border_radius=10)
                pygame.draw.rect(surface, (40, 90, 30), row_rect, 1, border_radius=10)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (38, 32, 24), row_rect, border_radius=10)

            # =========================
            # PROFILE PICTURE + COLOR DOT OVERLAY
            # =========================
            pfp = self.player_pfps.get(username)
            pfp_size = 32
            pfp_x = x_start
            pfp_y = y + 2
            center = (pfp_x + pfp_size // 2, pfp_y + pfp_size // 2)

            ring_color = (100, 220, 60) if is_active else (60, 50, 38)
            pygame.draw.circle(surface, ring_color, center, pfp_size // 2 + 2)
            pygame.draw.circle(surface, (25, 20, 15), center, pfp_size // 2)

            pfp_rect = pygame.Rect(pfp_x, pfp_y, pfp_size, pfp_size)
            if pfp:
                pfp_img = pygame.transform.smoothscale(pfp, (pfp_size, pfp_size))
                surface.blit(pfp_img, pfp_rect)
            else:
                initials_surf = font.render(username[0].upper(), True, (160, 140, 110))
                surface.blit(initials_surf, initials_surf.get_rect(center=center))

            # Color dot — bottom-right of avatar
            dot_x = pfp_x + pfp_size - 3
            dot_y = pfp_y + pfp_size - 3
            pygame.draw.circle(surface, (25, 20, 15), (dot_x, dot_y), 6)
            pygame.draw.circle(surface, player_color, (dot_x, dot_y), 5)

            # =========================
            # USERNAME + VP
            # =========================
            text_x = x_start + pfp_size + 10
            text_color = (160, 255, 120) if is_active else (200, 185, 165)
            vp_color = (106, 255, 106) if is_active else (138, 122, 106)

            name_surf = font.render(username, True, text_color)
            surface.blit(name_surf, (text_x, y + 3))

            sep_x = text_x + name_surf.get_width() + 6
            pygame.draw.circle(surface, (74, 58, 42), (sep_x, y + 11), 3)

            vp_surf = small_font.render(f"{points} VP", True, vp_color)
            surface.blit(vp_surf, (sep_x + 8, y + 4))

            # =========================
            # VP PROGRESS BAR
            # =========================
            bar_y = y + 28
            bar_x = text_x
            bar_w = 150
            bar_h = 3
            bar_fill = int(bar_w * min(points / 10.0, 1.0))

            pygame.draw.rect(surface, (22, 18, 13), pygame.Rect(bar_x, bar_y, bar_w, bar_h), border_radius=2)
            if bar_fill > 0:
                fill_color = (100, 220, 60) if is_active else player_color
                pygame.draw.rect(surface, fill_color, pygame.Rect(bar_x, bar_y, bar_fill, bar_h), border_radius=2)

            # =========================
            # BADGES
            # =========================
            label_font = pygame.font.Font(None, 16)

            has_road = (username == getattr(self, "longest_road_owner", None))
            has_army = (username == getattr(self, "largest_army_owner", None))

            road_label_surf = label_font.render("Road", True, (160, 130, 60))
            army_label_surf = label_font.render("Army", True, (160, 130, 60))
            road_pill_w = 16 + road_label_surf.get_width() + 10
            army_pill_w = 16 + army_label_surf.get_width() + 10

            gap = 6
            total_badge_w = 0
            if has_road:
                total_badge_w += road_pill_w
            if has_army:
                total_badge_w += army_pill_w
            if has_road and has_army:
                total_badge_w += gap

            badge_x = row_rect.right - total_badge_w - 10

            if has_road:
                self.draw_badge(surface, self.longest_road_img, "Road", badge_x, y + 18)
                badge_x += road_pill_w + gap

            if has_army:
                self.draw_badge(surface, self.largest_army_img, "Army", badge_x, y + 18)

            # =========================
            # ACTIVE TURN INDICATOR DOT
            # =========================
            if is_active:
                pygame.draw.circle(surface, (100, 255, 100), (row_rect.right - 10, row_rect.centery), 4)

            # =========================
            # STORE CLICK AREA
            # =========================
            self.player_rects[username] = row_rect

            y += 48

        # =========================
        # FOOTER
        # =========================
        footer_y = panel_rect.bottom - 22
        pygame.draw.line(surface, (46, 36, 24), (x_start, footer_y), (panel_rect.right - 14, footer_y), 1)
        footer_surf = small_font.render("10 points to win", True, (80, 65, 48))
        surface.blit(footer_surf, (x_start, footer_y + 6))

    def draw_badge(self, surface, img, label, x, y):
        if img is None:
            return

        icon_size = 24
        label_font = pygame.font.Font(None, 16)
        label_surf = label_font.render(label, True, (160, 130, 60))
        pill_w = icon_size + label_surf.get_width() + 12
        pill_h = 24

        pill_rect = pygame.Rect(x, y - pill_h // 2, pill_w, pill_h)
        pygame.draw.rect(surface, (35, 28, 14), pill_rect, border_radius=5)
        pygame.draw.rect(surface, (80, 60, 20), pill_rect, 1, border_radius=5)

        small_icon = pygame.transform.smoothscale(img, (icon_size, icon_size))
        surface.blit(small_icon, (x + 3, y - icon_size // 2))
        surface.blit(label_surf, (x + icon_size + 7, y - label_surf.get_height() // 2))
    # ==================================================
    # BUTTON
    # ==================================================

    def draw_buttons(self, surface):

        mouse = pygame.mouse.get_pos()

        # =========================
        # UI BAR BACKGROUND (modern panel)
        # =========================
        bar_rect = pygame.Rect(120, H - 120, W - 240, 100)

        # shadow
        shadow_rect = bar_rect.move(0, 4)
        pygame.draw.rect(surface, (10, 8, 6), shadow_rect, border_radius=16)

        # main bar
        pygame.draw.rect(surface, (30, 26, 22), bar_rect, border_radius=16)
        pygame.draw.rect(surface, (90, 75, 60), bar_rect, 2, border_radius=16)

        # =========================
        # BUTTON CONFIG
        # =========================
        BUTTON_Y = H - 105
        BUTTON_WIDTH = 170
        BUTTON_HEIGHT = 55
        GAP = 18
        START_X = 160

        font = pygame.font.Font(None, 30)
        small_font = pygame.font.Font(None, 24)

        # helper for hover scale effect
        def draw_button(rect, base_color, hover_color, text, text_color=(255, 255, 255)):
            is_hover = rect.collidepoint(mouse)

            color = hover_color if is_hover else base_color

            # shadow
            shadow = rect.move(0, 3)
            pygame.draw.rect(surface, (15, 12, 10), shadow, border_radius=10)

            # main button
            pygame.draw.rect(surface, color, rect, border_radius=10)
            pygame.draw.rect(surface, (0, 0, 0), rect, 1, border_radius=10)

            # text
            txt = font.render(text, True, text_color)
            surface.blit(txt, txt.get_rect(center=rect.center))

        # =========================
        # ROAD BUTTON
        # =========================
        road_rect = pygame.Rect(START_X, BUTTON_Y, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.road_button_rect = road_rect

        road_text = "Cancel Road" if self.show_road_spots else "Build Road"
        draw_button(
            road_rect,
            base_color=(120, 85, 55),
            hover_color=(170, 130, 85),
            text=road_text
        )

        # =========================
        # CITY BUTTON
        # =========================
        city_rect = pygame.Rect(
            START_X + (BUTTON_WIDTH + GAP),
            BUTTON_Y,
            BUTTON_WIDTH,
            BUTTON_HEIGHT
        )
        self.city_button_rect = city_rect

        draw_button(
            city_rect,
            base_color=(95, 70, 120),
            hover_color=(140, 110, 180),
            text="Build City"
        )

        # =========================
        # DEV CARD BUTTON
        # =========================
        dev_rect = pygame.Rect(
            START_X + 2 * (BUTTON_WIDTH + GAP),
            BUTTON_Y,
            BUTTON_WIDTH,
            BUTTON_HEIGHT
        )
        self.dev_card_button_rect = dev_rect

        draw_button(
            dev_rect,
            base_color=(70, 70, 120),
            hover_color=(110, 110, 180),
            text="Dev Cards"
        )

        # =========================
        # ROLL DICE BUTTON
        # =========================
        roll_rect = pygame.Rect(
            START_X + 3 * (BUTTON_WIDTH + GAP),
            BUTTON_Y,
            150,
            BUTTON_HEIGHT
        )
        self.roll_button = roll_rect

        draw_button(
            roll_rect,
            base_color=(150, 110, 60),
            hover_color=(210, 160, 90),
            text="Roll Dice"
        )

        # =========================
        # SMALL UI HINT (optional polish)
        # =========================
        hint = small_font.render("Actions", True, (180, 160, 130))
        surface.blit(hint, (bar_rect.x + 15, bar_rect.y + 10))

    def draw_resources_ui(self, surface):

        if self.username not in self.player_resources:
            return

        resources = self.player_resources[self.username]

        # =========================
        # PANEL (MOVED HIGHER to avoid bottom buttons)
        # =========================
        panel = pygame.Rect(20, H - 520, 340, 360)  # ⬅️ moved UP significantly

        # shadow
        shadow = panel.move(0, 5)
        pygame.draw.rect(surface, (10, 8, 6), shadow, border_radius=12)

        # main panel
        pygame.draw.rect(surface, (32, 28, 24), panel, border_radius=12)
        pygame.draw.rect(surface, (120, 95, 70), panel, 2, border_radius=12)

        font = pygame.font.Font(None, 26)
        title_font = pygame.font.Font(None, 34)
        small_font = pygame.font.Font(None, 22)

        # =========================
        # TITLE
        # =========================
        title = title_font.render("Resources", True, (255, 215, 150))
        surface.blit(title, (panel.x + 12, panel.y + 10))

        y = panel.y + 45
        x = panel.x + 15

        # =========================
        # RESOURCE LIST
        # =========================
        for res in ["wood", "brick", "ore", "wheat", "wool"]:
            amount = resources.get(res, 0)

            text = font.render(f"{res.capitalize()}: {amount}", True, (220, 220, 220))
            surface.blit(text, (x, y))

            pygame.draw.line(
                surface,
                (60, 55, 45),
                (x, y + 20),
                (panel.right - 15, y + 20),
                1
            )

            y += 26

        # =========================
        # HINT TEXT
        # =========================
        hint = small_font.render(
            "Click Dev Cards to use abilities",
            True,
            (180, 170, 150)
        )
        surface.blit(hint, (x, y + 5))

        y += 30

        # =========================
        # DEV CARDS SECTION
        # =========================
        dev_cards = resources.get("dev_cards") or {
            "knight": 0,
            "victory_point": 0,
            "monopoly": 0,
            "road_building": 0,
            "year_of_plenty": 0
        }

        title2 = title_font.render("Development Cards", True, (255, 215, 150))
        surface.blit(title2, (x, y))

        y += 30

        visible_cards = False

        for card in ["knight", "victory_point", "monopoly", "road_building", "year_of_plenty"]:

            amount = dev_cards.get(card, 0)

            if amount <= 0:
                continue

            visible_cards = True

            label = f"{card.replace('_', ' ').title()} x{amount}"
            color = (255, 230, 120) if self.selected_dev_card == card else (210, 210, 210)
            text = font.render(label, True, color)

            surface.blit(text, (x + 5, y))

            pygame.draw.rect(
                surface,
                (90, 80, 120),
                (x - 5, y + 6, 4, 14)
            )

            y += 24

        # fallback message if empty
        if not visible_cards:
            empty = small_font.render("No development cards", True, (120, 120, 120))
            surface.blit(empty, (x + 5, y))



    def draw_dev_cards_ui(self, surface):

        if not self.show_dev_cards:
            return

        if self.username not in self.player_resources:
            return
        if "dev_cards" not in self.player_resources[self.username]:
            return

        dev_cards = self.player_resources[self.username].get("dev_cards", {})

        panel = pygame.Rect(360, H - 300, 400, 220)
        pygame.draw.rect(surface, (30, 30, 50), panel, border_radius=10)
        pygame.draw.rect(surface, (120, 120, 200), panel, 2, border_radius=10)

        font = pygame.font.Font(None, 28)
        title = font.render("Select Dev Card to Use", True, (255, 255, 255))
        surface.blit(title, (panel.x + 10, panel.y + 10))

        y = panel.y + 50

        self.buy_dev_card_rect = pygame.Rect(panel.x + 20, panel.bottom - 50, 200, 35)

        pygame.draw.rect(surface, (80, 140, 80), self.buy_dev_card_rect, border_radius=6)
        buy_text = font.render("Buy Dev Card", True, (255, 255, 255))
        surface.blit(buy_text, buy_text.get_rect(center=self.buy_dev_card_rect.center))

        for card in ["knight", "victory_point", "monopoly", "road_building", "year_of_plenty"]:

            count = dev_cards.get(card, 0)

            if count <= 0:
                continue

            rect = pygame.Rect(panel.x + 20, y, 360, 30)

            pygame.draw.rect(surface, (60, 60, 90), rect, border_radius=6)

            text = font.render(f"{card.replace('_', ' ').title()} x{count}", True, (255, 255, 255))
            surface.blit(text, (rect.x + 10, rect.y + 5))

            self.dev_card_rects[card] = rect

            y += 40
            if hasattr(self, "dev_card_error") and self.dev_card_error:
                if time.time() - self.dev_card_error_time < 2:
                    font = pygame.font.Font(None, 26)
                    text = font.render(self.dev_card_error, True, (255, 80, 80))

                    surface.blit(text, (panel.x + 20, panel.y + 200))
    def draw_cities(self, surface):
        for pos, owner in self.cities.items():
            color = self.player_colors.get(owner, (255, 255, 255))

            x, y = int(pos[0]), int(pos[1])

            # 🔷 base (bigger than settlement)
            pygame.draw.circle(surface, color, (x, y), 16)

            # 🏰 main building (square)
            rect = pygame.Rect(x - 10, y - 10, 20, 20)
            pygame.draw.rect(surface, color, rect)

            # 🏰 roof (triangle)
            pygame.draw.polygon(surface, (40, 40, 40), [
                (x - 12, y - 10),
                (x + 12, y - 10),
                (x, y - 22)
            ])

            # 🏰 towers (left + right)
            pygame.draw.rect(surface, color, (x - 14, y - 8, 6, 14))
            pygame.draw.rect(surface, color, (x + 8, y - 8, 6, 14))

            # 🏰 tower tops
            pygame.draw.polygon(surface, (40, 40, 40), [
                (x - 14, y - 8),
                (x - 8, y - 8),
                (x - 11, y - 14)
            ])

            pygame.draw.polygon(surface, (40, 40, 40), [
                (x + 8, y - 8),
                (x + 14, y - 8),
                (x + 11, y - 14)
            ])

            # outline for clarity
            pygame.draw.circle(surface, (0, 0, 0), (x, y), 16, 2)

    def draw_robber(self, surface):
        if not self.robber_pos:
            return

        x, y = self.robber_pos

        pygame.draw.circle(surface, (20, 20, 20), (int(x), int(y)), 18)
        pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), 18, 2)

        font = pygame.font.Font(None, 22)
        text = font.render("☠", True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=(x, y)))

    def draw_dev_card_error(self, surface):
        if not self.dev_card_error:
            return

        elapsed = time.time() - self.dev_card_error_time
        duration = 2.5

        if elapsed > duration:
            self.dev_card_error = ""
            return

        # progress 0 → 1
        t = elapsed / duration

        # fade out at end
        alpha = 255
        if t > 0.8:
            alpha = int(255 * (1 - (t - 0.8) / 0.2))

        # slide down + settle animation
        start_y = 80
        target_y = 120
        y = start_y + (target_y - start_y) * min(1, t * 1.8)

        x = self.W // 2

        font = pygame.font.Font(None, 38)

        # better text styling (slight shadow effect)
        text_surface = font.render(self.dev_card_error, True, (255, 240, 240))
        text_surface.set_alpha(alpha)

        # background box
        padding_x = 60
        padding_y = 28

        bg_rect = text_surface.get_rect(center=(x, y)).inflate(padding_x, padding_y)

        # ===== shadow (stronger depth) =====
        shadow = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 140), shadow.get_rect(), border_radius=14)
        surface.blit(shadow, bg_rect.move(6, 6).topleft)

        # ===== main background (glass-like dark red) =====
        bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)

        # soft gradient feel (fake)
        pygame.draw.rect(bg, (90, 15, 15, alpha), bg.get_rect(), border_radius=14)
        pygame.draw.rect(bg, (180, 50, 50, alpha), bg.get_rect(), 2, border_radius=14)

        surface.blit(bg, bg_rect.topleft)

        # ===== subtle top highlight bar =====
        highlight = pygame.Surface((bg_rect.width, 6), pygame.SRCALPHA)
        pygame.draw.rect(highlight, (255, 120, 120, int(alpha * 0.4)), highlight.get_rect(), border_radius=3)
        surface.blit(highlight, (bg_rect.left, bg_rect.top))

        # ===== text =====
        text_rect = text_surface.get_rect(center=bg_rect.center)
        surface.blit(text_surface, text_rect)

        # ===== optional pulse effect =====
        if t < 0.2:
            pulse = pygame.Surface((bg_rect.width + 10, bg_rect.height + 10), pygame.SRCALPHA)
            pygame.draw.rect(pulse, (255, 80, 80, int(120 * (1 - t / 0.2))), pulse.get_rect(), 3, border_radius=16)
            surface.blit(pulse, bg_rect.move(-5, -5).topleft)

    def draw_trade_button(self, surface):
        mouse = pygame.mouse.get_pos()
        pressed = pygame.mouse.get_pressed()[0]

        hovered = self.trade_button.collidepoint(mouse)

        # colors
        base = (110, 85, 45)
        hover = (140, 110, 60)
        click = (90, 65, 35)
        shadow = (40, 30, 15)

        color = base
        if hovered:
            color = hover
        if hovered and pressed:
            color = click

        # shadow (gives depth)
        shadow_rect = self.trade_button.move(4, 4)
        pygame.draw.rect(surface, shadow, shadow_rect, border_radius=10)

        # main button
        pygame.draw.rect(surface, color, self.trade_button, border_radius=10)

        # border
        pygame.draw.rect(surface, (30, 20, 10), self.trade_button, 2, border_radius=10)

        # subtle glow on hover
        if hovered:
            glow_rect = self.trade_button.inflate(6, 6)
            pygame.draw.rect(surface, (180, 150, 90), glow_rect, 2, border_radius=12)

        # text
        font = pygame.font.Font(None, 34)
        text = font.render("Bank trade", True, (255, 255, 255))

        text_rect = text.get_rect(center=self.trade_button.center)
        surface.blit(text, text_rect)

    def draw_player_trade_button(self, screen):
        mouse = pygame.mouse.get_pos()

        # hover effect
        hovered = self.player_trade_button.collidepoint(mouse)

        base_color = (120, 95, 55)
        hover_color = (150, 120, 70)
        shadow_color = (60, 45, 25)

        color = hover_color if hovered else base_color

        # shadow (gives depth)
        shadow_rect = self.player_trade_button.move(4, 4)
        pygame.draw.rect(screen, shadow_color, shadow_rect, border_radius=10)

        # main button
        pygame.draw.rect(screen, color, self.player_trade_button, border_radius=10)

        # border
        pygame.draw.rect(screen, (30, 20, 10), self.player_trade_button, 2, border_radius=10)

        # text
        font = pygame.font.Font(None, 34)
        text = font.render("Player trade", True, (255, 255, 255))

        text_rect = text.get_rect(center=self.player_trade_button.center)
        screen.blit(text, text_rect)

    def draw_trade_menu(self, surface):
        if not self.trade_menu_open:
            return

        resources = ["wood", "brick", "wheat", "wool", "ore"]

        font = pygame.font.Font(None, 28)

        # GIVE section
        for i, res in enumerate(resources):
            rect = pygame.Rect(300, 200 + i * 60, 180, 50)
            pygame.draw.rect(surface, (60, 60, 60), rect)

            text = font.render(f"Give: {res}", True, (255, 255, 255))
            surface.blit(text, (rect.x + 10, rect.y + 10))

            if self.trade_give == res:
                pygame.draw.rect(surface, (255, 255, 0), rect, 3)

        # RECEIVE section
        for i, res in enumerate(resources):
            rect = pygame.Rect(520, 200 + i * 60, 180, 50)
            pygame.draw.rect(surface, (60, 60, 60), rect)

            text = font.render(f"Get: {res}", True, (255, 255, 255))
            surface.blit(text, (rect.x + 10, rect.y + 10))

            if self.trade_receive == res:
                pygame.draw.rect(surface, (0, 255, 0), rect, 3)

        # CONFIRM button
        self.trade_confirm_rect = pygame.Rect(420, 550, 150, 50)
        pygame.draw.rect(surface, (80, 120, 80), self.trade_confirm_rect)

        text = font.render("Confirm", True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=self.trade_confirm_rect.center))

    def draw_player_trade_menu(self, screen):
        if not self.player_trade_menu_open:
            return

        font = pygame.font.Font(None, 28)
        big_font = pygame.font.Font(None, 34)

        resources = ["wood", "brick", "wheat", "wool", "ore"]
        mouse = pygame.mouse.get_pos()

        # TITLES
        screen.blit(big_font.render("Give", True, (255, 255, 255)), (320, 150))
        screen.blit(big_font.render("Receive", True, (255, 255, 255)), (520, 150))
        screen.blit(big_font.render("Player", True, (255, 255, 255)), (770, 150))

        # =========================
        # GIVE
        # =========================
        for i, res in enumerate(resources):
            rect = pygame.Rect(300, 200 + i * 60, 150, 45)

            hovered = rect.collidepoint(mouse)
            selected = self.player_trade_give == res

            color = (40, 120, 40) if selected else (70, 70, 70)
            if hovered:
                color = (100, 100, 100)

            pygame.draw.rect(screen, color, rect, border_radius=8)

            text = f"{res}"
            if selected:
                text += f" x{self.player_trade_give_amount}"

            screen.blit(font.render(text, True, (255, 255, 255)), (rect.x + 10, rect.y + 10))

        # =========================
        # RECEIVE
        # =========================
        for i, res in enumerate(resources):
            rect = pygame.Rect(500, 200 + i * 60, 150, 45)

            hovered = rect.collidepoint(mouse)
            selected = self.player_trade_receive == res

            color = (40, 120, 40) if selected else (70, 70, 70)
            if hovered:
                color = (100, 100, 100)

            pygame.draw.rect(screen, color, rect, border_radius=8)

            text = f"{res}"
            if selected:
                text += f" x{self.player_trade_receive_amount}"

            screen.blit(font.render(text, True, (255, 255, 255)), (rect.x + 10, rect.y + 10))

        # =========================
        # PLAYERS
        # =========================
        for i, player in enumerate(self.player_resources.keys()):
            if player == self.username:
                continue

            rect = pygame.Rect(750, 200 + i * 60, 200, 45)

            hovered = rect.collidepoint(mouse)
            selected = self.trade_target == player

            color = (40, 120, 40) if selected else (70, 70, 70)
            if hovered:
                color = (100, 100, 100)

            pygame.draw.rect(screen, color, rect, border_radius=8)
            screen.blit(font.render(player, True, (255, 255, 255)), (rect.x + 10, rect.y + 10))

        # =========================
        # +/- BUTTONS (GIVE)
        # =========================
        self.give_minus_rect = pygame.Rect(300, 520, 40, 40)
        self.give_plus_rect = pygame.Rect(410, 520, 40, 40)

        pygame.draw.rect(screen, (120, 60, 60), self.give_minus_rect)
        pygame.draw.rect(screen, (60, 120, 60), self.give_plus_rect)

        screen.blit(font.render("-", True, (255, 255, 255)), (312, 525))
        screen.blit(font.render("+", True, (255, 255, 255)), (422, 525))

        # =========================
        # +/- BUTTONS (RECEIVE)
        # =========================
        self.recv_minus_rect = pygame.Rect(500, 520, 40, 40)
        self.recv_plus_rect = pygame.Rect(610, 520, 40, 40)

        pygame.draw.rect(screen, (120, 60, 60), self.recv_minus_rect)
        pygame.draw.rect(screen, (60, 120, 60), self.recv_plus_rect)

        screen.blit(font.render("-", True, (255, 255, 255)), (512, 525))
        screen.blit(font.render("+", True, (255, 255, 255)), (622, 525))

        # =========================
        # CONFIRM BUTTON
        # =========================
        self.player_trade_confirm_rect = pygame.Rect(450, 600, 200, 55)

        pygame.draw.rect(screen, (0, 150, 200), self.player_trade_confirm_rect, border_radius=10)
        screen.blit(font.render("Send Trade", True, (255, 255, 255)),
                    font.render("Send Trade", True, (255, 255, 255)).get_rect(center=self.player_trade_confirm_rect.center))

    def draw_incoming_trade(self, screen):
        if not self.incoming_trades:
            return

        trade = self.incoming_trades[0]

        rect = pygame.Rect(600, 300, 400, 220)
        pygame.draw.rect(screen, (40, 40, 40), rect, border_radius=10)

        font = pygame.font.Font(None, 28)
        small = pygame.font.Font(None, 24)

        txt = f"{trade['from']} offers trade"
        screen.blit(font.render(txt, True, (255, 255, 255)), (rect.x + 20, rect.y + 20))

        txt2 = f"Give: {trade['offer']}  →  Get: {trade['request']}"
        screen.blit(small.render(txt2, True, (200, 200, 200)), (rect.x + 20, rect.y + 70))

        # ACCEPT BUTTON
        self.accept_trade_rect = pygame.Rect(rect.x + 40, rect.y + 140, 130, 50)
        pygame.draw.rect(screen, (0, 180, 0), self.accept_trade_rect, border_radius=8)

        screen.blit(font.render("ACCEPT", True, (255, 255, 255)),
                    font.render("ACCEPT", True, (255, 255, 255)).get_rect(center=self.accept_trade_rect.center))

        # DECLINE BUTTON
        self.decline_trade_rect = pygame.Rect(rect.x + 230, rect.y + 140, 130, 50)
        pygame.draw.rect(screen, (180, 0, 0), self.decline_trade_rect, border_radius=8)

        screen.blit(font.render("DECLINE", True, (255, 255, 255)),
                    font.render("DECLINE", True, (255, 255, 255)).get_rect(center=self.decline_trade_rect.center))

    def draw_outgoing_trade(self, screen):
        if not self.outgoing_trades:
            return

        trade = self.outgoing_trades[0]

        rect = pygame.Rect(600, 550, 400, 150)
        pygame.draw.rect(screen, (50, 50, 80), rect)

        font = pygame.font.Font(None, 28)

        screen.blit(font.render("Confirm Trade?", True, (255, 255, 255)), (rect.x + 100, rect.y + 30))

        self.final_confirm_rect = pygame.Rect(rect.x + 140, rect.y + 80, 120, 40)
        pygame.draw.rect(screen, (0, 120, 200), self.final_confirm_rect)

    def draw_game_over_screen(self, screen):
        screen.fill((18, 18, 30))

        font_big = pygame.font.Font(None, 90)
        font = pygame.font.Font(None, 32)

        # =========================
        # TITLE
        # =========================
        title = font_big.render(f"{self.winner} WINS!", True, (255, 215, 0))
        screen.blit(title, title.get_rect(center=(self.W // 2, 80)))

        # =========================
        # TABLE BACKGROUND
        # =========================
        table_rect = pygame.Rect(150, 150, self.W - 300, 500)
        pygame.draw.rect(screen, (35, 35, 55), table_rect, border_radius=15)

        # =========================
        # HEADERS
        # =========================
        headers = ["Player", "Points", "Settlements", "Cities", "VP Dev Cards", "Largest Army Bonus"]
        x_positions = [180, 420, 600, 780, 980, 1180]

        y = 180

        for i, h in enumerate(headers):
            text = font.render(h, True, (200, 200, 200))
            screen.blit(text, (x_positions[i], y))

        pygame.draw.line(screen, (120, 120, 120), (160, y + 35), (self.W - 160, y + 35), 2)

        # =========================
        # PLAYER ROWS
        # =========================
        y += 60

        for player, stats in self.game_stats["breakdown"].items():

            values = [
                player,
                str(stats["points"]),
                str(stats["settlements"]),
                str(stats["cities"]),
                str(stats["vp_dev_cards"]),
                "YES" if stats["army"] else "NO"
            ]
            for i, v in enumerate(values):
                color = (255, 255, 255) if i == 0 else (180, 180, 180)
                text = font.render(v, True, color)
                screen.blit(text, (x_positions[i], y))

            y += 45

        # =========================
        # GAME INFO PANEL
        # =========================
        info_y = 700

        duration = self.game_stats.get("duration")
        turns = self.game_stats.get("turns", 0)

        if duration:
            duration = int(duration)

            if duration < 60:
                duration_text = f"Time: {duration} seconds"
            else:
                minutes = duration // 60
                seconds = duration % 60

                if seconds == 0:
                    duration_text = f"Time: {minutes} minutes"
                else:
                    duration_text = f"Time: {minutes} min {seconds} sec"

        info1 = font.render(f"Turns Played: {turns}", True, (255, 255, 255))
        info2 = font.render(duration_text, True, (255, 255, 255))

        screen.blit(info1, (160, info_y))
        screen.blit(info2, (160, info_y + 40))

        # =========================
        # LOBBY BUTTON
        # =========================
        pygame.draw.rect(screen, (0, 120, 200), self.lobby_button_rect, border_radius=10)
        btn = font.render("Back to Lobby", True, (255, 255, 255))
        screen.blit(btn, btn.get_rect(center=self.lobby_button_rect.center))


    def draw_dice(self, surface):
        font = pygame.font.Font(None, 40)

        mouse = pygame.mouse.get_pos()
        color = (160, 120, 70) if self.roll_button.collidepoint(mouse) else (120, 90, 60)

        pygame.draw.rect(surface, color, self.roll_button, border_radius=8)

        text = font.render("Roll Dice", True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=self.roll_button.center))

        # dice display
        if self.dice["result"]:
            d1, d2 = self.dice["result"]
        else:
            d1, d2 = (1, 1)

        x = W // 2 - 60
        y = 40

        for i, v in enumerate([d1, d2]):
            rect = pygame.Rect(x + i * 70, y, 60, 60)
            pygame.draw.rect(surface, (240, 240, 240), rect, border_radius=10)
            pygame.draw.rect(surface, (50, 50, 50), rect, 2, border_radius=10)

            num = font.render(str(v), True, (0, 0, 0))
            surface.blit(num, num.get_rect(center=rect.center))

        total = d1 + d2
        total_text = font.render(f"Total: {total}", True, (255, 220, 120))
        surface.blit(total_text, (W // 2 - 40, 110))

    def draw_discard_ui(self, screen):
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        font = pygame.font.Font(None, 40)

        text = font.render(f"Discard {self.my_discard_amount} cards", True, (255, 255, 255))
        screen.blit(text, (self.W // 2 - 150, 150))

        resources = ["wood", "brick", "wheat", "wool", "ore"]

        self.discard_plus_buttons = {}
        self.discard_minus_buttons = {}

        y_offset = 250

        for i, res in enumerate(resources):
            base_x = 650
            y = y_offset + i * 60

            count = self.player_resources[self.username].get(res, 0)
            selected = self.discard_selection.get(res, 0)

            # label
            label = font.render(f"{res}: {count} (-{selected})", True, (255, 255, 255))
            screen.blit(label, (base_x, y))

            # MINUS button
            minus_rect = pygame.Rect(base_x + 300, y, 40, 40)
            pygame.draw.rect(screen, (120, 40, 40), minus_rect)
            screen.blit(font.render("-", True, (255, 255, 255)), (minus_rect.x + 12, minus_rect.y + 5))

            # PLUS button
            plus_rect = pygame.Rect(base_x + 350, y, 40, 40)
            pygame.draw.rect(screen, (40, 120, 40), plus_rect)
            screen.blit(font.render("+", True, (255, 255, 255)), (plus_rect.x + 12, plus_rect.y + 5))

            self.discard_minus_buttons[res] = minus_rect
            self.discard_plus_buttons[res] = plus_rect

        # =========================
        # CONFIRM BUTTON
        # =========================
        self.discard_confirm_rect = pygame.Rect(750, 600, 180, 60)

        total_selected = sum(self.discard_selection.values())

        can_confirm = (total_selected == self.my_discard_amount)

        color = (120, 40, 40) if can_confirm else (80, 80, 80)
        pygame.draw.rect(screen, color, self.discard_confirm_rect)

        txt = font.render("CONFIRM", True, (255, 255, 255))
        screen.blit(txt, (self.discard_confirm_rect.x + 25, self.discard_confirm_rect.y + 15))

        # feedback
        fb = font.render(f"{total_selected}/{self.my_discard_amount}", True, (255, 255, 0))
        screen.blit(fb, (700, 200))

        # =========================
        # FEEDBACK TEXT
        # =========================
        feedback = font.render(
            f"Selected: {total_selected}/{self.my_discard_amount}",
            True,
            (255, 255, 0)
        )
        screen.blit(feedback, (700, 200))

    def handle_discard_click(self, mouse):
        if not hasattr(self, "discard_selection"):
            self.discard_selection = {}

        # select resources
        for res, rect in self.discard_buttons.items():
            if rect.collidepoint(mouse):
                current = self.discard_selection.get(res, 0)

                # don't exceed what player has
                if current < self.player_resources[self.username].get(res, 0):
                    self.discard_selection[res] = current + 1

        # confirm
        if self.discard_confirm_rect.collidepoint(mouse):

            total = sum(self.discard_selection.values())

            if total != self.my_discard_amount:
                print("Wrong discard amount")
                return

            response = self.client.send_request(
                "discard_cards",
                username=self.username,
                game_code=self.game_code,
                discard_dict=self.discard_selection
            )

            print("DISCARD RESPONSE:", response)

            if response and response.get("success"):
                self.steal_selecting = False
                self.steal_targets = []
    # ==================================================
    # MAIN LOOP
    # ==================================================
    def refresh_trades(self):
        r = self.client.send_request(
            "game_state",
            game_code=self.game_code
        )

        if r and r.get("success"):
            self.incoming_trades = r.get("incoming_trades", [])
            self.outgoing_trades = r.get("outgoing_trades", [])

    def run(self):

        while self.running:

            self.clock.tick(60)

            for e in pygame.event.get():

                if e.type == pygame.QUIT:
                    self.running = False



                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:

                    mouse = e.pos

                    # =========================

                    # OPEN MENUS

                    # =========================

                    if self.player_trade_button.collidepoint(mouse):
                        self.player_trade_menu_open = not self.player_trade_menu_open

                        self.trade_menu_open = False  # prevent overlap

                    if self.trade_button.collidepoint(mouse):
                        self.trade_menu_open = not self.trade_menu_open

                        self.player_trade_menu_open = False  # prevent overlap

                    # =========================

                    # PLAYER TRADE MENU

                    # =========================

                    if self.player_trade_menu_open:

                        resources = ["wood", "brick", "wheat", "wool", "ore"]

                        # SELECT GIVE

                        for i, res in enumerate(resources):

                            rect = pygame.Rect(300, 200 + i * 60, 150, 40)

                            if rect.collidepoint(mouse):
                                self.player_trade_give = res

                        # SELECT RECEIVE

                        for i, res in enumerate(resources):

                            rect = pygame.Rect(500, 200 + i * 60, 150, 40)

                            if rect.collidepoint(mouse):
                                self.player_trade_receive = res

                        # SELECT PLAYER

                        for i, player in enumerate(self.player_resources.keys()):

                            if player == self.username:
                                continue

                            rect = pygame.Rect(750, 200 + i * 60, 200, 40)

                            if rect.collidepoint(mouse):
                                self.trade_target = player

                        # =========================

                        # +/- BUTTONS (SAFE)

                        # =========================

                        # GIVE amount
                        if hasattr(self, "give_plus_rect") and self.give_plus_rect.collidepoint(mouse):
                            self.player_trade_give_amount += 1

                        if hasattr(self, "give_minus_rect") and self.give_minus_rect.collidepoint(mouse):
                            self.player_trade_give_amount = max(1, self.player_trade_give_amount - 1)

                        # RECEIVE amount
                        if hasattr(self, "recv_plus_rect") and self.recv_plus_rect.collidepoint(mouse):
                            self.player_trade_receive_amount += 1

                        if hasattr(self, "recv_minus_rect") and self.recv_minus_rect.collidepoint(mouse):
                            self.player_trade_receive_amount = max(1, self.player_trade_receive_amount - 1)

                        # =========================

                        # CONFIRM PLAYER TRADE

                        # =========================

                    if hasattr(self, "player_trade_confirm_rect") and self.player_trade_confirm_rect.collidepoint(
                            mouse):

                        if self.player_trade_give and self.player_trade_receive and self.trade_target:

                            response = self.client.send_request(
                                "create_trade",
                                username=self.username,
                                game_code=self.game_code,
                                to_player=self.trade_target,
                                offer={self.player_trade_give: self.player_trade_give_amount},
                                request={self.player_trade_receive: self.player_trade_receive_amount}
                            )

                            # =========================
                            # HANDLE SERVER RESPONSE
                            # =========================
                            if not response or not response.get("success"):
                                self.dev_card_error = response.get("message", "Trade failed")
                                self.dev_card_error_time = time.time()

                            else:
                                # RESET ONLY ON SUCCESS
                                self.player_trade_menu_open = False
                                self.player_trade_give = None
                                self.player_trade_receive = None
                                self.trade_target = None
                                self.player_trade_give_amount = 1
                                self.player_trade_receive_amount = 1

                        # =========================

                        # INCOMING TRADE RESPONSES

                        # =========================
                    print(f"condition 0 {self.incoming_trades}")
                    if self.incoming_trades:

                        trade = self.incoming_trades[0]
                        print(f" condition 1 : {hasattr(self, "accept_trade_rect")}")
                        print(f" condition 2 : {self.accept_trade_rect.collidepoint(mouse)}")
                        if hasattr(self, "accept_trade_rect") and self.accept_trade_rect.collidepoint(mouse):
                            print("ACCEPT CLICKED")
                            print("MOUSE:", mouse)
                            print("ACCEPT RECT:", getattr(self, "accept_trade_rect", None))

                            self.client.send_request(
                                "respond_trade",
                                username=self.username,
                                game_code=self.game_code,
                                trade_id=trade["id"],
                                accept=True
                            )

                            # 🔥 FORCE REFRESH

                        if hasattr(self, "decline_trade_rect") and self.decline_trade_rect.collidepoint(mouse):
                            print("DECLINE CLICKED")

                            self.client.send_request(
                                "respond_trade",
                                username=self.username,
                                game_code=self.game_code,
                                trade_id=trade["id"],
                                accept=False
                            )

                            # 🔥 FORCE REFRESH
                            self.refresh_trades()

                    # =========================

                    # OUTGOING TRADE CONFIRM

                    # =========================

                    if self.outgoing_trades:

                        trade = self.outgoing_trades[0]

                        if self.final_confirm_rect and self.final_confirm_rect.collidepoint(mouse):
                            self.client.send_request(

                                "confirm_trade",

                                username=self.username,

                                game_code=self.game_code,

                                trade_id=trade["id"]

                            )

                    # =========================

                    # BANK TRADE MENU

                    # =========================

                    if self.trade_menu_open:
                        if self.bank_trade_confirm_rect.collidepoint(mouse):
                            print("BANK CONFIRM CLICKED")

                        resources = ["wood", "brick", "wheat", "wool", "ore"]

                        # GIVE

                        for i, res in enumerate(resources):

                            rect = pygame.Rect(300, 200 + i * 60, 180, 50)

                            if rect.collidepoint(mouse):
                                self.trade_give = res

                        # RECEIVE

                        for i, res in enumerate(resources):

                            rect = pygame.Rect(520, 200 + i * 60, 180, 50)

                            if rect.collidepoint(mouse):
                                self.trade_receive = res

                        # CONFIRM BANK TRADE

                        if hasattr(self, "bank_trade_confirm_rect") and self.bank_trade_confirm_rect.collidepoint(
                                mouse):

                            if self.trade_give and self.trade_receive:

                                response = self.client.send_request(

                                    "trade_with_bank",

                                    username=self.username,

                                    game_code=self.game_code,

                                    give_resource=self.trade_give,

                                    receive_resource=self.trade_receive

                                )

                                print("TRADE RESPONSE:", response)

                                if not response or not response.get("success"):

                                    self.dev_card_error = response.get("message", "Trade failed")

                                    self.dev_card_error_time = time.time()


                                else:

                                    if "resources" in response:
                                        self.player_resources[self.username] = response["resources"]

                                    self.trade_menu_open = False

                                    self.trade_give = None

                                    self.trade_receive = None

                    if self.discarding:

                        # PLUS
                        for res, rect in self.discard_plus_buttons.items():
                            if rect.collidepoint(mouse):
                                if sum(self.discard_selection.values()) < self.my_discard_amount:
                                    if self.player_resources[self.username].get(res, 0) > self.discard_selection[res]:
                                        self.discard_selection[res] += 1

                        # MINUS
                        for res, rect in self.discard_minus_buttons.items():
                            if rect.collidepoint(mouse):
                                if self.discard_selection[res] > 0:
                                    self.discard_selection[res] -= 1

                        # CONFIRM
                        if self.discard_confirm_rect and self.discard_confirm_rect.collidepoint(mouse):

                            if sum(self.discard_selection.values()) == self.my_discard_amount:

                                response = self.client.send_request(
                                    "discard_cards",
                                    username=self.username,
                                    game_code=self.game_code,
                                    discard_dict=self.discard_selection
                                )

                                print("DISCARD RESPONSE:", response)

                                if response and response.get("success"):
                                    print("success")
                                    self.discarding = False
                                    self.discard_selection = {k: 0 for k in ["wood", "brick", "wheat", "wool", "ore"]}
                                    self.my_discard_amount = 0
                                    print()
                                    print(self.username)
                                    print(self.my_turn )
                                    print("turn")

                    # =========================
                    # ROBBER MOVE
                    # =========================
                    if self.show_robber_select and not getattr(self, "robber_already_moved", False):

                        clicked_hex = None

                        for hex_pos in self.hexagon_positions:
                            if pygame.Vector2(hex_pos).distance_to(mouse) < 40:  # ✅ use mouse
                                clicked_hex = hex_pos
                                break

                        if clicked_hex is None:
                            continue

                        response = self.client.send_request(
                            "move_robber",
                            username=self.username,
                            game_code=self.game_code,
                            position=clicked_hex
                        )

                        if response and response.get("success"):
                            self.show_robber_select = False
                            self.robber_already_moved = True  # 🔥 lock movement

                            # ✅ ONLY enter steal if server says so
                            if response.get("action") == "choose_player_to_steal":
                                # Let sync_loop populate targets (recommended)
                                self.steal_selecting = True
                            else:
                                self.steal_selecting = False

                    # =========================
                    # STEAL
                    # =========================
                    if self.steal_selecting:

                        for i, player in enumerate(self.steal_targets):
                            rect = pygame.Rect(600, 200 + i * 60, 250, 50)

                            if rect.collidepoint(mouse):  # ✅ use mouse

                                # ✅ FIX: extract username
                                target_username = player["username"] if isinstance(player, dict) else player

                                response = self.client.send_request(
                                    "steal_from_player",
                                    username=self.username,
                                    game_code=self.game_code,
                                    target=target_username
                                )

                                print("STEAL RESULT:", response)

                                if response and response.get("success"):
                                    self.steal_selecting = False
                                    self.steal_targets = []

                                    # 🔥 IMPORTANT RESET
                                    self.robber_already_moved = False
                                else:
                                    print("Steal failed:", response)

                                break

                        continue

                    # =========================
                    # YEAR OF PLENTY
                    # =========================
                    if getattr(self, "year_of_plenty_selecting", False):

                        resources = ["wood", "brick", "wheat", "wool", "ore"]

                        for i, res in enumerate(resources):
                            rect = pygame.Rect(850, 200 + i * 60, 200, 50)

                            if rect.collidepoint(mouse):  # ✅ use mouse

                                response = self.client.send_request(
                                    "choose_year_of_plenty",
                                    username=self.username,
                                    game_code=self.game_code,
                                    resource=res
                                )

                                print("YEAR OF PLENTY:", response)

                                if not response or not response.get("success"):
                                    self.dev_card_error = response.get("message", "Year of Plenty failed")
                                    self.dev_card_error_time = time.time()
                                    break

                                # 🔥 REFRESH STATE
                                r = self.client.send_request(
                                    "game_state",
                                    game_code=self.game_code
                                )

                                if r and r.get("success"):
                                    self.player_resources = r["player_resources"]

                                    for user, res2 in self.player_resources.items():
                                        dev_list = res2.get("dev_cards", [])
                                        res2["dev_cards_raw"] = dev_list
                                        res2["dev_cards"] = self.count_dev_cards(dev_list)

                                self.yop_remaining -= 1

                                if self.yop_remaining <= 0:
                                    self.year_of_plenty_selecting = False

                                break

                        continue
                    if self.monopoly_selecting:
                        resources = ["wood", "brick", "wheat", "wool", "ore"]

                        for i, res in enumerate(resources):
                            rect = pygame.Rect(600, 200 + i * 60, 200, 50)

                            if rect.collidepoint(mouse):

                                response = self.client.send_request(
                                    "choose_monopoly",
                                    username=self.username,
                                    game_code=self.game_code,
                                    resource=res
                                )

                                print("MONOPOLY RESULT:", response)

                                if not response or not response.get("success"):
                                    self.dev_card_error = response.get("message", "Monopoly failed")
                                    self.dev_card_error_time = time.time()

                                if response and response.get("success"):

                                    # 🔥 REFRESH STATE AFTER MONOPOLY
                                    r = self.client.send_request(
                                        "game_state",
                                        game_code=self.game_code
                                    )

                                    if r and r.get("success"):
                                        self.player_resources = r["player_resources"]

                                        for user, res in self.player_resources.items():
                                            dev_list = res.get("dev_cards", [])
                                            res["dev_cards_raw"] = dev_list
                                            res["dev_cards"] = self.count_dev_cards(dev_list)

                                self.monopoly_selecting = False
                                break

                        continue
                    if self.show_dev_cards and self.buy_dev_card_rect:
                        if self.buy_dev_card_rect.collidepoint(mouse):

                            response = self.client.send_request(
                                "buy_dev_card",
                                username=self.username,
                                game_code=self.game_code
                            )

                            print("BUY DEV CARD:", response)

                            if response.get("success"):

                                # make sure dict exists
                                self.player_resources[self.username].setdefault("dev_cards", {})

                                # update from server
                                dev_list = response.get("dev_cards", [])

                                self.player_resources[self.username]["dev_cards_raw"] = dev_list
                                self.player_resources[self.username]["dev_cards"] = self.count_dev_cards(dev_list)

                            else:
                                # =========================
                                # NOT YOUR TURN OR ERROR
                                # =========================
                                print(response.get("message", "Cannot buy dev card"))

                                # optional UI feedback
                                self.dev_card_error = response.get("message", "Not allowed")

                                self.dev_card_error_time = time.time()

                            continue

                    if self.dev_card_button_rect.collidepoint(mouse):
                        self.show_dev_cards = not self.show_dev_cards
                        continue

                    if self.end_turn_button.collidepoint(e.pos):
                        self.client.send_request(
                            "end_turn",
                            username=self.username,
                            game_code=self.game_code
                        )
                        continue

                    if self.road_button_rect.collidepoint(mouse):
                        self.show_road_spots = not self.show_road_spots
                        continue
                    if self.roll_button.collidepoint(e.pos):
                        self.roll_dice()
                        continue
                    if self.city_button_rect.collidepoint(mouse):
                        self.show_city_spots = not self.show_city_spots
                        continue
                    for username, rect in self.player_rects.items():

                        if rect.collidepoint(mouse):

                            if self.parent_window and username != self.username:
                                #chat
                                self.parent_window.open_friend_page(
                                    username,
                                    profile_pic_data=None
                                )

                            break

                    if self.show_dev_cards and hasattr(self, "dev_card_rects"):

                        for card, rect in self.dev_card_rects.items():

                            if rect.collidepoint(mouse):

                                # =========================
                                # FIRST CLICK → SELECT
                                # =========================
                                if self.selected_dev_card != card:
                                    self.selected_dev_card = card
                                    break

                                # =========================
                                # SECOND CLICK → USE CARD
                                # =========================
                                response = self.client.send_request(
                                    "use_dev_card",
                                    username=self.username,
                                    game_code=self.game_code,
                                    card=card
                                )

                                print("USE DEV CARD:", response)

                                # =========================
                                # SAFE CHECK
                                # =========================
                                if not response:
                                    self.dev_card_error = "Server error"
                                    self.dev_card_error_time = time.time()
                                    self.selected_dev_card = None
                                    break

                                if not response.get("success"):
                                    self.dev_card_error = response.get("message", "Cannot use dev card")
                                    self.dev_card_error_time = time.time()
                                    self.selected_dev_card = None
                                    break


                                # =========================
                                # MONOPOLY FLOW
                                # =========================
                                if response.get("action") == "choose_monopoly_resource":
                                    self.monopoly_selecting = True
                                    self.selected_dev_card = None
                                    self.show_dev_cards = False
                                    break

                                # =========================
                                # YEAR OF PLENTY FLOW 🔥
                                # =========================
                                if response.get("action") == "choose_year_of_plenty":
                                    print("ENTERING YEAR OF PLENTY MODE")  # 👈 add this
                                    self.year_of_plenty_selecting = True
                                    self.yop_remaining = 2
                                    self.selected_dev_card = None
                                    self.show_dev_cards = False
                                    break
                                if response.get("action") == "place_road_building":
                                    print("ENTERING ROAD BUILDING MODE")
                                    self.road_building_active = True
                                    self.roads_to_place = 2
                                    self.show_road_spots = True  # Automatically show spots for the player
                                    self.selected_dev_card = None
                                    self.show_dev_cards = False
                                    break

                                # =========================
                                # KNIGHT FLOW
                                # =========================
                                if card == "knight":
                                    self.show_robber_select = True

                                # =========================
                                # REFRESH STATE
                                # =========================
                                r = self.client.send_request(
                                    "game_state",
                                    game_code=self.game_code
                                )

                                if r and r.get("success") and "player_resources" in r:
                                    self.player_resources = r["player_resources"]
                                else:
                                    print("[ERROR] Bad game_state:", r)

                                    for user, res in self.player_resources.items():
                                        dev_list = res.get("dev_cards", [])
                                        res["dev_cards_raw"] = dev_list
                                        res["dev_cards"] = self.count_dev_cards(dev_list)

                                self.selected_dev_card = None
                                self.show_dev_cards = False
                                break


                    if self.show_road_spots:
                        response = self.try_place_road(e.pos)

                        print("response road:", response)

                        if not response.get("success", False):

                            error = response.get("error")

                            # =========================
                            # HANDLE MISSING RESOURCES
                            # =========================
                            if error == "missing_resources":

                                self.road_error_time = time.time()
                                self.road_error_type = "road_cost_missing"

                                self.missing_resources = response.get("missing", [])

                                # build readable message
                                if len(self.missing_resources) == 2:
                                    self.road_error_message = "Missing wood and brick"
                                elif self.missing_resources:
                                    self.road_error_message = f"Missing {self.missing_resources[0]}"
                                else:
                                    self.road_error_message = "Not enough resources"
                    if self.game_over_screen and self.lobby_button_rect.collidepoint(mouse):
                        self.client.send_request(
                            "leave_game",
                            username=self.username,
                            game_code=self.game_code
                        )

                        self.running = False  # or return to lobby screen

                    elif self.show_city_spots:

                        self.try_upgrade_city(e.pos)


                    else:

                        self.try_place_settlement(e.pos)

            try:
                self.draw()
            except Exception as e:
                print("[DRAW CRASH]", e)

        pygame.quit()

    # ==================================================
    # DRAW
    # ==================================================


    def draw(self):
        if self.game_over_screen:
            self.draw_game_over_screen(self.screen)
            pygame.display.flip()
            return
        self.screen.fill(BG_COLOR)

        if not self.hexagon_positions:

            font = pygame.font.Font(None, 36)
            text = font.render("Waiting for board data...", True, (255, 255, 255))
            self.screen.blit(text, (40, 40))

            pygame.display.flip()
            return

        try:

            valid_spots, valid_roads = render_map(
                surface=self.screen,
                hex_positions=self.hexagon_positions,
                hex_resources=self.hexagon_resources,
                resource_colors=self.resource_colors(),
                icons=self.resource_icons,
                hex_numbers=self.hexagon_numbers,
                is_my_turn=self.my_turn,
                placed_settlements=self.settlements,
                placed_cities=self.cities,
                player_colors=self.player_colors,
                mouse_pos=pygame.mouse.get_pos(),
                my_username=self.username,
                placed_roads=self.placed_roads,
                show_road_spots=self.show_road_spots,
                last_settlement=self.last_settlement,
                ports=self.ports
            )

            if self.phase.startswith("setup"):
                # SETUP MODE
                self.valid_spots = valid_spots
            else:
                # NORMAL MODE
                my_nodes = self.get_my_nodes()

                self.valid_spots = {
                    spot for spot in valid_spots
                    if normalize(spot) in my_nodes
                }
            my_nodes = self.get_my_nodes()

            filtered_roads = set()

            normalized_valid_roads = set()

            for edge in valid_roads:
                a, b = edge
                a_n = normalize(a)
                b_n = normalize(b)
                normalized_valid_roads.add((a_n, b_n))

            filtered_roads = set()

            for a, b in normalized_valid_roads:
                if a in my_nodes or b in my_nodes:
                    filtered_roads.add((a, b))

            self.valid_roads = filtered_roads
        except Exception as e:
            print("[RENDER ERROR]", e)
            self.valid_spots = set()

        # draw roads
        self.draw_placed_roads(self.screen)
        self.draw_road_previews(self.screen)
        self.draw_city_previews(self.screen)
        self.draw_cities(self.screen)
        # UI
        self.draw_buttons(self.screen)
        self.draw_players_panel(self.screen)
        self.draw_resources_ui(self.screen)
        self.draw_end_turn_button(self.screen)
        self.draw_dice(self.screen)
        self.draw_robber(self.screen)
        self.draw_dev_cards_ui(self.screen)
        self.draw_dev_card_error(self.screen)
        self.draw_trade_button(self.screen)
        self.draw_trade_menu(self.screen)
        self.draw_player_trade_button(self.screen)
        self.draw_player_trade_menu(self.screen)
        self.draw_incoming_trade(self.screen)
        self.draw_outgoing_trade(self.screen)
        self.draw_longest_road_popup(self.screen)
        if self.discarding and not self.username in self.discard_submitted :
            self.draw_discard_ui(self.screen)
            pygame.display.flip()
            return
        print(f"robber_select : {self.show_robber_select}")
        print(f"self.discard_required : {self.discard_required}")
        if self.show_robber_select and not self.discard_required and not self.steal_selecting:
            for pos in self.hexagon_positions:
                if pos == self.robber_pos:
                    continue
                pygame.draw.circle(self.screen, (255, 255, 255), (int(pos[0]), int(pos[1])), 40, 2)
            # =========================
        if self.road_error_type == "road_cost_missing" and self.missing_resources:

            if time.time() - self.road_error_time < 2:

                font = pygame.font.SysFont("Arial", 28, bold=True)

                text = font.render(self.road_error_message, True, (255, 80, 80))
                bg_rect = text.get_rect(center=(self.W // 2, 120))

                pygame.draw.rect(
                    self.screen,
                    (60, 0, 0),
                    bg_rect.inflate(140, 40),
                    border_radius=10
                )

                self.screen.blit(text, bg_rect)

                # =========================
                # ONLY MISSING ICONS
                # =========================

                icon_y = bg_rect.bottom + 10
                spacing = 50

                start_x = self.W // 2 - (len(self.missing_resources) * spacing) // 2

                for i, res in enumerate(self.missing_resources):
                    icon = self.resource_icons[res]

                    rect = icon.get_rect()
                    rect.center = (start_x + i * spacing, icon_y)

                    self.screen.blit(icon, rect)

            else:
                self.road_error_type = None
                self.missing_resources = []

        # =========================
        if self.road_error_type == "road_cost_missing" and self.missing_resources:

            if time.time() - self.road_error_time < 2:

                font = pygame.font.SysFont("Arial", 28, bold=True)

                text = font.render(self.road_error_message, True, (255, 80, 80))
                bg_rect = text.get_rect(center=(self.W // 2, 120))

                pygame.draw.rect(
                    self.screen,
                    (60, 0, 0),
                    bg_rect.inflate(140, 40),
                    border_radius=10
                )

                self.screen.blit(text, bg_rect)


                # =========================
                # ONLY MISSING ICONS
                # =========================

                icon_y = bg_rect.bottom + 10
                spacing = 50

                start_x = self.W // 2 - (len(self.missing_resources) * spacing) // 2

                for i, res in enumerate(self.missing_resources):
                    icon = self.resource_icons[res]

                    rect = icon.get_rect()
                    rect.center = (start_x + i * spacing, icon_y)

                    self.screen.blit(icon, rect)

            else:
                self.road_error_type = None
                self.missing_resources = []
        if self.monopoly_selecting:
            try:
                resources = ["wood", "brick", "wheat", "wool", "ore"]

                for i, res in enumerate(resources):
                    rect = pygame.Rect(600, 200 + i * 60, 200, 50)
                    pygame.draw.rect(self.screen, (50, 50, 50), rect)

                    if not hasattr(self, "font") or self.font is None:
                        self.font = pygame.font.Font(None, 32)

                    text = self.font.render(res, True, (255, 255, 255))
                    self.screen.blit(text, (rect.x + 20, rect.y + 10))

            except Exception as e:
                print("[MONOPOLY DRAW ERROR]", e)
                self.monopoly_selecting = False
        if getattr(self, "year_of_plenty_selecting", False):
            resources = ["wood", "brick", "wheat", "wool", "ore"]

            for i, res in enumerate(resources):
                rect = pygame.Rect(850, 200 + i * 60, 200, 50)
                pygame.draw.rect(self.screen, (70, 70, 120), rect)

                text = self.font.render(f"{res} ({self.yop_remaining} left)", True, (255, 255, 255))
                self.screen.blit(text, (rect.x + 10, rect.y + 10))

        if self.steal_selecting:
            # 1. Safety check: ensure steal_targets is actually a list we can iterate
            if isinstance(self.steal_targets, list):
                for i, target in enumerate(self.steal_targets):

                    # 2. Logic Check: handle both string usernames or dict objects
                    if isinstance(target, dict):
                        username = target.get("username", "Unknown")
                        # Ensure player_pfps is a dict before calling .get()
                        pfp = None
                        if isinstance(self.player_pfps, dict):
                            pfp = self.player_pfps.get(username)
                    else:
                        username = str(target)
                        pfp = self.player_pfps.get(username) if isinstance(self.player_pfps, dict) else None

                    rect = pygame.Rect(600, 200 + i * 60, 300, 50)
                    pygame.draw.rect(self.screen, (80, 40, 40), rect, border_radius=8)

                    # 3. Blit safely
                    if pfp and isinstance(pfp, pygame.Surface):
                        self.screen.blit(pfp, (rect.x + 5, rect.y + 5))
                    else:
                        # Placeholder if PFP is missing or still a list/string
                        pygame.draw.rect(self.screen, (60, 60, 60), (rect.x + 5, rect.y + 5, 30, 30), border_radius=4)

                    text = self.font.render(f"Steal from {username}", True, (255, 255, 255))
                    self.screen.blit(text, (rect.x + 45, rect.y + 10))

        if hasattr(self, "winner") and self.winner:
            font = pygame.font.Font(None, 80)
            text = font.render(f"{self.winner} WINS!", True, (255, 215, 0))
            self.screen.blit(text, (self.W // 2 - 200, self.H // 2))


        pygame.display.flip()  # 👈 ALWAYS LAST LINE