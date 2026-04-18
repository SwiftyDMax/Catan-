import pygame
import math

# =========================================================
# SCREEN / CONSTANTS
# =========================================================
SCREEN_WIDTH = 1820
SCREEN_HEIGHT = 980
HEX_SIZE = 53
PATH_WIDTH = 14
PORT_PATH_WIDTH = 6

# =========================================================
# COLORS
# =========================================================
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)
RED = (200, 50, 50)
BG = (30, 30, 30)

HEX_OUTLINE = (35, 30, 25)
HEX_INNER_OUTLINE = (80, 70, 55)

PATH_COLOR = (110, 80, 45)
PORT_PATH_COLOR = (160, 120, 60)

TOKEN_BG = (235, 220, 190)
TOKEN_BORDER = (70, 55, 40)

SPOT_FILL = (110, 110, 110)
SPOT_BORDER = (230, 230, 230)
HOVER_FILL = (170, 170, 170)
HOVER_BORDER = (255, 255, 255)
PLAYER_COLOR_RGB = {
    "Red": (255, 0, 0),
    "Blue": (0, 0, 255),
    "White": (255, 255, 255),
    "Orange": (255, 140, 0),
}
# =========================================================
# RESOURCE ICON PATHS
# =========================================================
RESOURCE_ICON_PATHS = {
    "wood": "Images/game/wood.png",
    "brick": "Images/game/brick.png",
    "ore": "Images/game/ore.png",
    "wheat": "Images/game/wheat.png",
    "wool": "Images/game/sheep.png",
    "any": "Images/game/any.png",
    "desert": "Images/game/desert.png",
}

# =========================================================
# ICON LOADING
# =========================================================
def load_resource_icons():
    icons = {}
    for resource, path in RESOURCE_ICON_PATHS.items():
        try:
            img = pygame.image.load(path).convert_alpha()
            size = int(HEX_SIZE * 1.6) if resource == "desert" else 42
            icons[resource] = pygame.transform.smoothscale(img, (size, size))
        except Exception as e:
            print(f"[ICON LOAD ERROR] {resource}: {e}")
            surf = pygame.Surface((30, 30), pygame.SRCALPHA)
            surf.fill((200, 200, 200, 255))
            icons[resource] = surf
    return icons

# =========================================================
# GEOMETRY
# =========================================================
def get_hexagon_vertices(center, radius):
    pts = []
    for i in range(6):
        a = math.radians(30 + i * 60)
        pts.append((
            center[0] + radius * math.cos(a),
            center[1] + radius * math.sin(a)
        ))
    return pts

def draw_hexagon(surface, fill_color, center, radius):
    pts = get_hexagon_vertices(center, radius)
    pygame.draw.polygon(surface, fill_color, pts)
    pygame.draw.polygon(surface, HEX_OUTLINE, pts, 4)
    pygame.draw.polygon(surface, HEX_INNER_OUTLINE, pts, 2)

def draw_path(surface, start, end):
    pygame.draw.line(surface, PATH_COLOR, start, end, PATH_WIDTH)

# =========================================================
# PORTS
# =========================================================
def get_closest_vertices(port_pos, hex_pos):
    verts = get_hexagon_vertices(hex_pos, HEX_SIZE)
    verts.sort(key=lambda v: math.dist(v, port_pos))
    return verts[:2]

def find_closest_hexagon(port_pos, hex_positions):
    return min(hex_positions, key=lambda h: math.dist(h, port_pos))

def draw_port_paths(surface, port_pos, hex_pos):
    for v in get_closest_vertices(port_pos, hex_pos):
        pygame.draw.line(surface, PORT_PATH_COLOR, port_pos, v, PORT_PATH_WIDTH)

def draw_port(surface, position, port_type, icons):
    pygame.draw.circle(surface, (40, 80, 140), position, 20)
    pygame.draw.circle(surface, (210, 210, 220), position, 20, 2)

    ratio, resource = port_type.split()
    font = pygame.font.Font(None, 24)
    txt = font.render(ratio, True, WHITE)
    surface.blit(txt, txt.get_rect(center=(position[0], position[1] - 12)))

    icon = icons.get(resource)
    if icon:
        small = pygame.transform.smoothscale(icon, (28, 28))
        surface.blit(small, small.get_rect(center=(position[0], position[1] + 10)))

