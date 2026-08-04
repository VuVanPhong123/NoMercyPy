import os
import random

os.environ.setdefault("KIVY_NO_ARGS", "1")

import project


def playing_model(scene: project.GameScene, seed: int = 7) -> project.GameModel:
    model = project.GameModel(seed=seed)
    model.set_scene(scene)
    model.reset_level_data()
    return model


def test_import_safety_and_constants() -> None:
    assert project.LOGICAL_WIDTH == 1000
    assert project.LOGICAL_HEIGHT == 700
    assert project.RENDER_DT == 1 / 60
    assert project.SIMULATION_DT == 1 / 240
    assert project.FIXED_DT == project.SIMULATION_DT
    remainder, steps = project.simulation_steps_for_frame(0.0, 1 / 60)
    assert steps == 4
    assert remainder < project.SIMULATION_DT
    remainder, steps = project.simulation_steps_for_frame(0.0, 1.0)
    assert steps == project.MAX_SIMULATION_STEPS_PER_FRAME
    assert remainder > 0
    assert project.GameScene.TITLE == 0
    assert project.GameScene.ENDING == 18


def test_collision_uses_logical_coordinates_and_inset() -> None:
    obstacle = project.GameRect(10, 10, 30, 30)
    assert not project.rectangles_collide(obstacle, project.GameRect(100, 100, 10, 10))
    assert project.rectangles_collide(obstacle, project.GameRect(20, 20, 10, 10))
    assert project.rectangles_collide(obstacle, project.GameRect(34, 10, 10, 10))
    assert project.rectangles_collide(obstacle, project.GameRect(15, 15, 5, 5))
    assert project.rectangles_collide(project.GameRect(-20, 10, 30, 30), project.GameRect(0, 20, 20, 20))
    assert not project.rectangles_collide(project.GameRect(0, 0, 5, 5), project.GameRect(20, 20, 5, 5))
    assert project.rectangles_collide(project.GameRect(10.5, 10.5, 30.25, 30.25), project.GameRect(20.0, 20.0, 5.0, 5.0))


def test_logical_to_kivy_conversion() -> None:
    assert project.logical_to_kivy_rect(project.GameRect(10, 20, 30, 40)) == (10, 640, 30, 40)


def test_player_moves_in_two_directions_and_stays_in_bounds() -> None:
    player = project.GameRect(1, 1, project.UFO_WIDTH, project.UFO_HEIGHT)
    project.move_player(player, {"right", "down"})
    assert (player.x, player.y) == (2, 2)
    project.move_player(player, {"left", "up"}, speed=10000)
    assert (player.x, player.y) == (0, 0)
    project.move_player(player, {"right", "down"}, speed=10000)
    assert player.x == project.LOGICAL_WIDTH - project.UFO_WIDTH
    assert player.y == project.LOGICAL_HEIGHT - project.UFO_HEIGHT


def test_meteoroid_spawn_is_seeded_and_homing_handles_same_axis() -> None:
    first = project.Meteoroid()
    second = project.Meteoroid()
    rng_a = random.Random(11)
    rng_b = random.Random(11)
    assert project.spawn_from_edge(first.rect, rng_a, 30, 30) == project.spawn_from_edge(second.rect, rng_b, 30, 30)
    assert first.rect == second.rect
    target = (first.rect.x, first.rect.y + 100)
    velocity = project.calculate_legacy_velocity((first.rect.x, first.rect.y), target)
    assert max(abs(value) for value in velocity) == 1
    project.advance_linear(first.rect, velocity)
    assert first.rect.y > target[1] - 100


def test_projectile_passes_target_and_does_not_stop() -> None:
    rect = project.GameRect(0, 0, 2, 2)
    velocity = project.calculate_legacy_velocity((0, 0), (10, 0))
    for _ in range(15):
        project.advance_linear(rect, velocity)
    assert rect.x > 10
    diagonal = project.calculate_legacy_velocity((0, 0), (10, 20))
    assert max(abs(value) for value in diagonal) == 1
    rect = project.GameRect(0, 0, 2, 2)
    for _ in range(21):
        project.advance_linear(rect, diagonal)
    assert rect.y > 20
    fallback = project.calculate_legacy_velocity((5, 5), (5, 5))
    assert fallback == (1, 0)


