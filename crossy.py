import pygame
import random

# ----------------------------
# Sensible defaults
# ----------------------------
TILE = 48
COLS = 9
ROWS_VISIBLE = 12
WIDTH = COLS * TILE
HEIGHT = ROWS_VISIBLE * TILE

FPS = 60
HOP_TIME = 0.14

LANES_BEHIND = 10
LANES_AHEAD = 30

TREE_CHANCE = 0.18

SAFE_START_ROWS = 6  # rows 0..5 are guaranteed grass

# Road / car tuning (slow cars)
ROAD_EVERY_APPROX = 5
ROAD_JITTER = 2
ROAD_SEGMENT_MIN = 1
ROAD_SEGMENT_MAX = 3

CAR_SPEED_MIN = 60
CAR_SPEED_MAX = 140
CAR_GAP_MIN_TILES = 1.2
CAR_GAP_MAX_TILES = 3.0
CAR_LEN_MIN = 1
CAR_LEN_MAX = 2

# Guaranteed path behavior on grass
PATH_WIGGLE_CHANCE = 0.6

# Timeout rule
TIMEOUT_SECONDS = 10.0

COL_GRASS = (70, 170, 80)
COL_ROAD = (55, 55, 60)
COL_TEXT = (20, 20, 20)
COL_BG = (30, 30, 30)
COL_CAR_1 = (220, 80, 80)
COL_CAR_2 = (240, 200, 70)

# Chicken colors
COL_CHICKEN_BODY = (245, 245, 245)
COL_CHICKEN_BEAK = (245, 170, 60)
COL_CHICKEN_COMB = (220, 70, 70)
COL_CHICKEN_EYE = (35, 35, 35)

# ----------------------------
# Helpers
# ----------------------------
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def lerp(a, b, t):
    return a + (b - a) * t

def world_row_to_screen_y(row: float, camera_y: float) -> float:
    return HEIGHT - ((row + 1) * TILE) + camera_y