# =========================================================
# SETTLEMENTS
# =========================================================
def calculate_vertex_positions(hex_positions, tolerance=12):
    """
    Returns one vertex per real board intersection
    by clustering nearby vertices.
    """
    raw_vertices = []

    for center in hex_positions:
        for i in range(6):
            a = math.radians(30 + i * 60)
            x = center[0] + HEX_SIZE * math.cos(a)
            y = center[1] + HEX_SIZE * math.sin(a)
            raw_vertices.append((x, y))

    clustered = []

    for v in raw_vertices:
        found_cluster = False
        for i, c in enumerate(clustered):
            if math.dist(v, c) < tolerance:
                # average them
                clustered[i] = (
                    (c[0] + v[0]) / 2,
                    (c[1] + v[1]) / 2
                )
                found_cluster = True
                break

        if not found_cluster:
            clustered.append(v)

    return [tuple(map(int, c)) for c in clustered]

def calculate_valid_settlement_spots(vertices, placed_settlements, placed_cities=None, is_initial_placement=False):

    if is_initial_placement:
        return set(vertices)

    valid_spots = set()
    DISTANCE_RULE = HEX_SIZE * 1.5

    # settlements
    if isinstance(placed_settlements, dict):
        settlement_positions = set(placed_settlements.keys())
    else:
        settlement_positions = set(placed_settlements)

    # cities
    if placed_cities:
        if isinstance(placed_cities, dict):
            city_positions = set(placed_cities.keys())
        else:
            city_positions = set(placed_cities)
    else:
        city_positions = set()

    # 🔥 unified occupied nodes
    placed_positions = settlement_positions | city_positions

    for vertex in vertices:
        is_valid = True

        for pos in placed_positions:
            dx = vertex[0] - pos[0]
            dy = vertex[1] - pos[1]

            if math.hypot(dx, dy) < DISTANCE_RULE:
                is_valid = False
                break

        if is_valid:
            valid_spots.add(vertex)

    return valid_spots

def draw_settlement_spots(surface, spots, mouse_pos=None, hex_positions=None):
    for v in spots:
        # count how many hexes are close → inner nodes get more connections
        connections = sum(
            1 for h in hex_positions
            if math.dist(v, h) < HEX_SIZE * 1.3
        )

        base_radius = 8
        if connections <= 2:      # outer ring
            base_radius = 11
        elif connections == 3:    # mid ring
            base_radius = 9

        hover = mouse_pos and math.dist(v, mouse_pos) < 18
        r = base_radius + (3 if hover else 0)

        fill = HOVER_FILL if hover else SPOT_FILL
        border = HOVER_BORDER if hover else SPOT_BORDER

        pygame.draw.circle(surface, fill, v, r)
        pygame.draw.circle(surface, border, v, r, 2)

def draw_settlements(surface, placed, player_colors):
    for (x, y), owner in placed.items():

        # 🔍 DEBUG (keep until stable)
        if owner not in player_colors:
            print("[DRAW ERROR]")
            print(" owner:", owner)
            print(" player_colors:", player_colors)
            continue  # do NOT draw silently as blue

        color_name = player_colors[owner]

        # normalize color name just in case
        color_name = color_name.capitalize()

        if color_name not in PLAYER_COLOR_RGB:
            print("[DRAW ERROR] Unknown color:", color_name)
            continue

        color = PLAYER_COLOR_RGB[color_name]

        size = 12
        points = [
            (x - size, y + size),
            (x + size, y + size),
            (x + size, y),
            (x, y - size),
            (x - size, y),
        ]

        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, BLACK, points, 2)
# =========================================================
# ROAD LOGIC
# =========================================================

