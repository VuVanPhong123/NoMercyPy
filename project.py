from __future__ import annotations

import logging
import random
import warnings
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Iterable

from kivy.config import Config

Config.set("graphics", "width", "1000")
Config.set("graphics", "height", "700")
Config.set("graphics", "resizable", "0")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import Sound, SoundLoader
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Rotate
from kivy.uix.widget import Widget


LOGICAL_WIDTH = 1000
LOGICAL_HEIGHT = 700
UFO_WIDTH = 25
UFO_HEIGHT = 20
RENDER_FPS = 60.0
LEGACY_TICKS_PER_SECOND = 240.0
RENDER_DT = 1.0 / RENDER_FPS
SIMULATION_DT = 1.0 / LEGACY_TICKS_PER_SECOND
FIXED_DT = SIMULATION_DT
MAX_FRAME_DT = 0.25
MAX_SIMULATION_STEPS_PER_FRAME = 16
PLAYER_SPEED = 1.0
DEBUG_MODE = False

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"


def _asset(relative: str) -> Path:
    return ASSET_DIR / relative


ASSETS: dict[str, Path] = {
    "background": _asset("background.jpg"),
    "game_over": _asset("GameOver.png"),
    "title": _asset("NoMercy!!!.png"),
    "ufo": _asset("UFO(2).png"),
    "music": _asset("song.mp3"),
    "game_over_sound": _asset("soundGameOver.mp3"),
    "congrat_1": _asset("congrat/congrat1.png"),
    "congrat_2": _asset("congrat/congrat2.png"),
    "congrat_3": _asset("congrat/congrat3.png"),
    "congrat_4": _asset("congrat/congrat4.png"),
    "congrat_5": _asset("congrat/congrat5.png"),
    "end_0": _asset("end/end.png"),
    "end_1": _asset("end/end1.png"),
    "end_2": _asset("end/end2.png"),
    "level_1_intro": _asset("waitingScreen/Level1.png"),
    "level_2_intro": _asset("waitingScreen/Level2.png"),
    "level_3_intro": _asset("waitingScreen/Level3.png"),
    "level_4_intro": _asset("waitingScreen/Level4.png"),
    "level_5_intro": _asset("waitingScreen/Level5.png"),
    "level_6_intro": _asset("waitingScreen/Level6.png"),
    "meteoroid": _asset("LV1/meteoroid.png"),
    "cloud": _asset("LV2/cloud.png"),
    "atomic_bomb": _asset("LV3/AtomicBomb.png"),
    "explosion": _asset("LV3/explosion.png"),
    "fan_1": _asset("LV3/flyingFan1.png"),
    "fan_2": _asset("LV3/FlyingFan2.png"),
    "fan_3": _asset("LV3/FlyingFan3.png"),
    "fan_4": _asset("LV3/FlyingFan4.png"),
    "fragment": _asset("LV3/Fragment.png"),
    "tornado": _asset("LV4/Tornado.png"),
    "cat": _asset("LV5/Cat1.png"),
    "dog": _asset("LV5/Dog1.png"),
    "boss_1": _asset("LV6/boss1.png"),
    "boss_2": _asset("LV6/boss2.png"),
    "boss_3": _asset("LV6/boss3.png"),
    "chocolate": _asset("LV6/chocolate.png"),
    "nutella": _asset("LV6/nutella.png"),
    "pizza": _asset("LV6/pizza.png"),
    "popcorn": _asset("LV6/popcorn.png"),
}

COLOR_KEY_ASSETS = frozenset(
    {
        "game_over",
        "ufo",
        "meteoroid",
        "cloud",
        "atomic_bomb",
        "explosion",
        "fan_1",
        "fan_2",
        "fan_3",
        "fan_4",
        "fragment",
        "tornado",
        "cat",
        "dog",
        "boss_1",
        "boss_2",
        "boss_3",
        "chocolate",
        "nutella",
        "pizza",
        "popcorn",
        "end_0",
        "end_1",
        "end_2",
    }
)


def missing_assets() -> list[Path]:
    """Return missing manifest entries without depending on the working directory."""

    return [path for path in ASSETS.values() if not path.is_file()]


def validate_asset_manifest() -> None:
    missing = missing_assets()
    if missing:
        joined = ", ".join(str(path) for path in missing)
        warnings.warn(f"Missing asset(s): {joined}", RuntimeWarning, stacklevel=2)