def draw_scalloped_bush(
    surf: pygame.Surface,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int] = (30, 110, 50),  # default so we never crash
):
    """
    Flat-color circular bush with scalloped edges.
    Color can vary slightly per bush.
    """
    cx = x + w // 2
    cy = y + h // 2
    R = min(w, h) // 2

    # Main body
    pygame.draw.circle(surf, color, (cx, cy), R)

    # Bigger scallops
    bump_r = max(5, R // 2)
    ring_r = R - bump_r // 2

    bumps = max(6, int(2 * 3.14159 * ring_r / (bump_r * 2.2)))

    v = pygame.math.Vector2(1, 0)
    for i in range(bumps):
        a = (i / bumps) * 2 * 3.14159
        p = v.rotate_rad(a)
        bx = int(cx + ring_r * p.x)
        by = int(cy + ring_r * p.y)
        pygame.draw.circle(surf, color, (bx, by), bump_r)

# ----------------------------
# Cars
# ----------------------------
class Car:
    def __init__(self, x_px: float, width_tiles: int, speed_px_s: float, direction: int):
        self.x = x_px
        self.w = width_tiles * TILE
        self.speed = speed_px_s
        self.dir = direction

    def update(self, dt: float):
        self.x += self.dir * self.speed * dt
        buffer_px = 2 * TILE
        if self.dir == 1 and self.x > WIDTH + buffer_px:
            self.x = -self.w - buffer_px
        elif self.dir == -1 and self.x < -self.w - buffer_px:
            self.x = WIDTH + buffer_px

    def rect(self, lane_screen_y: float) -> pygame.Rect:
        return pygame.Rect(int(self.x + 6), int(lane_screen_y + 10), int(self.w - 12), TILE - 20)

# ----------------------------
# Lane
# ----------------------------
class Lane:
    def __init__(self, row_index: int, cols: int, kind: str, seed: int, forced_open_col: int | None = None):
        self.row = row_index
        self.kind = kind
        self.cols = cols

        self.blocked = [False] * cols
        self.cars: list[Car] = []

        rng = random.Random(seed)

        if self.kind == "grass":
            passable_cols = list(range(cols))
            rng.shuffle(passable_cols)
            guaranteed_open = passable_cols[0]

            for c in range(cols):
                if c == guaranteed_open:
                    self.blocked[c] = False
                else:
                    self.blocked[c] = (rng.random() < TREE_CHANCE)

            if forced_open_col is not None and 0 <= forced_open_col < cols:
                self.blocked[forced_open_col] = False

        elif self.kind == "road":
            direction = rng.choice([-1, 1])
            difficulty = clamp(row_index / 60.0, 0.0, 1.0)
            base_speed = lerp(CAR_SPEED_MIN, CAR_SPEED_MAX, difficulty)
            speed = base_speed * rng.uniform(0.85, 1.15)

            x = rng.uniform(-2 * TILE, 2 * TILE)
            while x < WIDTH + 3 * TILE:
                car_len = rng.randint(CAR_LEN_MIN, CAR_LEN_MAX)
                self.cars.append(Car(x_px=x, width_tiles=car_len, speed_px_s=speed, direction=direction))
                gap_tiles = rng.uniform(CAR_GAP_MIN_TILES, CAR_GAP_MAX_TILES)
                x += (car_len * TILE) + gap_tiles * TILE

    def is_blocked(self, col: int) -> bool:
        if self.kind != "grass":
            return False
        if 0 <= col < len(self.blocked):
            return self.blocked[col]
        return True

    def update(self, dt: float):
        if self.kind == "road":
            for car in self.cars:
                car.update(dt)

    def draw(self, surf: pygame.Surface, camera_y: float):
        y = world_row_to_screen_y(self.row, camera_y)

        if self.kind == "grass":
            pygame.draw.rect(surf, COL_GRASS, pygame.Rect(0, y, WIDTH, TILE))

            for c, is_tree in enumerate(self.blocked):
                if not is_tree:
                    continue

                x0 = c * TILE

                # Inner tile area for the bush
                bx = x0 + 6
                by = int(y + 6)
                bw = TILE - 12
                bh = TILE - 12

                # Slight green hue variation per bush (deterministic)
                rng = random.Random((self.row + 1) * 1000 + c)

                base_g = 170  # overall brighter green
                g = clamp(base_g + rng.randint(-6, 6), 135, 155)

                r = clamp(60 + rng.randint(-6, 6), 60, 155)
                b = clamp(60 + rng.randint(-6, 6), 60, 155)

                bush_color = (r, g, b)


                draw_scalloped_bush(surf, bx, by, bw, bh, bush_color)

        elif self.kind == "road":
            pygame.draw.rect(surf, COL_ROAD, pygame.Rect(0, y, WIDTH, TILE))
            dash_y = int(y + TILE // 2)
            for i in range(0, WIDTH, 24):
                pygame.draw.line(surf, (85, 85, 90), (i, dash_y), (i + 12, dash_y), 2)

            for idx, car in enumerate(self.cars):
                color = COL_CAR_1 if (idx % 2 == 0) else COL_CAR_2
                pygame.draw.rect(surf, color, car.rect(y), border_radius=8)

        pygame.draw.line(surf, (0, 0, 0), (0, y), (WIDTH, y), 1)

# ----------------------------
# Player (Chicken!)
# ----------------------------
class Player:
    def __init__(self, start_col: int, start_row: int):
        self.col = start_col
        self.row = start_row

        self.is_hopping = False
        self.hop_t = 0.0
        self.start_pos = (float(self.col), float(self.row))
        self.end_pos = (float(self.col), float(self.row))

        self.render_col = float(self.col)
        self.render_row = float(self.row)

        self.alive = True
        self.max_row = self.row

        self.time_in_same_row = 0.0
        self._last_row_for_timer = self.row

    def try_move(self, dcol: int, drow: int, world):
        if not self.alive or self.is_hopping:
            return

        target_col = self.col + dcol
        target_row = self.row + drow

        if target_col < 0 or target_col >= COLS:
            self.alive = False
            return

        lane = world.get_lane(target_row)
        if lane is None:
            return
        if lane.is_blocked(target_col):
            return

        self.is_hopping = True
        self.hop_t = 0.0
        self.start_pos = (float(self.col), float(self.row))
        self.end_pos = (float(target_col), float(target_row))

        self.col = target_col
        self.row = target_row
        self.max_row = max(self.max_row, self.row)

        if self.row != self._last_row_for_timer:
            self._last_row_for_timer = self.row
            self.time_in_same_row = 0.0

    def update(self, dt: float):
        if not self.alive:
            return

        self.time_in_same_row += dt

        if self.is_hopping:
            self.hop_t += dt / HOP_TIME
            t = clamp(self.hop_t, 0.0, 1.0)
            self.render_col = lerp(self.start_pos[0], self.end_pos[0], t)
            self.render_row = lerp(self.start_pos[1], self.end_pos[1], t)
            if t >= 1.0:
                self.is_hopping = False
        else:
            self.render_col = float(self.col)
            self.render_row = float(self.row)

    def rect_for_collision(self, camera_y: float) -> pygame.Rect:
        x = self.render_col * TILE
        y = world_row_to_screen_y(self.render_row, camera_y)
        return pygame.Rect(int(x + 10), int(y + 10), TILE - 20, TILE - 20)

    def draw(self, surf: pygame.Surface, camera_y: float):
        if not self.alive:
            return

        x = self.render_col * TILE
        y = world_row_to_screen_y(self.render_row, camera_y)

        lift = 0
        if self.is_hopping:
            hop_phase = clamp(self.hop_t, 0.0, 1.0)
            lift = int(8 * (1 - (2 * hop_phase - 1) ** 2))

        # Chicken body
        body = pygame.Rect(int(x + 10), int(y + 12 - lift), TILE - 20, TILE - 22)
        pygame.draw.rect(surf, COL_CHICKEN_BODY, body, border_radius=10)

        # Head
        head = pygame.Rect(int(x + 22), int(y + 6 - lift), 18, 18)
        pygame.draw.ellipse(surf, COL_CHICKEN_BODY, head)

        # Comb
        comb1 = pygame.Rect(int(x + 26), int(y + 2 - lift), 6, 6)
        comb2 = pygame.Rect(int(x + 31), int(y + 3 - lift), 6, 6)
        pygame.draw.ellipse(surf, COL_CHICKEN_COMB, comb1)
        pygame.draw.ellipse(surf, COL_CHICKEN_COMB, comb2)

        # Beak
        beak_pts = [
            (int(x + 40), int(y + 15 - lift)),
            (int(x + 46), int(y + 18 - lift)),
            (int(x + 40), int(y + 21 - lift)),
        ]
        pygame.draw.polygon(surf, COL_CHICKEN_BEAK, beak_pts)

        # Eye
        pygame.draw.circle(surf, COL_CHICKEN_EYE, (int(x + 36), int(y + 14 - lift)), 2)

        # Feet
        foot_y = int(y + 34 - lift)
        pygame.draw.line(surf, (180, 140, 70), (int(x + 20), foot_y), (int(x + 24), foot_y), 2)
        pygame.draw.line(surf, (180, 140, 70), (int(x + 30), foot_y), (int(x + 34), foot_y), 2)

# ----------------------------
# World generator (with guaranteed grass path)
# ----------------------------
class World:
    def __init__(self, cols: int):
        self.cols = cols
        self.lanes: dict[int, Lane] = {}

        self.generated_max = -999999

        self.next_road_start = 999999
        self.road_remaining = 0

        self.rng = random.Random(1337)

        self.path_col = cols // 2
        self._schedule_next_road_start(SAFE_START_ROWS - 1)

    def _schedule_next_road_start(self, current_row: int):
        delta = ROAD_EVERY_APPROX + self.rng.randint(-ROAD_JITTER, ROAD_JITTER)
        delta = max(2, delta)
        self.next_road_start = current_row + delta
        if self.next_road_start < SAFE_START_ROWS:
            self.next_road_start = SAFE_START_ROWS

    def _maybe_wiggle_path(self):
        if self.rng.random() < PATH_WIGGLE_CHANCE:
            step = self.rng.choice([-1, 0, 1])
            self.path_col = clamp(self.path_col + step, 0, self.cols - 1)

    def _make_lane(self, row: int) -> Lane:
        if row < SAFE_START_ROWS:
            seed = (row * 1000003) ^ 0x123456
            return Lane(row, self.cols, kind="grass", seed=seed, forced_open_col=self.path_col)

        if self.road_remaining > 0:
            kind = "road"
            self.road_remaining -= 1
        else:
            if row >= self.next_road_start:
                self.road_remaining = self.rng.randint(ROAD_SEGMENT_MIN, ROAD_SEGMENT_MAX)
                kind = "road"
                self.road_remaining -= 1
                self._schedule_next_road_start(row)
            else:
                kind = "grass"

        if kind == "grass":
            self._maybe_wiggle_path()
            seed = (row * 1000003) ^ 0x123456
            return Lane(row, self.cols, kind="grass", seed=seed, forced_open_col=self.path_col)

        seed = (row * 1000003) ^ 0xABCDEF
        return Lane(row, self.cols, kind="road", seed=seed)

    def ensure_range(self, row_min: int, row_max: int):
        if self.generated_max < row_min - 50:
            self.generated_max = row_min - 1
            self.next_road_start = 999999
            self.road_remaining = 0
            self.rng = random.Random(1337)
            self.path_col = self.cols // 2
            self._schedule_next_road_start(SAFE_START_ROWS - 1)

        start = max(self.generated_max + 1, row_min)
        for r in range(start, row_max + 1):
            if r not in self.lanes:
                self.lanes[r] = self._make_lane(r)
            self.generated_max = max(self.generated_max, r)

        for r in range(row_min, min(row_max, self.generated_max) + 1):
            if r not in self.lanes:
                seed = (r * 1000003) ^ 0x123456
                self.lanes[r] = Lane(r, self.cols, kind="grass", seed=seed, forced_open_col=self.path_col)

        keep_min = row_min - 2
        keep_max = row_max + 2
        to_delete = [r for r in list(self.lanes.keys()) if r < keep_min or r > keep_max]
        for r in to_delete:
            del self.lanes[r]

    def get_lane(self, row: int):
        return self.lanes.get(row)

    def update(self, dt: float, camera_y: float):
        for lane in self.lanes.values():
            y = world_row_to_screen_y(lane.row, camera_y)
            if y > HEIGHT + TILE or y < -TILE:
                continue
            lane.update(dt)

    def draw(self, surf: pygame.Surface, camera_y: float):
        for lane in self.lanes.values():
            y = world_row_to_screen_y(lane.row, camera_y)
            if y > HEIGHT + TILE or y < -TILE:
                continue
            lane.draw(surf, camera_y)

# ----------------------------
# Game
# ----------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Crossy - Chicken Mode")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)
    big_font = pygame.font.SysFont(None, 40)

    def new_game():
        world = World(COLS)
        player = Player(start_col=COLS // 2, start_row=0)
        world.ensure_range(player.row - LANES_BEHIND, player.row + LANES_AHEAD)
        return world, player, "PLAYING", 0.0, None

    world, player, state, camera_y, death_reason = new_game()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if state == "DEAD":
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_r):
                        world, player, state, camera_y, death_reason = new_game()
                    continue

                if state == "PLAYING":
                    if event.key in (pygame.K_UP, pygame.K_w):
                        player.try_move(0, 1, world)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        player.try_move(0, -1, world)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        player.try_move(-1, 0, world)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        player.try_move(1, 0, world)

        if state == "PLAYING":
            player.update(dt)
            world.ensure_range(player.row - LANES_BEHIND, player.row + LANES_AHEAD)

            if player.time_in_same_row >= TIMEOUT_SECONDS:
                player.alive = False
                death_reason = "EAGLE"

            desired_player_screen_y = HEIGHT * 0.65
            target_cam_y = ((player.render_row + 1) * TILE) - (HEIGHT - desired_player_screen_y)
            target_cam_y = max(0.0, target_cam_y)
            camera_y = lerp(camera_y, target_cam_y, 0.12)
            camera_y = max(0.0, camera_y)

            world.update(dt, camera_y)

            lane = world.get_lane(player.row)
            if lane and lane.kind == "road" and player.alive:
                p_rect = player.rect_for_collision(camera_y)
                lane_y = world_row_to_screen_y(lane.row, camera_y)
                for car in lane.cars:
                    if p_rect.colliderect(car.rect(lane_y)):
                        player.alive = False
                        death_reason = "CAR"
                        break

            if not player.alive:
                state = "DEAD"

        screen.fill(COL_BG)
        world.draw(screen, camera_y)
        player.draw(screen, camera_y)

        score = player.max_row
        screen.blit(font.render(f"Score: {score}", True, COL_TEXT), (10, 10))

        if state == "PLAYING":
            remaining = max(0.0, TIMEOUT_SECONDS - player.time_in_same_row)
            screen.blit(font.render(f"Move timer: {remaining:0.1f}s", True, COL_TEXT), (10, 34))

        if state == "DEAD":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            title = "Game Over"
            if death_reason == "EAGLE":
                subtitle = "You took too long and an eagle ate you."
            elif death_reason == "CAR":
                subtitle = "You got hit by a car."
            else:
                subtitle = "You died."

            t1 = big_font.render(title, True, (245, 245, 245))
            t2 = font.render(subtitle, True, (245, 245, 245))
            t3 = font.render(f"Score: {score}", True, (245, 245, 245))
            t4 = font.render("Enter / Space / R to restart", True, (245, 245, 245))

            screen.blit(t1, (WIDTH // 2 - t1.get_width() // 2, HEIGHT // 2 - 90))
            screen.blit(t2, (WIDTH // 2 - t2.get_width() // 2, HEIGHT // 2 - 45))
            screen.blit(t3, (WIDTH // 2 - t3.get_width() // 2, HEIGHT // 2 - 15))
            screen.blit(t4, (WIDTH // 2 - t4.get_width() // 2, HEIGHT // 2 + 20))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