# roads: {(v1, v2): owner}
# normalize edges so order doesn't matter
def normalize_edge(a, b):
    return tuple(sorted((a, b)))
def calculate_road_edges(vertices):
    edges = set()
    MAX_LEN = HEX_SIZE * 1.25  # edge length

    for i, v1 in enumerate(vertices):
        for v2 in vertices[i + 1:]:
            if math.dist(v1, v2) < MAX_LEN:
                edges.add(normalize_edge(v1, v2))

    return edges
def calculate_valid_roads(edges, placed_roads, last_settlement):
    return {edge for edge in edges if edge not in placed_roads}

    return valid

def draw_road_spots(surface, roads, mouse_pos):
    for a, b in roads:
        pygame.draw.line(surface, (255, 0, 255), a, b, 8)

def draw_roads(surface, placed_roads, player_colors):
    for (a, b), owner in placed_roads.items():
        color = PLAYER_COLOR_RGB[player_colors[owner].capitalize()]
        pygame.draw.line(surface, color, a, b, PATH_WIDTH)







# =========================================================
# NUMBER TOKENS
# =========================================================
def draw_number_token(surface, pos, number):
    r = 18
    pygame.draw.circle(surface, TOKEN_BG, pos, r)
    pygame.draw.circle(surface, TOKEN_BORDER, pos, r, 2)
    font = pygame.font.Font(None, 28)
    col = RED if number in (6, 8) else BLACK
    txt = font.render(str(number), True, col)
    surface.blit(txt, txt.get_rect(center=pos))

# =========================================================
# MAIN RENDER FUNCTION
# =========================================================
def render_map(
        surface,
        hex_positions,
        hex_resources,
        resource_colors,
        icons,
        hex_numbers,
        is_my_turn,
        placed_settlements,
        placed_cities,
        player_colors,
        mouse_pos,
        my_username,
        placed_roads,
        show_road_spots,
        last_settlement,
        ports
):
    # =========================
    # BACKGROUND PATHS
    # =========================
    for i, h1 in enumerate(hex_positions):
        for h2 in hex_positions[i + 1:]:
            if math.dist(h1, h2) < HEX_SIZE * 2.2:
                draw_path(surface, h1, h2)

    # =========================
    # PORTS
    # =========================
    for p, _ in ports:
        h = find_closest_hexagon(p, hex_positions)
        draw_port_paths(surface, p, h)

    # =========================
    # HEXES
    # =========================
    for pos in hex_positions:
        res = hex_resources[pos]
        draw_hexagon(surface, resource_colors[res], pos, HEX_SIZE)

        icon = icons.get(res)
        if icon:
            surface.blit(icon, icon.get_rect(center=pos))

        if res != "desert":
            draw_number_token(surface, (pos[0], pos[1] + 30), hex_numbers[pos])

    # =========================
    # GEOMETRY
    # =========================
    vertices = calculate_vertex_positions(hex_positions)
    edges = calculate_road_edges(vertices)

    # =========================
    # SETTLEMENT PREVIEW
    # =========================
    valid_settlements = calculate_valid_settlement_spots(
        vertices,
        placed_settlements,
        placed_cities,
        is_initial_placement=(len(placed_settlements) == 0)
    )

    if not show_road_spots:
        draw_settlement_spots(
            surface,
            valid_settlements,
            mouse_pos,
            hex_positions
        )

    draw_settlements(surface, placed_settlements, player_colors)

    # =========================
    # ROAD PREVIEW
    # =========================
    if show_road_spots:
        # TEMP: allow all edges (remove last_settlement restriction for now)
        valid_roads = calculate_valid_roads(
            edges,
            placed_roads,
            last_settlement
        )

        draw_road_spots(surface, valid_roads, mouse_pos)
    else:
        valid_roads = set()

    draw_roads(surface, placed_roads, player_colors)

    # =========================
    # PORT ICONS (TOP LAYER)
    # =========================
    for p, t in ports:
        draw_port(surface, p, t, icons)

    # =========================
    # RETURN BOTH
    # =========================
    return valid_settlements, valid_roads