@dataclass
class GameRect:
    """A rectangle expressed in the original top-left logical coordinates."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def w(self) -> float:
        return self.width

    @w.setter
    def w(self, value: float) -> None:
        self.width = value

    @property
    def h(self) -> float:
        return self.height

    @h.setter
    def h(self, value: float) -> None:
        self.height = value

    def copy(self) -> "GameRect":
        return GameRect(self.x, self.y, self.width, self.height)


ENDING_RECT_0 = GameRect(200, 10, 150, 150)
ENDING_RECT_1 = GameRect(50, 250, 300, 300)
ENDING_RECT_2 = GameRect(600, 250, 300, 300)


def logical_to_kivy_rect(rect: GameRect) -> tuple[float, float, float, float]:

    return (rect.x, LOGICAL_HEIGHT - rect.y - rect.height, rect.width, rect.height)


def rectangles_collide(obstacle: GameRect, player: GameRect, inset: float = 6.0) -> bool:

    if inset < 0:
        raise ValueError("inset must be non-negative")
    return not (
        obstacle.bottom - inset < player.y
        or obstacle.y + inset > player.bottom
        or obstacle.x + inset > player.right
        or obstacle.right - inset < player.x
    )


def move_player(player: GameRect, pressed_keys: Iterable[str], speed: float = PLAYER_SPEED) -> None:
    keys = {key.lower() for key in pressed_keys}
    if "up" in keys:
        player.y -= speed
    if "down" in keys:
        player.y += speed
    if "left" in keys:
        player.x -= speed
    if "right" in keys:
        player.x += speed
    player.x = min(max(player.x, 0.0), LOGICAL_WIDTH - player.width)
    player.y = min(max(player.y, 0.0), LOGICAL_HEIGHT - player.height)


def calculate_legacy_velocity(
    start: tuple[float, float],
    target: tuple[float, float],
    dominant_speed: float = 1.0,
) -> tuple[float, float]:

    dx = target[0] - start[0]
    dy = target[1] - start[1]
    dominant_distance = max(abs(dx), abs(dy))
    if dominant_distance == 0:
        return (dominant_speed, 0.0)
    scale = dominant_speed / dominant_distance
    return (dx * scale, dy * scale)


def advance_linear(rect: GameRect, velocity: tuple[float, float]) -> None:
    rect.x += velocity[0]
    rect.y += velocity[1]


def move_homing(rect: GameRect, target: tuple[float, float], speed: float = 1.0) -> None:
    advance_linear(rect, calculate_legacy_velocity((rect.x, rect.y), target, speed))


def is_outside_playfield(rect: GameRect, margin: float = 0.0) -> bool:
    return (
        rect.right < -margin
        or rect.x > LOGICAL_WIDTH + margin
        or rect.bottom < -margin
        or rect.y > LOGICAL_HEIGHT + margin
    )


def simulation_steps_for_frame(accumulator: float, dt: float) -> tuple[float, int]:
    accumulator += min(dt, MAX_FRAME_DT)
    steps = 0
    while accumulator >= SIMULATION_DT and steps < MAX_SIMULATION_STEPS_PER_FRAME:
        accumulator -= SIMULATION_DT
        steps += 1
    return accumulator, steps


def spawn_from_edge(rect: GameRect, rng: random.Random, width: float | None = None, height: float | None = None) -> str:
    width = rect.width if width is None else width
    height = rect.height if height is None else height
    rect.width, rect.height = width, height
    edge = rng.randrange(4)
    if edge == 0:
        rect.x, rect.y = rng.uniform(0, LOGICAL_WIDTH - width), 0
        return "top"
    if edge == 1:
        rect.x, rect.y = 0, rng.uniform(0, LOGICAL_HEIGHT - height)
        return "left"
    if edge == 2:
        rect.x, rect.y = LOGICAL_WIDTH - width, rng.uniform(0, LOGICAL_HEIGHT - height)
        return "right"
    rect.x, rect.y = rng.uniform(0, LOGICAL_WIDTH - width), LOGICAL_HEIGHT - height
    return "bottom"


@dataclass
class Meteoroid:
    rect: GameRect = field(default_factory=lambda: GameRect(-10, -10, 30, 30))
    target: tuple[float, float] = (0.0, 0.0)
    velocity: tuple[float, float] = (0.0, 0.0)
    active: bool = False


@dataclass
class CloudObject:
    rect: GameRect = field(default_factory=lambda: GameRect(760, 760, 150, 100))
    active: bool = False


@dataclass
class FanObject:
    rect: GameRect
    direction: float = 1.0
    active: bool = True


@dataclass
class BombObject:
    rect: GameRect = field(default_factory=lambda: GameRect(-750, -750, 50, 50))
    previous_y: float = -750.0
    active: bool = False


@dataclass
class ExplosionObject:
    rect: GameRect = field(default_factory=lambda: GameRect(-750, -750, 10, 10))
    active: bool = False
    fragments_spawned: bool = False


@dataclass
class FragmentObject:
    rect: GameRect = field(default_factory=lambda: GameRect(-750, -750, 30, 30))
    velocity: tuple[float, float] = (0.0, 0.0)
    active: bool = False
    rotation: float = 0.0


@dataclass
class TornadoObject:
    rect: GameRect = field(default_factory=lambda: GameRect(-750, -750, 200, 200))
    velocity: tuple[float, float] = (1.0, 1.0)
    active: bool = False
    rotation: float = 0.0


@dataclass
class ChaserObject:
    rect: GameRect
    target: tuple[float, float] = (0.0, 0.0)
    velocity: tuple[float, float] = (0.0, 0.0)
    active: bool = False


@dataclass
class FoodObject:
    kind: str
    rect: GameRect
    target: tuple[float, float] = (0.0, 0.0)
    velocity: tuple[float, float] = (0.0, 0.0)
    active: bool = False
    rotation: float = 0.0


@dataclass
class BossObject:
    rect: GameRect = field(default_factory=lambda: GameRect(350, -280, 300, 239))
    frame: int = 0
    direction: int = 1


class GameScene(IntEnum):
    TITLE = 0
    LEVEL_1_INTRO = 1
    LEVEL_1_PLAYING = 2
    LEVEL_1_COMPLETE = 3
    LEVEL_2_INTRO = 4
    LEVEL_2_PLAYING = 5
    LEVEL_2_COMPLETE = 6
    LEVEL_3_INTRO = 7
    LEVEL_3_PLAYING = 8
    LEVEL_3_COMPLETE = 9
    LEVEL_4_INTRO = 10
    LEVEL_4_PLAYING = 11
    LEVEL_4_COMPLETE = 12
    LEVEL_5_INTRO = 13
    LEVEL_5_PLAYING = 14
    LEVEL_5_COMPLETE = 15
    LEVEL_6_INTRO = 16
    LEVEL_6_PLAYING = 17
    ENDING = 18


PLAYING_SCENES = frozenset(
    {
        GameScene.LEVEL_1_PLAYING,
        GameScene.LEVEL_2_PLAYING,
        GameScene.LEVEL_3_PLAYING,
        GameScene.LEVEL_4_PLAYING,
        GameScene.LEVEL_5_PLAYING,
        GameScene.LEVEL_6_PLAYING,
    }
)
INTRO_SCENES = frozenset(
    {
        GameScene.LEVEL_1_INTRO,
        GameScene.LEVEL_2_INTRO,
        GameScene.LEVEL_3_INTRO,
        GameScene.LEVEL_4_INTRO,
        GameScene.LEVEL_5_INTRO,
        GameScene.LEVEL_6_INTRO,
    }
)
COMPLETE_SCENES = frozenset(
    {
        GameScene.LEVEL_1_COMPLETE,
        GameScene.LEVEL_2_COMPLETE,
        GameScene.LEVEL_3_COMPLETE,
        GameScene.LEVEL_4_COMPLETE,
        GameScene.LEVEL_5_COMPLETE,
    }
)


class GameModel:
    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.scene = GameScene.TITLE
        self.player = GameRect(470, 325, UFO_WIDTH, UFO_HEIGHT)
        self.pressed_keys: set[str] = set()
        self.game_over = False
        self.game_over_sound_played = False
        self.quit_requested = False
        self.reset_level_data()

    @property
    def level_number(self) -> int:
        if self.scene == GameScene.TITLE:
            return 1
        return min(6, max(1, (int(self.scene) - 1) // 3 + 1))

    def set_scene(self, scene: GameScene) -> None:
        self.scene = GameScene(scene)
    def skip_current_level(self) -> None:

        if self.scene not in PLAYING_SCENES:
            return

        self.game_over = False
        self.game_over_sound_played = False
        self.pressed_keys.clear()

        if self.scene == GameScene.LEVEL_6_PLAYING:
            self.set_scene(GameScene.ENDING)
            self.boss.rect = GameRect(350, -280, 300, 239)
            self.ending_ticks = 0
            self.ending_complete = False
            return

        next_scene = GameScene(int(self.scene) + 1)
        self.complete_current_level(next_scene)
    def advance_scene(self) -> None:
        if self.scene == GameScene.TITLE:
            self.set_scene(GameScene.LEVEL_1_INTRO)
        elif self.scene in INTRO_SCENES:
            self.set_scene(GameScene(int(self.scene) + 1))
            self.reset_level_data()
        elif self.scene in COMPLETE_SCENES:
            self.set_scene(GameScene(int(self.scene) + 1))
        self.game_over = False

    def skip_current_level(self) -> None:
        """Debug shortcut: skip the current playing level."""

        if self.scene not in PLAYING_SCENES:
            return

        self.game_over = False
        self.game_over_sound_played = False
        self.pressed_keys.clear()

        if self.scene == GameScene.LEVEL_6_PLAYING:
            self.set_scene(GameScene.ENDING)
            self.boss.rect = GameRect(350, -280, 300, 239)
            self.ending_ticks = 0
            self.ending_complete = False
            return

        next_scene = GameScene(int(self.scene) + 1)
        self.complete_current_level(next_scene)

    def reset_all(self) -> None:
        self.scene = GameScene.TITLE
        self.player = GameRect(470, 325, UFO_WIDTH, UFO_HEIGHT)
        self.game_over = False
        self.game_over_sound_played = False
        self.quit_requested = False
        self.reset_level_data()

    def reset_current_level(self) -> None:
        scene = self.scene
        if self.game_over and scene in PLAYING_SCENES:
            self.reset_level_data()
            self.game_over = False
            self.game_over_sound_played = False
            return
        self.reset_level_data()

    def reset_level_data(self) -> None:
        self.player = GameRect(470, 325, UFO_WIDTH, UFO_HEIGHT)
        self.meteoroids = [Meteoroid() for _ in range(9)]
        self.meteoroid_count = 0

        self.clouds = [CloudObject() for _ in range(10)]
        self.cloud_wave = 0
        self.cloud_missing = 5

        self.fans = [FanObject(GameRect(2 + index * 300, 0, 70, 70)) for index in range(4)]
        self.bombs = [BombObject() for _ in range(4)]
        self.explosions = [ExplosionObject() for _ in range(4)]
        velocities = ((1, -1), (2, 0), (1, 1), (-1, 1), (-2, 0), (-2, -2))
        self.fragments = [
            [FragmentObject(velocity=velocity) for velocity in velocities] for _ in range(4)
        ]
        self.level_3_wave = 0
        self.fan_animation_tick = 0
        self.fragment_angle = 0.0

        self.tornadoes = [TornadoObject() for _ in range(5)]
        self.level_4_count = 0
        self.tornado_pulse_expanding = True
        self.tornado_animation_tick = 0
        self.tornado_angle = 0.0

        self.level_5_clouds = [CloudObject() for _ in range(10)]
        self.cats = [ChaserObject(GameRect(750, 750, 35, 35)) for _ in range(10)]
        self.dogs = [ChaserObject(GameRect(800, 800, 35, 35)) for _ in range(10)]
        self.dog_cat_counter = 0
        self.level_5_animation_tick = 0

        self.boss = BossObject()
        self.boss_phase = 1
        self.boss_phase_ticks = 0
        self.boss_condition = 0
        self.boss_animation_tick = 0
        self.boss_clouds = [
            CloudObject(GameRect(index * 100, 0, 150, 100), True) for index in range(10)
        ]
        food_sizes = {"nutella": (50, 60), "popcorn": (50, 50), "pizza": (50, 80), "chocolate": (50, 80)}
        self.food_groups: dict[str, list[FoodObject]] = {}
        for kind, (width, height) in food_sizes.items():
            self.food_groups[kind] = [
                FoodObject(kind, GameRect(750, 750, width, height)) for _ in range(5)
            ]
        self.food = [item for group in self.food_groups.values() for item in group]
        self.ending_ticks = 0
        self.ending_complete = False

    def handle_key_down(self, key: str) -> None:
        key = key.lower()
        if key in {"up", "down", "left", "right"}:
            self.pressed_keys.add(key)
            return
        if DEBUG_MODE and key == "n" and self.scene in PLAYING_SCENES:
            self.skip_current_level()
            return
        if key == "x" and not self.game_over and (
            self.scene == GameScene.TITLE or self.scene in INTRO_SCENES or self.scene in COMPLETE_SCENES
        ):
            self.advance_scene()
            return
        if key == "1" and self.game_over and self.scene in PLAYING_SCENES:
            self.reset_current_level()
            return
        if key == "1" and self.scene == GameScene.ENDING and self.ending_complete:
            self.reset_all()
            return
        if key == "2" and (self.game_over or (self.scene == GameScene.ENDING and self.ending_complete)):
            self.quit_requested = True

    def handle_key_up(self, key: str) -> None:
        self.pressed_keys.discard(key.lower())

    def update_fixed(self) -> None:
        if self.game_over:
            return
        if self.scene in PLAYING_SCENES or (self.scene == GameScene.ENDING and not self.ending_complete):
            move_player(self.player, self.pressed_keys)
        if self.scene == GameScene.LEVEL_1_PLAYING:
            self.update_level_1()
        elif self.scene == GameScene.LEVEL_2_PLAYING:
            self.update_level_2()
        elif self.scene == GameScene.LEVEL_3_PLAYING:
            self.update_level_3()
        elif self.scene == GameScene.LEVEL_4_PLAYING:
            self.update_level_4()
        elif self.scene == GameScene.LEVEL_5_PLAYING:
            self.update_level_5()
        elif self.scene == GameScene.LEVEL_6_PLAYING:
            self.update_level_6()
        elif self.scene == GameScene.ENDING:
            self.update_ending()

    def complete_current_level(self, next_scene: GameScene) -> None:
        self.game_over = False
        self.game_over_sound_played = False
        self.reset_level_data()
        self.set_scene(next_scene)

    def mark_game_over(self) -> None:
        if not self.game_over:
            self.game_over = True
            self.game_over_sound_played = False

    def update_level_1(self) -> None:
        for meteoroid in self.meteoroids:
            if not meteoroid.active or is_outside_playfield(
                meteoroid.rect, margin=max(meteoroid.rect.width, meteoroid.rect.height)
            ):
                spawn_from_edge(meteoroid.rect, self.rng, 30, 30)
                meteoroid.target = (self.player.x, self.player.y)
                meteoroid.velocity = calculate_legacy_velocity(
                    (meteoroid.rect.x, meteoroid.rect.y), meteoroid.target
                )
                meteoroid.active = True
                self.meteoroid_count += 1
            advance_linear(meteoroid.rect, meteoroid.velocity)
            if rectangles_collide(meteoroid.rect, self.player):
                self.mark_game_over()
        if self.meteoroid_count >= 70 and not self.game_over:
            self.complete_current_level(GameScene.LEVEL_1_COMPLETE)

    def spawn_cloud_wave(self, clouds: list[CloudObject], missing: int) -> None:
        for index, cloud in enumerate(clouds):
            cloud.rect = GameRect(index * 100, 0, 150, 100)
            cloud.active = index != missing

    def update_level_2(self) -> None:
        active_clouds = [cloud for cloud in self.clouds if cloud.active]
        if not active_clouds:
            self.spawn_cloud_wave(self.clouds, self.cloud_missing)
            active_clouds = [cloud for cloud in self.clouds if cloud.active]
        for cloud in active_clouds:
            cloud.rect.y += 2
            if rectangles_collide(cloud.rect, self.player):
                self.mark_game_over()
        if active_clouds and max(cloud.rect.y for cloud in active_clouds) >= LOGICAL_HEIGHT:
            self.cloud_wave += 1
            delta = self.rng.choice((-2, 2))
            if delta > 0 and self.cloud_missing < 8:
                self.cloud_missing += 2
            elif delta < 0 and self.cloud_missing > 1:
                self.cloud_missing -= 2
            self.spawn_cloud_wave(self.clouds, self.cloud_missing)
        if self.cloud_wave >= 20 and not self.game_over:
            self.complete_current_level(GameScene.LEVEL_2_COMPLETE)

    def fan_cycle_is_active(self, index: int) -> bool:
        return (
            self.bombs[index].active
            or self.explosions[index].active
            or any(fragment.active for fragment in self.fragments[index])
        )

    def update_level_3(self) -> None:
        self.fan_animation_tick = (self.fan_animation_tick + 1) % 80
        fan_frame = self.fan_animation_tick // 20
        for index, fan in enumerate(self.fans):
            fan.rect.x += fan.direction
            if fan.rect.x <= 0:
                fan.rect.x, fan.direction = 0, 1
            elif fan.rect.right >= LOGICAL_WIDTH:
                fan.rect.x, fan.direction = LOGICAL_WIDTH - fan.rect.width, -1
            if abs(fan.rect.x - self.player.x) <= 1 and not self.fan_cycle_is_active(index):
                bomb = self.bombs[index]
                bomb.rect = GameRect(fan.rect.x, fan.rect.y, 50, 50)
                bomb.previous_y = bomb.rect.y
                bomb.active = True
                self.level_3_wave += 1
            if rectangles_collide(fan.rect, self.player):
                self.mark_game_over()
        for index, bomb in enumerate(self.bombs):
            if not bomb.active:
                continue
            bomb.previous_y = bomb.rect.y
            bomb.rect.y += 2
            crossed_player = bomb.previous_y <= self.player.y <= bomb.rect.y
            if crossed_player:
                explosion = self.explosions[index]
                explosion.rect = GameRect(bomb.rect.x, bomb.rect.y, 10, 10)
                explosion.active = True
                explosion.fragments_spawned = False
                bomb.active = False
            if bomb.active and rectangles_collide(bomb.rect, self.player):
                self.mark_game_over()
        for index, explosion in enumerate(self.explosions):
            if explosion.active:
                if explosion.rect.width < 180 and self.fan_animation_tick % 2 == 0:
                    explosion.rect.x -= 3
                    explosion.rect.y -= 3
                    explosion.rect.width += 6
                    explosion.rect.height += 6
                if explosion.rect.width >= 160 and not explosion.fragments_spawned:
                    for fragment in self.fragments[index]:
                        fragment.rect = GameRect(explosion.rect.x + 60, explosion.rect.y + 60, 30, 30)
                        fragment.active = True
                    explosion.fragments_spawned = True
                if explosion.rect.width >= 170:
                    explosion.active = False
                if rectangles_collide(explosion.rect, self.player):
                    self.mark_game_over()
        for group in self.fragments:
            for fragment in group:
                if fragment.active:
                    advance_linear(fragment.rect, fragment.velocity)
                    fragment.rotation = (fragment.rotation + 1.0) % 360
                    if rectangles_collide(fragment.rect, self.player):
                        self.mark_game_over()
                    if is_outside_playfield(fragment.rect, margin=max(fragment.rect.width, fragment.rect.height)):
                        fragment.active = False
        self.fragment_angle = (self.fragment_angle + 1.0) % 360
        if self.level_3_wave >= 30 and not self.game_over:
            self.complete_current_level(GameScene.LEVEL_3_COMPLETE)
        self.current_fan_frame = fan_frame

    def update_level_4(self) -> None:
        self.tornado_animation_tick += 1
        for tornado in self.tornadoes:
            if not tornado.active:
                spawn_from_edge(tornado.rect, self.rng, 200, 200)
                tornado.velocity = (1.0 if self.rng.randrange(2) else -1.0, 1.0 if self.rng.randrange(2) else -1.0)
                tornado.active = True
                self.level_4_count += 1
            if self.tornado_animation_tick % 20 == 0:
                delta = 2 if self.tornado_pulse_expanding else -2
                tornado.rect.width += delta
                tornado.rect.height += delta
                tornado.rect.x -= delta / 2
                tornado.rect.y -= delta / 2
            else:
                if tornado.rect.x <= 0 or tornado.rect.right >= LOGICAL_WIDTH:
                    tornado.velocity = (-tornado.velocity[0], tornado.velocity[1])
                    tornado.rect.x = min(max(tornado.rect.x, 0), LOGICAL_WIDTH - max(tornado.rect.width, 0))
                if tornado.rect.y <= 0 or tornado.rect.bottom >= LOGICAL_HEIGHT:
                    tornado.velocity = (tornado.velocity[0], -tornado.velocity[1])
                    tornado.rect.y = min(max(tornado.rect.y, 0), LOGICAL_HEIGHT - max(tornado.rect.height, 0))
                advance_linear(tornado.rect, tornado.velocity)
            if tornado.active and tornado.rect.width > 0 and tornado.rect.height > 0:
                if rectangles_collide(tornado.rect, self.player):
                    self.mark_game_over()
            if not self.tornado_pulse_expanding and tornado.rect.width <= 0:
                tornado.active = False
                tornado.rect = GameRect(-750, -750, 200, 200)
            tornado.rotation = (tornado.rotation + 5.0) % 360
        if self.tornadoes and self.tornadoes[0].rect.width >= 190:
            self.tornado_pulse_expanding = False
        if all(not tornado.active for tornado in self.tornadoes):
            self.tornado_pulse_expanding = True
        self.tornado_angle = (self.tornado_angle + 5.0) % 360
        if self.level_4_count >= 30 and not self.game_over:
            self.complete_current_level(GameScene.LEVEL_4_COMPLETE)

    def update_level_5(self) -> None:
        if not any(cloud.active for cloud in self.level_5_clouds):
            self.spawn_cloud_wave(self.level_5_clouds, -1)
        self.level_5_animation_tick = (self.level_5_animation_tick + 1) % 80
        for cloud in self.level_5_clouds:
            if rectangles_collide(cloud.rect, self.player):
                self.mark_game_over()
        if self.dog_cat_counter > 9:
            for cloud in self.level_5_clouds:
                cloud.rect.y += 10
            self.dog_cat_counter = 0
        if self.level_5_animation_tick % 10 == 0:
            cat = next((item for item in self.cats if not item.active), None)
            if cat is not None:
                cat.rect.x = self.rng.uniform(0, LOGICAL_WIDTH - cat.rect.width)
                cat.rect.y = self.level_5_clouds[0].rect.y
                cat.active = True
        for cat in self.cats:
            if cat.active:
                cat.rect.y += 1 if cat.rect.y - self.level_5_clouds[0].rect.y < 200 else 3
                if rectangles_collide(cat.rect, self.player):
                    self.mark_game_over()
                if cat.rect.y > LOGICAL_HEIGHT + 50:
                    cat.active = False
        for dog in self.dogs:
            if not dog.active and dog.rect.y >= 650 + self.rng.randrange(150):
                dog.rect.x = self.rng.uniform(0, LOGICAL_WIDTH - dog.rect.width)
                dog.rect.y = self.level_5_clouds[0].rect.y
                dog.target = (self.player.x, self.player.y)
                dog.velocity = calculate_legacy_velocity((dog.rect.x, dog.rect.y), dog.target)
                dog.active = True
                self.dog_cat_counter += 1
            if dog.active:
                advance_linear(dog.rect, dog.velocity)
                if rectangles_collide(dog.rect, self.player):
                    self.mark_game_over()
                if is_outside_playfield(dog.rect, margin=max(dog.rect.width, dog.rect.height)):
                    dog.active = False
                    dog.rect = GameRect(800, 800, 35, 35)
        if self.level_5_clouds[0].rect.y >= 150 and not self.game_over:
            self.complete_current_level(GameScene.LEVEL_5_COMPLETE)

    def _update_boss_animation(self) -> None:
        self.boss_animation_tick += 1
        self.boss.frame += self.boss.direction
        if self.boss.frame >= 74 or self.boss.frame <= 0:
            self.boss.direction = -self.boss.direction
            self.boss.frame = min(74, max(0, self.boss.frame))

    def _spawn_food_item(self, kind: str, index: int) -> None:
        group = self.food_groups[kind]
        item = group[index]
        if item.active:
            return
        previous_y = group[index - 1].rect.y if index else 0
        if kind == "nutella":
            ready = item.rect.y >= 700 and (index == 0 or previous_y > 250)
        elif kind == "popcorn":
            ready = item.rect.y >= 750 and (index == 0 and self.food_groups["nutella"][0].rect.y > 270 or index > 0 and previous_y > 350)
        elif kind == "pizza":
            ready = item.rect.y >= 750 and (index == 0 and self.food_groups["popcorn"][0].rect.y > 270 or index > 0 and previous_y > 450)
        else:
            ready = item.rect.y >= 750 and (index == 0 and self.food_groups["popcorn"][0].rect.y > 270 or index > 0 and previous_y > 250)
        if not ready:
            return
        item.rect.x = self.boss.rect.x + 150
        item.rect.y = self.boss.rect.y + 100
        item.target = (self.player.x, self.player.y)
        item.velocity = calculate_legacy_velocity((item.rect.x, item.rect.y), item.target)
        item.active = True
        if kind == "chocolate" and index > 0:
            self.boss_condition += 1

    def _update_food(self) -> None:
        for kind, group in self.food_groups.items():
            for index, item in enumerate(group):
                self._spawn_food_item(kind, index)
                if not item.active:
                    continue
                advance_linear(item.rect, item.velocity)
                item.rotation = (item.rotation + 2) % 360
                if rectangles_collide(item.rect, self.player):
                    self.mark_game_over()
                if is_outside_playfield(item.rect, margin=max(item.rect.width, item.rect.height)):
                    item.active = False
                    item.rect.x, item.rect.y = 750, 750
                    item.target = (0.0, 0.0)
                    item.velocity = (0.0, 0.0)

    def _update_boss_cloud_pattern(self) -> None:
        selected = (self.cloud_missing, (self.cloud_missing + 5) % 10)
        if self.boss_clouds[self.cloud_missing].rect.y < 700:
            for index in selected:
                self.boss_clouds[index].rect.y += 1
        else:
            for index in selected:
                self.boss_clouds[index].rect.y = 290
            self.cloud_missing = self.rng.randrange(10)

    def update_level_6(self) -> None:
        self._update_boss_animation()
        if self.boss_phase == 1:
            if self.boss.rect.y < 10:
                if self.boss_animation_tick % 3 == 0:
                    self.boss.rect.y += 1
                    for cloud in self.boss_clouds:
                        cloud.rect.y += 1
            else:
                self._update_boss_cloud_pattern()
                self._update_food()
                if self.boss_condition >= 70 and not self.game_over:
                    self.boss_phase = 2
                    self.boss_phase_ticks = 0
        elif self.boss_phase == 2:
            if self.boss_phase_ticks == 0:
                for item in self.food:
                    item.active = False
                    item.rect.x, item.rect.y = 750, 750
                    item.target = (0.0, 0.0)
                    item.velocity = (0.0, 0.0)
            self.boss_phase_ticks += 1
            for cloud in self.boss_clouds:
                if cloud.rect.y > 290:
                    cloud.rect.y += 1
            if self.boss_clouds[self.cloud_missing].rect.y >= 700:
                selected = (self.cloud_missing, (self.cloud_missing + 5) % 10)
                for index in selected:
                    self.boss_clouds[index].rect.y = 290
                self.cloud_missing = self.rng.randrange(10)
            if self.boss_phase_ticks >= 1000:
                self.boss_phase = 3
        else:
            self.boss.rect.y -= 1
            for cloud in self.boss_clouds:
                cloud.rect.y -= 1
            if self.boss.rect.y <= -480:
                self.set_scene(GameScene.ENDING)
                self.ending_ticks = 0
                self.ending_complete = False
        for cloud in self.boss_clouds:
            if cloud.active and rectangles_collide(cloud.rect, self.player):
                self.mark_game_over()

    def update_ending(self) -> None:
        self._update_boss_animation()
        if self.boss.rect.y < 10:
            self.boss.rect.y += 1
            return
        self.ending_ticks += 1
        if self.ending_ticks >= 900:
            self.ending_complete = True


class NoMercyGameWidget(Widget):
    """Kivy view/controller whose only mutable gameplay source is GameModel."""

    def __init__(self, model: GameModel | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.model = model or GameModel()
        self.accumulator = 0.0
        self.pressed_keys: set[str] = self.model.pressed_keys
        self._keyboard = None
        self._textures: dict[str, object | None] = {}
        self._drawables: dict[str, tuple[Color, Rectangle, Rotate | None]] = {}
        self._music: Sound | None = None
        self._game_over_sound: Sound | None = None
        self._audio_started = False
        self._load_textures()
        self._load_audio()
        self._bind_keyboard()
        self.bind(size=lambda *_: self.render())
        Clock.schedule_interval(self.update, RENDER_DT)
        self.render()

    def _load_textures(self) -> None:
        validate_asset_manifest()
        for name, path in ASSETS.items():
            if name in {"music", "game_over_sound"}:
                continue
            if not path.is_file():
                logging.warning("Missing asset: %s", path)
                self._textures[name] = None
                continue
            try:
                self._textures[name] = CoreImage(str(path), nocache=False).texture
            except Exception as exc:
                logging.warning("Unable to load image %s: %s", path, exc)
                self._textures[name] = None

    def _load_audio(self) -> None:
        for name, path in (("music", ASSETS["music"]), ("game_over", ASSETS["game_over_sound"])):
            if not path.is_file():
                logging.warning("Missing audio: %s", path)
                continue
            try:
                sound = SoundLoader.load(str(path))
            except Exception as exc:
                logging.warning("Unable to load audio %s: %s", path, exc)
                sound = None
            if name == "music":
                self._music = sound
                if self._music is not None:
                    self._music.loop = True
                    self._music.volume = 1.0 / 6.0
            else:
                self._game_over_sound = sound

    def _bind_keyboard(self) -> None:
        try:
            self._keyboard = Window.request_keyboard(self._keyboard_closed, self, "text")
            if self._keyboard:
                self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        except Exception as exc:
            logging.warning("Keyboard unavailable: %s", exc)

    def _keyboard_closed(self) -> None:
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self._keyboard = None

    def _on_key_down(self, _keyboard: object, keycode: tuple[int, str], _text: str, _modifiers: list[str]) -> bool:
        self.model.handle_key_down(keycode[1])
        self._check_quit()
        return True

    def _on_key_up(self, _keyboard: object, keycode: tuple[int, str]) -> bool:
        self.model.handle_key_up(keycode[1])
        return True

    def _check_quit(self) -> None:
        if self.model.quit_requested:
            App.get_running_app().stop() if App.get_running_app() else None

    def update(self, dt: float) -> None:
        self.accumulator, steps = simulation_steps_for_frame(self.accumulator, dt)
        for _ in range(steps):
            self.model.update_fixed()
        self._play_audio_once()
        self.render()
        self._check_quit()

    def _play_audio_once(self) -> None:
        if self._music is not None and not self._audio_started:
            try:
                self._music.play()
                self._audio_started = True
            except Exception as exc:
                logging.warning("Unable to play music: %s", exc)
        if self.model.game_over and not self.model.game_over_sound_played:
            self.model.game_over_sound_played = True
            if self._game_over_sound is not None:
                try:
                    self._game_over_sound.stop()
                    self._game_over_sound.play()
                except Exception as exc:
                    logging.warning("Unable to play game-over sound: %s", exc)

    def _scaled_rect(self, rect: GameRect) -> tuple[float, float, float, float]:
        scale = min(self.width / LOGICAL_WIDTH if self.width else 1.0, self.height / LOGICAL_HEIGHT if self.height else 1.0)
        view_width, view_height = LOGICAL_WIDTH * scale, LOGICAL_HEIGHT * scale
        offset_x, offset_y = (self.width - view_width) / 2.0, (self.height - view_height) / 2.0
        logical_x, logical_y, width, height = logical_to_kivy_rect(rect)
        return (offset_x + logical_x * scale, offset_y + logical_y * scale, width * scale, height * scale)

    def _rectangle(
        self,
        name: str,
        rect: GameRect,
        texture_name: str | None,
        visible: bool = True,
        rotation: float | None = None,
    ) -> None:
        if name not in self._drawables:
            color = Color(1, 1, 1, 1)
            rotate = None
            if rotation is not None:
                self.canvas.add(PushMatrix())
                rotate = Rotate(angle=rotation)
                self.canvas.add(rotate)
            rectangle = Rectangle(texture=self._textures.get(texture_name) if texture_name else None)
            self.canvas.add(color)
            self.canvas.add(rectangle)
            if rotation is not None:
                self.canvas.add(PopMatrix())
            self._drawables[name] = (color, rectangle, rotate)
        color, rectangle, rotate = self._drawables[name]
        rectangle.texture = self._textures.get(texture_name) if texture_name else None
        screen_rect = self._scaled_rect(rect)
        rectangle.pos = screen_rect[:2] if visible else (0, 0)
        rectangle.size = screen_rect[2:] if visible else (0, 0)
        if rotate is not None:
            rotate.angle = rotation or 0.0
            rotate.origin = (screen_rect[0] + screen_rect[2] / 2, screen_rect[1] + screen_rect[3] / 2)
        color.a = 1 if visible else 0

    def _full_screen(self, name: str, texture_name: str | None, visible: bool = True) -> None:
        self._rectangle(name, GameRect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), texture_name, visible)

    def render(self) -> None:
        self._hide_all_scene_layers()
        scene = self.model.scene
        if scene == GameScene.TITLE:
            self._full_screen("title", "title")
            return
        if scene in INTRO_SCENES or scene in COMPLETE_SCENES:
            self._full_screen("screen", self._scene_texture(scene))
            return
        self._full_screen("background", "background")
        if scene in PLAYING_SCENES or scene == GameScene.ENDING:
            self._render_world()
        if self.model.game_over:
            self._full_screen("game_over", "game_over")

    def _hide_drawable(self, name: str) -> None:
        drawable = self._drawables.get(name)
        if drawable is None:
            return
        color, rectangle, _rotate = drawable
        color.a = 0
        rectangle.size = (0, 0)

    def _hide_all_scene_layers(self) -> None:
        for name in tuple(self._drawables):
            self._hide_drawable(name)

    def _scene_texture(self, scene: GameScene) -> str:
        if scene in INTRO_SCENES:
            return f"level_{((int(scene) + 2) // 3)}_intro"
        return f"congrat_{((int(scene) + 1) // 3)}"

    def _render_world(self) -> None:
        model = self.model
        self._rectangle("world_player", model.player, "ufo")
        if model.scene == GameScene.LEVEL_1_PLAYING:
            for index, item in enumerate(model.meteoroids):
                self._rectangle(f"world_meteor_{index}", item.rect, "meteoroid", item.active)
        elif model.scene == GameScene.LEVEL_2_PLAYING:
            for index, item in enumerate(model.clouds):
                self._rectangle(f"world_cloud_{index}", item.rect, "cloud", item.active)
        elif model.scene == GameScene.LEVEL_3_PLAYING:
            for index, item in enumerate(model.fans):
                self._rectangle(f"world_fan_{index}", item.rect, f"fan_{model.current_fan_frame + 1}")
            for index, item in enumerate(model.bombs):
                self._rectangle(f"world_bomb_{index}", item.rect, "atomic_bomb", item.active)
            for index, item in enumerate(model.explosions):
                self._rectangle(f"world_explosion_{index}", item.rect, "explosion", item.active)
            for index, group in enumerate(model.fragments):
                for part, item in enumerate(group):
                    self._rectangle(
                        f"world_fragment_{index}_{part}",
                        item.rect,
                        "fragment",
                        item.active,
                        item.rotation,
                    )
        elif model.scene == GameScene.LEVEL_4_PLAYING:
            for index, item in enumerate(model.tornadoes):
                self._rectangle(f"world_tornado_{index}", item.rect, "tornado", item.active, item.rotation)
        elif model.scene == GameScene.LEVEL_5_PLAYING:
            for index, item in enumerate(model.level_5_clouds):
                self._rectangle(f"world_l5_cloud_{index}", item.rect, "cloud", item.active)
            for index, item in enumerate(model.cats):
                self._rectangle(f"world_cat_{index}", item.rect, "cat", item.active)
            for index, item in enumerate(model.dogs):
                self._rectangle(f"world_dog_{index}", item.rect, "dog", item.active)
        elif model.scene == GameScene.LEVEL_6_PLAYING or model.scene == GameScene.ENDING:
            self._rectangle("world_boss", model.boss.rect, f"boss_{model.boss.frame // 25 + 1}")
            for index, item in enumerate(model.boss_clouds):
                self._rectangle(f"world_boss_cloud_{index}", item.rect, "cloud", item.active)
            for index, item in enumerate(model.food):
                self._rectangle(f"world_food_{index}", item.rect, item.kind, item.active, item.rotation)
            if model.scene == GameScene.ENDING:
                self._rectangle("ending_0", ENDING_RECT_0, "end_0", model.ending_ticks >= 300)
                self._rectangle("ending_1", ENDING_RECT_1, "end_1", model.ending_ticks >= 600)
                self._rectangle("ending_2", ENDING_RECT_2, "end_2", model.ending_ticks >= 900)

    def shutdown(self) -> None:
        Clock.unschedule(self.update)
        self._keyboard_closed()
        if self._music is not None:
            self._music.stop()
        if self._game_over_sound is not None:
            self._game_over_sound.stop()


class NoMercyApp(App):
    title = "NO MERCY"

    def build(self) -> NoMercyGameWidget:
        return NoMercyGameWidget()

    def on_stop(self) -> None:
        if self.root is not None and isinstance(self.root, NoMercyGameWidget):
            self.root.shutdown()


def main() -> None:
    NoMercyApp().run()


if __name__ == "__main__":
    main()