def test_legacy_speed_calibration() -> None:
    player = project.GameRect(0, 100, project.UFO_WIDTH, project.UFO_HEIGHT)
    for _ in range(int(project.LEGACY_TICKS_PER_SECOND)):
        project.move_player(player, {"right"})
    assert player.x == 240
    cloud = project.GameRect(100, 0, 150, 100)
    for _ in range(int(project.LEGACY_TICKS_PER_SECOND)):
        cloud.y += 2
    assert cloud.y == 480
    rect = project.GameRect(0, 0, 30, 30)
    velocity = project.calculate_legacy_velocity((0, 0), (200, 100))
    for _ in range(int(project.LEGACY_TICKS_PER_SECOND)):
        project.advance_linear(rect, velocity)
    assert rect.x == 240


def test_is_outside_playfield_checks_all_four_edges() -> None:
    assert project.is_outside_playfield(project.GameRect(-31, 100, 30, 30))
    assert project.is_outside_playfield(project.GameRect(1001, 100, 30, 30))
    assert project.is_outside_playfield(project.GameRect(100, -31, 30, 30))
    assert project.is_outside_playfield(project.GameRect(100, 701, 30, 30))
    assert not project.is_outside_playfield(project.GameRect(100, 100, 30, 30))


def test_level_1_spawns_nine_and_transitions_at_70() -> None:
    model = playing_model(project.GameScene.LEVEL_1_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.update_fixed()
    assert sum(item.active for item in model.meteoroids) == 9
    assert all(item.rect.width == 30 and item.rect.height == 30 for item in model.meteoroids)
    model.meteoroid_count = 70
    for item in model.meteoroids:
        item.rect = project.GameRect(900, 600, 30, 30)
        item.active = True
        item.target = (900, 600)
        item.velocity = (0, 0)
    model.update_level_1()
    assert model.scene == project.GameScene.LEVEL_1_COMPLETE


def test_level_1_meteoroid_natural_respawn_lifecycle() -> None:
    model = playing_model(project.GameScene.LEVEL_1_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.update_level_1()
    assert model.meteoroid_count == 9
    first_target = model.meteoroids[0].target
    model.player = project.GameRect(-2000, -2000, 25, 20)
    for _ in range(2500):
        model.update_level_1()
        if model.meteoroid_count > 9:
            break
    assert model.meteoroid_count > 9
    assert first_target == (-1000, -1000)
    assert not model.game_over


def test_level_2_has_one_missing_column_and_advances_after_20_waves() -> None:
    model = playing_model(project.GameScene.LEVEL_2_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    assert model.cloud_missing == 5
    model.update_level_2()
    assert sum(cloud.active for cloud in model.clouds) == 9
    missing = model.cloud_missing
    y_before = model.clouds[missing].rect.y
    model.update_level_2()
    assert model.clouds[missing].rect.y == y_before
    model.cloud_wave = 19
    for cloud in model.clouds:
        cloud.rect.y = 700
        cloud.active = True
    model.clouds[missing].active = False
    model.update_level_2()
    assert model.scene == project.GameScene.LEVEL_2_COMPLETE


def test_level_3_fans_bombs_explosion_and_fragments() -> None:
    model = playing_model(project.GameScene.LEVEL_3_PLAYING)
    model.player = project.GameRect(0, 500, 25, 20)
    fan = model.fans[0]
    fan.rect.x = 0
    fan.direction = -1
    model.update_level_3()
    assert fan.direction == 1
    fan.rect.x = model.player.x
    fan.direction = 0
    model.update_level_3()
    assert model.bombs[0].active
    model.bombs[0].rect.y = model.player.y - 2
    model.update_level_3()
    assert model.explosions[0].active
    model.explosions[0].rect.width = 160
    model.fan_animation_tick = 1
    model.update_level_3()
    assert all(fragment.active for fragment in model.fragments[0])
    model.level_3_wave = 30
    model.game_over = False
    for bomb in model.bombs:
        bomb.active = False
    for explosion in model.explosions:
        explosion.active = False
    for group in model.fragments:
        for fragment in group:
            fragment.active = False
    for item in model.fans:
        item.rect = project.GameRect(900, 600, 70, 70)
    model.update_level_3()
    assert model.scene == project.GameScene.LEVEL_3_COMPLETE


def test_level_4_bounces_pulses_and_transitions() -> None:
    model = playing_model(project.GameScene.LEVEL_4_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.tornadoes[0].active = True
    model.tornadoes[0].rect = project.GameRect(0, 300, 188, 188)
    model.tornadoes[0].velocity = (-1, 0)
    model.tornado_animation_tick = 18
    model.update_level_4()
    assert model.tornadoes[0].velocity[0] == 1
    model.tornado_animation_tick = 19
    model.update_level_4()
    assert model.tornadoes[0].rect.width == 190
    assert not model.tornado_pulse_expanding
    model.level_4_count = 30
    for item in model.tornadoes:
        item.rect = project.GameRect(900, 500, 50, 50)
        item.active = True
    model.update_level_4()
    assert model.scene == project.GameScene.LEVEL_4_COMPLETE


def test_level_5_dog_uses_target_snapshot_and_cloud_row_threshold() -> None:
    model = playing_model(project.GameScene.LEVEL_5_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    dog = model.dogs[0]
    dog.active = True
    dog.rect = project.GameRect(0, 0, 35, 35)
    dog.target = (100, 0)
    dog.velocity = project.calculate_legacy_velocity((0, 0), dog.target)
    model.update_level_5()
    assert dog.rect.x > 0
    model.level_5_clouds[0].rect.y = 150
    for cloud in model.level_5_clouds:
        cloud.rect = project.GameRect(900, 600, 50, 50)
    model.update_level_5()
    assert model.scene == project.GameScene.LEVEL_5_COMPLETE


def test_boss_phases_and_ending_thresholds() -> None:
    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.boss.rect.y = 10
    model.boss_condition = 70
    model.update_level_6()
    assert model.boss_phase == 2
    model.boss_phase_ticks = 999
    model.update_level_6()
    assert model.boss_phase == 3
    model.boss.rect.y = -480
    model.update_level_6()
    assert model.scene == project.GameScene.ENDING
    model.boss.rect.y = 10
    model.ending_ticks = 899
    model.update_ending()
    assert model.ending_complete


def test_state_input_game_over_replay_quit_and_ending_restart() -> None:
    model = project.GameModel(seed=1)
    model.handle_key_down("x")
    assert model.scene == project.GameScene.LEVEL_1_INTRO
    model.handle_key_down("x")
    assert model.scene == project.GameScene.LEVEL_1_PLAYING
    model.handle_key_down("x")
    assert model.scene == project.GameScene.LEVEL_1_PLAYING
    model.mark_game_over()
    model.meteoroid_count = 12
    model.handle_key_down("1")
    assert not model.game_over
    assert model.meteoroid_count == 0
    model.mark_game_over()
    model.handle_key_down("2")
    assert model.quit_requested
    model.reset_all()
    model.set_scene(project.GameScene.ENDING)
    model.ending_complete = True
    model.handle_key_down("1")
    assert model.scene == project.GameScene.TITLE


def test_n_skips_playing_levels_and_clears_transient_state() -> None:
    playing_levels = [
        project.GameScene.LEVEL_1_PLAYING,
        project.GameScene.LEVEL_2_PLAYING,
        project.GameScene.LEVEL_3_PLAYING,
        project.GameScene.LEVEL_4_PLAYING,
        project.GameScene.LEVEL_5_PLAYING,
    ]
    for scene in playing_levels:
        model = playing_model(scene)
        model.game_over = True
        model.game_over_sound_played = True
        model.pressed_keys.update({"left", "n"})
        model.handle_key_down("N")
        assert model.scene == project.GameScene(int(scene) + 1)
        assert not model.game_over
        assert not model.game_over_sound_played
        assert not model.pressed_keys


def test_n_skips_level_6_to_ending_and_is_ignored_elsewhere() -> None:
    model = project.GameModel(seed=5)
    model.handle_key_down("n")
    assert model.scene == project.GameScene.TITLE
    model.set_scene(project.GameScene.LEVEL_1_INTRO)
    model.handle_key_down("n")
    assert model.scene == project.GameScene.LEVEL_1_INTRO

    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    model.game_over = True
    model.game_over_sound_played = True
    model.pressed_keys.add("right")
    model.handle_key_down("n")
    assert model.scene == project.GameScene.ENDING
    assert model.boss.rect == project.GameRect(350, -280, 300, 239)
    assert model.ending_ticks == 0
    assert not model.ending_complete
    assert not model.game_over
    assert not model.game_over_sound_played
    assert not model.pressed_keys


def test_debug_mode_can_disable_n_skip() -> None:
    original_debug_mode = project.DEBUG_MODE
    try:
        project.DEBUG_MODE = False
        model = playing_model(project.GameScene.LEVEL_1_PLAYING)
        model.handle_key_down("n")
        assert model.scene == project.GameScene.LEVEL_1_PLAYING

        project.DEBUG_MODE = True
        model.handle_key_down("n")
        assert model.scene == project.GameScene.LEVEL_1_COMPLETE
    finally:
        project.DEBUG_MODE = original_debug_mode


def test_reset_clears_projectiles_and_counters() -> None:
    model = playing_model(project.GameScene.LEVEL_3_PLAYING)
    model.level_3_wave = 29
    model.bombs[0].active = True
    model.mark_game_over()
    model.handle_key_down("1")
    assert model.level_3_wave == 0
    assert not model.bombs[0].active
    assert model.player == project.GameRect(470, 325, 25, 20)


def test_level_3_lane_stays_locked_until_fragments_finish() -> None:
    model = playing_model(project.GameScene.LEVEL_3_PLAYING)
    model.player = project.GameRect(100, 500, 25, 20)
    fan = model.fans[0]
    fan.rect.x, fan.direction = 100, 0
    model.update_level_3()
    assert model.bombs[0].active
    model.bombs[0].rect.y = model.player.y - 2
    model.update_level_3()
    assert not model.bombs[0].active
    assert model.explosions[0].active
    model.explosions[0].rect.width = 160
    model.fan_animation_tick = 1
    model.update_level_3()
    assert model.fan_cycle_is_active(0)
    wave_before = model.level_3_wave
    model.update_level_3()
    assert not model.bombs[0].active
    assert model.level_3_wave == wave_before
    model.explosions[0].active = False
    for fragment in model.fragments[0]:
        fragment.active = False
    model.update_level_3()
    assert model.bombs[0].active
    assert model.level_3_wave == wave_before + 1


def test_level_4_natural_respawn_reaches_thirty() -> None:
    model = playing_model(project.GameScene.LEVEL_4_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.update_level_4()
    assert model.level_4_count == 5
    for _ in range(2050):
        model.update_level_4()
    assert model.level_4_count >= 10
    for _ in range(9000):
        if model.scene == project.GameScene.LEVEL_4_COMPLETE:
            break
        model.update_level_4()
    assert model.scene == project.GameScene.LEVEL_4_COMPLETE


def test_level_5_cat_cadence_and_dog_recycle() -> None:
    model = playing_model(project.GameScene.LEVEL_5_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    for _ in range(9):
        model.update_level_5()
    assert sum(cat.active for cat in model.cats) == 0
    model.update_level_5()
    assert sum(cat.active for cat in model.cats) == 1
    dog = model.dogs[0]
    dog.active = True
    dog.rect = project.GameRect(1000, 1000, 35, 35)
    dog.velocity = (1, 1)
    model.update_level_5()
    assert not dog.active
    assert dog.rect == project.GameRect(800, 800, 35, 35)


def test_level_5_natural_cloud_progression_completes() -> None:
    model = playing_model(project.GameScene.LEVEL_5_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    for _ in range(3000):
        if model.scene == project.GameScene.LEVEL_5_COMPLETE:
            break
        model.update_level_5()
    assert model.scene == project.GameScene.LEVEL_5_COMPLETE


def test_level_6_entrance_cloud_pattern_and_staggered_food() -> None:
    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    assert all(cloud.active and cloud.rect.y == 0 for cloud in model.boss_clouds)
    for _ in range(870):
        model.update_level_6()
    assert model.boss.rect.y == 10
    assert all(cloud.rect.y == 290 for cloud in model.boss_clouds)
    model.update_level_6()
    selected = {model.cloud_missing, (model.cloud_missing + 5) % 10}
    assert all(
        cloud.rect.y == 291 if index in selected else cloud.rect.y == 290
        for index, cloud in enumerate(model.boss_clouds)
    )
    for item in model.food_groups["nutella"]:
        item.active = False
        item.rect = project.GameRect(750, 750, 50, 60)
    model.food_groups["nutella"][0].rect.y = 700
    model.update_level_6()
    assert model.food_groups["nutella"][0].active
    assert not model.food_groups["nutella"][1].active


def test_level_6_food_passes_target_and_recycles() -> None:
    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    item = model.food_groups["chocolate"][0]
    item.active = True
    item.rect = project.GameRect(0, 0, 50, 80)
    item.target = (10, 0)
    item.velocity = project.calculate_legacy_velocity((0, 0), item.target)
    for _ in range(20):
        project.advance_linear(item.rect, item.velocity)
    assert item.rect.x > 10
    item.rect = project.GameRect(1001, 1001, 50, 80)
    model._update_food()
    assert not item.active
    assert item.rect == project.GameRect(750, 750, 50, 80)


def test_level_6_phase_two_keeps_clouds_visible_and_phase_three_exits() -> None:
    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    model.boss.rect.y = 10
    model.boss_condition = 70
    model.update_level_6()
    assert model.boss_phase == 2
    assert all(cloud.active for cloud in model.boss_clouds)
    model.boss_phase_ticks = 999
    model.update_level_6()
    assert model.boss_phase == 3
    model.boss.rect.y = -480
    model.update_level_6()
    assert model.scene == project.GameScene.ENDING


def test_render_state_hides_overlay_and_applies_rotation() -> None:
    from kivy.graphics import Rotate

    model = playing_model(project.GameScene.LEVEL_6_PLAYING)
    model.player = project.GameRect(-1000, -1000, 25, 20)
    widget = project.NoMercyGameWidget(model=model)
    try:
        assert widget._drawables["world_food_0"][2] is not None
        assert isinstance(widget._drawables["world_food_0"][2], Rotate)
        model.game_over = True
        widget.render()
        assert widget._drawables["game_over"][0].a == 1
        model.reset_current_level()
        widget.render()
        assert widget._drawables["game_over"][0].a == 0
    finally:
        widget.shutdown()


def test_assets_are_present_case_sensitively_and_without_runtime_binaries() -> None:
    assert not project.missing_assets()
    asset_root = project.ASSET_DIR
    assert asset_root.is_absolute()
    assert all(path.is_relative_to(asset_root) for path in project.ASSETS.values())
    forbidden = {".dll", ".exe", ".o", ".obj"}
    assert not any(path.suffix.lower() in forbidden for path in asset_root.rglob("*"))
    assert (asset_root / "LV3" / "flyingFan1.png").is_file()
    assert not any(path.name == "FlyingFan1.png" for path in (asset_root / "LV3").iterdir())
