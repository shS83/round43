import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import unittest
import math
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pygame as pg
import round43 as game


class GameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.display.set_mode((1920, 1080))

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def test_movement_matches_at_different_render_rates(self):
        results = []
        for fps in (30, 60, 156):
            player = game.Player()
            start = player.pos_x
            bullet = game.Bullet(800, 1000)
            accumulator = 0.0
            for _ in range(fps):
                accumulator += 1 / fps
                while accumulator + 1e-9 >= game.STEP:
                    player.move(1, game.STEP)
                    bullet.update(game.STEP)
                    accumulator -= game.STEP
            results.append((player.pos_x - start, bullet.pos.x, bullet.pos.y))
        for distance, x, y in results:
            self.assertAlmostEqual(distance, game.PLAYER_SPEED)
            self.assertEqual(x, 800)
            self.assertAlmostEqual(y, 1000 - game.BULLET_SPEED)

    def test_enemy_waits_after_landing_and_stays_inside_edges(self):
        enemy = game.Enemy(300, 64)
        enemy.update(enemy.jump_duration)
        landed = enemy.rect.copy()
        self.assertEqual(landed.topleft, (320, 64))
        enemy.update(enemy.jump_cooldown - 0.01)
        self.assertEqual(enemy.rect, landed)
        enemy.update(0.11)
        self.assertGreater(enemy.rect.x, landed.x)
        edge = game.Enemy(game.WIDTH - game.ENEMY_SIZE[0] - 5, 64)
        for _ in range(600):
            edge.update(game.STEP)
            self.assertGreaterEqual(edge.rect.left, 0)
            self.assertLessEqual(edge.rect.right, game.WIDTH)
        self.assertGreater(edge.rect.top, 64)
        self.assertEqual(edge.direction, -1)

    def test_enemy_formation_has_gaps(self):
        sprites, enemies = pg.sprite.Group(), pg.sprite.Group()
        game.spawn_enemies(sprites, enemies, horde=8)
        self.assertEqual(len(enemies), 8)
        ordered = sorted(enemies, key=lambda enemy: enemy.rect.x)
        for left, right in zip(ordered, ordered[1:]):
            self.assertEqual(right.rect.left - left.rect.right, game.ENEMY_GAP)
        self.assertGreaterEqual(ordered[0].rect.left, 0)
        self.assertLessEqual(ordered[-1].rect.right, game.WIDTH)

    def test_powerup_grants_three_half_second_bursts(self):
        player = game.Player()
        self.assertFalse(player.start_rainbow())
        player.rainbow_charges += game.RAINBOW_CHARGES
        font = pg.font.SysFont('Arial', 32, bold=True)
        bullets = pg.sprite.Group()
        for charge in range(3):
            self.assertTrue(player.start_rainbow())
            self.assertFalse(player.start_rainbow())
            self.assertEqual(player.rainbow_charges, 2 - charge)
            with patch.object(game.RainbowBeam, 'fire') as fire:
                for _ in range(game.FPS // 2):
                    player.update_rainbow(game.STEP, (800, 100), font, bullets)
                self.assertEqual(sum(call.args[-1] for call in fire.call_args_list), game.RAINBOW_EMISSION_RATE // 2)
                self.assertEqual(player.rainbow_remaining, 0)
                calls = fire.call_count
                player.update_rainbow(1, (800, 100), font, bullets)
                self.assertEqual(fire.call_count, calls)
        self.assertFalse(player.start_rainbow())

    def test_powerup_falls_and_can_be_collected(self):
        player = game.Player()
        drops = pg.sprite.Group()
        drop = game.PowerUp(player.rect.centerx, player.rect.top - 30, drops)
        drop.update(0.2)
        hits = pg.sprite.spritecollide(player, drops, True)
        self.assertEqual(hits, [drop])
        self.assertFalse(drop.alive())
        player.rainbow_charges += len(hits) * game.RAINBOW_CHARGES
        self.assertEqual(player.rainbow_charges, 3)

    def test_fireball_core_hits_without_glow_hitbox(self):
        enemies = pg.sprite.Group()
        enemy = game.Enemy(500, 400, enemies)
        bullets = pg.sprite.Group()
        bullet = game.Bullet(enemy.rect.centerx, enemy.rect.bottom + 30, bullets)
        self.assertEqual(bullet.rect.size, (16, 20))
        self.assertGreater(bullet.image.get_width(), bullet.rect.width)
        bullet.update(0.02)
        self.assertTrue(pg.sprite.groupcollide(bullets, enemies, True, True))
        self.assertFalse(enemy.alive())
        self.assertFalse(bullet.alive())

    def test_rainbow_survives_fullscreen_launch_and_exits(self):
        bullets = pg.sprite.Group()
        particle = game.RainbowBeamParticle(1500, 900, -1.57079632679, None, bullets)
        particle.update(game.STEP)
        self.assertTrue(particle.alive())
        self.assertGreater(particle.pos.y, 770)
        for _ in range(100):
            particle.update(game.STEP)
        self.assertFalse(particle.alive())

    def test_rainbow_color_cycles_identically_in_every_direction(self):
        histories = []
        for angle in (0, math.pi / 4, math.pi / 2, 3 * math.pi / 4,
                      math.pi, -3 * math.pi / 4, -math.pi / 2, -math.pi / 4):
            particle = game.RainbowBeamParticle(960, 540, angle, None, hue=60)
            hues = []
            for _ in range(60):
                particle.update(game.STEP)
                hues.append(round(particle.hue, 6))
            histories.append(hues)
        for hues in histories:
            self.assertEqual(hues, histories[0])
            self.assertGreater(len(set(int(hue // 60) for hue in hues)), 5)

    def test_rainbow_source_color_changes_between_bursts(self):
        player = game.Player()
        player.rainbow_charges = 2
        bullets = pg.sprite.Group()
        player.start_rainbow()
        with patch.object(game.RainbowBeam, 'fire') as fire:
            player.update_rainbow(0.1, (100, 100), None, bullets)
            first_hue = fire.call_args.kwargs['hue']
            player.update_rainbow(0.9, (100, 100), None, bullets)
            player.update_rainbow(0.15, (100, 100), None, bullets)
            player.start_rainbow()
            player.update_rainbow(0.1, (100, 100), None, bullets)
            self.assertNotEqual(first_hue, fire.call_args.kwargs['hue'])

    def test_enemy_shoots_slow_purple_fireballs_that_hit_player(self):
        player = game.Player()
        enemy = game.Enemy(player.rect.left, 64)
        bullets = pg.sprite.Group()
        enemy.shot_remaining = 0.01
        enemy.update_weapon(0.02, bullets)
        self.assertEqual(len(bullets), 1)
        bullet = next(iter(bullets))
        self.assertIsInstance(bullet, game.EnemyBullet)
        start = bullet.pos.copy()
        bullet.update(0.5)
        self.assertEqual(bullet.pos.x, start.x)
        self.assertAlmostEqual(bullet.pos.y - start.y, game.ENEMY_BULLET_SPEED * 0.5)
        self.assertLess(game.ENEMY_BULLET_SPEED, game.BULLET_SPEED)
        self.assertEqual(bullet.image.get_size(), (21, 32))
        self.assertEqual(bullet.rect.size, (5, 7))
        core = bullet.image.get_at(game.ENEMY_BULLET_ANCHOR)
        self.assertGreater(core.b, core.g)
        self.assertGreater(core.r, core.g)
        enemy.update_weapon(0.02, bullets)
        self.assertEqual(len(bullets), 1)
        for _ in range(400):
            bullets.update(game.STEP)
            if pg.sprite.spritecollide(player, bullets, True):
                break
        else:
            self.fail('Vihollisen tulipallo ei osunut pelaajaan')
        self.assertFalse(bullet.alive())

    def test_enemy_bullet_exits_bottom_of_screen(self):
        bullets = pg.sprite.Group()
        bullet = game.EnemyBullet(800, game.HEIGHT + 67, bullets)
        bullet.update(game.STEP)
        self.assertFalse(bullet.alive())

    def test_enemy_skips_all_rows_with_oncoming_enemies(self):
        enemies = pg.sprite.Group()
        spacing = game.ENEMY_SIZE[1] + game.ENEMY_GAP
        dropping = game.Enemy(game.WIDTH - game.ENEMY_SIZE[0] - 5, 64,
                              enemies, enemy_group=enemies)
        game.Enemy(400, 64 + spacing, enemies, enemy_group=enemies)
        game.Enemy(600, 64 + 2 * spacing, enemies, enemy_group=enemies)
        dropping.update(dropping.jump_duration + dropping.jump_cooldown)
        self.assertTrue(dropping.is_dropping)
        self.assertEqual(dropping.drop_y, 64 + 3 * spacing)
        dropping.update(dropping.jump_duration)
        self.assertEqual(dropping.rect.y, 64 + 3 * spacing)
        dropping.update(dropping.jump_cooldown + 0.001)
        self.assertFalse(dropping.is_dropping)
        self.assertEqual(dropping.base_y, 64 + 3 * spacing)
        self.assertEqual(dropping.direction, -1)

    def test_enemy_can_join_a_row_moving_in_same_direction(self):
        enemies = pg.sprite.Group()
        spacing = game.ENEMY_SIZE[1] + game.ENEMY_GAP
        dropping = game.Enemy(game.WIDTH - game.ENEMY_SIZE[0] - 5, 64,
                              enemies, enemy_group=enemies)
        resident = game.Enemy(400, 64 + spacing, enemies, enemy_group=enemies)
        resident.direction = -1
        dropping.update(dropping.jump_duration + dropping.jump_cooldown)
        self.assertEqual(dropping.drop_y, 64 + spacing)

    def test_enemy_avoids_opposing_reserved_landing_row(self):
        enemies = pg.sprite.Group()
        spacing = game.ENEMY_SIZE[1] + game.ENEMY_GAP
        reserving = game.Enemy(0, 64, enemies, enemy_group=enemies)
        reserving.direction = -1
        reserving.update(reserving.jump_duration + reserving.jump_cooldown)
        self.assertEqual(reserving.drop_y, 64 + spacing)
        dropping = game.Enemy(game.WIDTH - game.ENEMY_SIZE[0] - 5, 64,
                              enemies, enemy_group=enemies)
        dropping.update(dropping.jump_duration + dropping.jump_cooldown)
        self.assertEqual(dropping.drop_y, 64 + 2 * spacing)

    def test_destroyed_enemy_no_longer_blocks_a_row(self):
        enemies = pg.sprite.Group()
        spacing = game.ENEMY_SIZE[1] + game.ENEMY_GAP
        dropping = game.Enemy(game.WIDTH - game.ENEMY_SIZE[0] - 5, 64,
                              enemies, enemy_group=enemies)
        blocker = game.Enemy(400, 64 + spacing, enemies, enemy_group=enemies)
        blocker.kill()
        dropping.update(dropping.jump_duration + dropping.jump_cooldown)
        self.assertEqual(dropping.drop_y, 64 + spacing)

    def test_powerup_drops_are_rare_and_have_a_cooldown(self):
        drops = game.PowerUpDrops()
        sprites, powerups = pg.sprite.Group(), pg.sprite.Group()
        with patch.object(game.random, 'random', return_value=0.026):
            self.assertFalse(drops.try_drop((800, 400), sprites, powerups))
        with patch.object(game.random, 'random', return_value=0.024):
            self.assertTrue(drops.try_drop((800, 400), sprites, powerups))
            self.assertFalse(drops.try_drop((900, 400), sprites, powerups))
            drops.update(11.9)
            self.assertFalse(drops.try_drop((900, 400), sprites, powerups))
            drops.update(0.2)
            self.assertTrue(drops.try_drop((900, 400), sprites, powerups))
        self.assertEqual(len(powerups), 2)

    def test_drop_waits_for_occupied_path_then_resumes(self):
        enemies = pg.sprite.Group()
        spacing = game.ENEMY_SIZE[1] + game.ENEMY_GAP
        x = game.WIDTH - game.ENEMY_SIZE[0] - 5
        dropping = game.Enemy(x, 64, enemies, enemy_group=enemies)
        blocker = game.Enemy(x, 64 + spacing, enemies, enemy_group=enemies)
        blocker.direction = -1
        dropping.update(dropping.jump_duration + dropping.jump_cooldown)
        self.assertFalse(dropping.is_dropping)
        self.assertEqual(dropping.rect.topleft, (x, 64))
        for _ in range(game.FPS * 12):
            enemies.update(game.STEP)
            self.assertFalse(dropping.rect.colliderect(blocker.rect))
        self.assertEqual(dropping.base_y, 64 + spacing)
        self.assertEqual(dropping.direction, -1)

    def test_multiple_rows_never_overlap_during_movement(self):
        sprites, enemies = pg.sprite.Group(), pg.sprite.Group()
        game.spawn_enemies(sprites, enemies, horde=32)
        items = list(enemies)
        for _ in range(game.FPS * 45):
            enemies.update(game.STEP)
            for index, enemy in enumerate(items):
                self.assertFalse(any(enemy.rect.colliderect(other.rect)
                                     for other in items[index + 1:]))
        self.assertTrue(any(enemy.base_y > 64 + (game.ENEMY_SIZE[1] + game.ENEMY_GAP)
                            for enemy in enemies))

    def test_ship_pixels_return_to_original_ship_and_protect_respawn(self):
        player = game.Player()
        original = player.rect.copy()
        self.assertEqual(player.lives, 3)
        self.assertEqual(player.rect.size, (36, 48))
        self.assertTrue(player.hit())
        self.assertEqual(player.lives, 2)
        self.assertFalse(player.hit())
        self.assertTrue(player.fragments)
        origin, velocity, distance, color, size, max_distance = player.fragments[0]
        initial_velocity = velocity.copy()
        player.move(1, 1)
        self.assertEqual(player.rect, original)
        bullets = pg.sprite.Group()
        player.shoot(bullets)
        self.assertFalse(bullets)
        player.update(0.1)
        self.assertEqual(player.fragments[0][1], initial_velocity)
        self.assertAlmostEqual(player.fragments[0][2], initial_velocity.length() * 0.1)
        for _ in range(game.FPS * 3):
            player.update(game.STEP)
            if player.active:
                break
        self.assertTrue(player.active)
        self.assertIs(player.image, player.ship_surface)
        self.assertEqual(player.rect, original)
        self.assertFalse(player.hit())
        player.update(game.RESPAWN_PROTECTION)
        self.assertTrue(player.hit())
        player.update(3)
        player.update(game.RESPAWN_PROTECTION)
        self.assertTrue(player.hit())
        player.update(3)
        self.assertEqual(player.lives, 0)
        self.assertFalse(player.active)
        self.assertFalse(player.fragments)

    def test_life_powerup_probability_and_collection(self):
        drops = game.PowerUpDrops()
        sprites, powerups = pg.sprite.Group(), pg.sprite.Group()
        with patch.object(game.random, 'random', return_value=0.025):
            self.assertFalse(drops.try_drop_life((800, 400), sprites, powerups))
        with patch.object(game.random, 'random', return_value=0.024):
            self.assertTrue(drops.try_drop_life((800, 400), sprites, powerups))
            self.assertFalse(drops.try_drop_life((800, 400), sprites, powerups))
        player = game.Player()
        player.collect(next(iter(powerups)))
        self.assertEqual(player.lives, 4)
        self.assertEqual(player.rainbow_charges, 0)

    def test_default_horde_has_individual_jump_timing(self):
        sprites, enemies = pg.sprite.Group(), pg.sprite.Group()
        game.spawn_enemies(sprites, enemies)
        self.assertEqual(len(enemies), game.DEFAULT_HORDE_SIZE)
        self.assertGreater(len({enemy.phase for enemy in enemies}), 1)
        self.assertGreater(len({enemy.jump_cooldown for enemy in enemies}), 1)

    def test_enemy_health_flash_and_score_only_on_destruction(self):
        sprites, enemies, bullets, powerups = (pg.sprite.Group() for _ in range(4))
        enemy = game.Enemy(500, 100, sprites, enemies, level=2)
        progress, drops = game.LevelProgress(), game.PowerUpDrops()
        game.Bullet(*enemy.rect.center, bullets)
        game.resolve_enemy_hits(bullets, enemies, sprites, powerups, drops, progress)
        self.assertEqual(enemy.hitpoints, 1)
        self.assertTrue(enemy.alive())
        self.assertIs(enemy.image, enemy.flash_image)
        self.assertEqual(progress.score, 0)
        enemy.update(game.ENEMY_HIT_FLASH)
        self.assertIs(enemy.image, enemy.normal_image)
        game.Bullet(*enemy.rect.center, bullets)
        game.Bullet(*enemy.rect.center, bullets)
        with patch.object(drops, 'try_drop') as rainbow, patch.object(drops, 'try_drop_life') as life:
            game.resolve_enemy_hits(bullets, enemies, sprites, powerups, drops, progress)
            rainbow.assert_called_once()
            life.assert_called_once()
        self.assertFalse(enemy.alive())
        self.assertEqual(progress.score, game.ENEMY_SCORE)
        self.assertEqual(len(bullets), 1)

    def test_level_transition_fades_and_spawns_stronger_faster_hordes(self):
        sprites, enemies, bullets, enemy_bullets = (pg.sprite.Group() for _ in range(4))
        player = game.Player(sprites)
        progress = game.LevelProgress()
        player.rainbow_remaining = 0.4
        game.Bullet(500, 500, bullets)
        game.EnemyBullet(500, 500, enemy_bullets)
        progress.update(game.STEP, sprites, enemies, bullets, enemy_bullets, player)
        self.assertEqual(progress.level, 2)
        self.assertEqual(progress.text_alpha, 0)
        self.assertFalse(bullets)
        self.assertFalse(enemy_bullets)
        self.assertEqual(player.rainbow_remaining, 0)
        progress.update(0.35, sprites, enemies, bullets, enemy_bullets, player)
        self.assertAlmostEqual(progress.text_alpha, 128, delta=1)
        self.assertFalse(enemies)
        progress.update(0.35, sprites, enemies, bullets, enemy_bullets, player)
        self.assertEqual(progress.text_alpha, 255)
        progress.update(2, sprites, enemies, bullets, enemy_bullets, player)
        self.assertFalse(progress.transitioning)
        self.assertEqual(len(enemies), game.DEFAULT_HORDE_SIZE)
        self.assertTrue(all(enemy.hitpoints == 2 for enemy in enemies))
        self.assertTrue(all(abs(enemy.speed_multiplier - 1.1) < 1e-9 for enemy in enemies))
        for enemy in list(enemies):
            enemy.kill()
        progress.update(game.STEP, sprites, enemies, bullets, enemy_bullets, player)
        progress.update(game.LEVEL_TRANSITION_DURATION, sprites, enemies, bullets, enemy_bullets, player)
        self.assertEqual(progress.level, 3)
        self.assertTrue(all(enemy.hitpoints == 3 for enemy in enemies))
        self.assertTrue(all(abs(enemy.speed_multiplier - 1.21) < 1e-9 for enemy in enemies))

    def test_higher_level_moves_ten_percent_faster(self):
        normal = game.Enemy(500, 100)
        faster = game.Enemy(500, 100, level=2)
        normal.update(0.2)
        faster.update(0.2 / 1.1)
        self.assertEqual(normal.rect, faster.rect)

    def test_level_title_dissolves_horizontally_and_disappears(self):
        original = game.level_title(2)
        middle = game.dissolving_title(2, 15)
        end = game.dissolving_title(2, 30)
        self.assertGreater(middle.get_width(), original.get_width())
        self.assertEqual(middle.get_height(), original.get_height())
        self.assertLess(middle.get_alpha(), 255)
        self.assertEqual(pg.mask.from_surface(end).count(), 0)
        self.assertIs(game.dissolving_title(2, 15), middle)
        self.assertEqual(original.get_alpha(), 255)

    def test_explosion_holds_all_large_pixels_before_return(self):
        player = game.Player()
        player.hit()
        self.assertTrue(all(4 <= fragment[4] <= 8 for fragment in player.fragments))
        self.assertGreater(max(f[5] for f in player.fragments) - min(f[5] for f in player.fragments), game.HEIGHT / 4)
        player.update(player.explosion_outward_duration)
        self.assertTrue(all(abs(fragment[2] - fragment[5]) < 1e-6
                            for fragment in player.fragments))
        player.update(0.49)
        self.assertTrue(all(abs(fragment[2] - fragment[5]) < 1e-6
                            for fragment in player.fragments))
        player.update(0.02)
        self.assertTrue(all(fragment[2] < fragment[5] for fragment in player.fragments))
        player.update(player.explosion_outward_duration)
        self.assertTrue(player.active)

    def test_space_autofire_rate_and_respawn_block(self):
        for fps in (30, 60, 156):
            player, bullets = game.Player(), pg.sprite.Group()
            for _ in range(fps):
                player.update_space_fire(True, 1 / fps, bullets)
            self.assertEqual(len(bullets), 7)
            player.update_space_fire(False, 0.1, bullets)
            player.update_space_fire(True, game.STEP, bullets)
            self.assertEqual(len(bullets), 8)
            player.hit()
            player.update_space_fire(True, 1, bullets)
            self.assertEqual(len(bullets), 8)

    def test_lightning_instantly_destroys_one_high_hp_enemy_and_scores_once(self):
        sprites, enemies, powerups = (pg.sprite.Group() for _ in range(3))
        first = game.Enemy(500, 100, sprites, enemies, level=20)
        second = game.Enemy(550, 100, sprites, enemies, level=20)
        player = game.Player()
        player.collect(game.PowerUp(0, 0, kind="lightning"))
        self.assertEqual(player.lightning_charges, 3)
        self.assertEqual(player.rainbow_charges, 0)
        progress, drops = game.LevelProgress(), game.PowerUpDrops()
        with patch.object(game.random, 'choice', side_effect=lambda options: options[0]), \
                patch.object(game.random, 'random', return_value=1):
            self.assertTrue(player.fire_lightning(enemies, sprites, powerups, drops, progress))
            self.assertEqual(first.hitpoints, 0)
            self.assertFalse(first.alive())
            self.assertEqual(second.hitpoints, 20)
            self.assertEqual(progress.score, 100)
            bolt = next(sprite for sprite in sprites if isinstance(sprite, game.Lightning))
            self.assertEqual(bolt.paths[0][0], pg.Vector2(player.rect.midtop))
            self.assertEqual(bolt.paths[0][-1], pg.Vector2(first.rect.center))
            self.assertGreater(len(bolt.paths), 5)
            bolt.update(game.LIGHTNING_DURATION)
            self.assertFalse(bolt.alive())
            self.assertEqual(progress.score, 100)
            self.assertEqual(player.lightning_charges, 2)
            self.assertTrue(player.fire_lightning(enemies, sprites, powerups, drops, progress))
            self.assertFalse(second.alive())
            self.assertEqual(progress.score, 200)
            self.assertEqual(player.lightning_charges, 1)

    def test_lightning_keeps_charge_without_target_and_during_transition_or_death(self):
        player = game.Player()
        player.lightning_charges = 1
        sprites, enemies, powerups = (pg.sprite.Group() for _ in range(3))
        drops, progress = game.PowerUpDrops(), game.LevelProgress()
        self.assertFalse(player.fire_lightning(enemies, sprites, powerups, drops, progress))
        enemy = game.Enemy(500, 100, enemies)
        progress.transition_remaining = 1
        self.assertFalse(player.fire_lightning(enemies, sprites, powerups, drops, progress))
        progress.transition_remaining = 0
        player.hit()
        self.assertFalse(player.fire_lightning(enemies, sprites, powerups, drops, progress))
        self.assertEqual(player.lightning_charges, 1)
        self.assertEqual(enemy.hitpoints, 1)

    def test_lightning_powerup_drop_has_independent_chance_and_cooldown(self):
        drops = game.PowerUpDrops()
        sprites, powerups = pg.sprite.Group(), pg.sprite.Group()
        drops.cooldown = drops.life_cooldown = 12
        with patch.object(game.random, 'random', return_value=0.025):
            self.assertFalse(drops.try_drop_lightning((500, 100), sprites, powerups))
        with patch.object(game.random, 'random', return_value=0.024):
            self.assertTrue(drops.try_drop_lightning((500, 100), sprites, powerups))
            self.assertFalse(drops.try_drop_lightning((500, 100), sprites, powerups))
            drops.update(12)
            self.assertTrue(drops.try_drop_lightning((500, 100), sprites, powerups))
        self.assertTrue(all(powerup.kind == "lightning" for powerup in powerups))

    def test_keyboard_space_and_f1_dispatch_and_ignore_repeat(self):
        events = [pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_F1),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_F1, repeat=True),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE)]
        previous_size = game.WIDTH, game.HEIGHT
        try:
            with patch.object(pg.event, 'get', return_value=events), \
                    patch.object(game.Player, 'shoot') as shoot, \
                    patch.object(game.Player, 'fire_lightning') as lightning:
                self.assertEqual(game.main(), 0)
                shoot.assert_called_once()
                lightning.assert_called_once()
        finally:
            game.WIDTH, game.HEIGHT = previous_size
            pg.init()
            pg.display.set_mode(previous_size)

    def test_highscores_persist_top_ten_and_handle_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scores.json'
            board = game.HighScores(path)
            self.assertEqual(board.entries, [])
            for score in range(12):
                board.add(score * 100, score + 1, "Test")
            self.assertEqual(len(board.entries), 10)
            self.assertEqual(board.entries[0], {'score': 1100, 'level': 12, 'name': 'Test'})
            self.assertEqual(board.entries[-1]['score'], 200)
            self.assertEqual(game.HighScores(path).entries, board.entries)
            self.assertFalse(path.with_suffix('.json.tmp').exists())
            path.write_text(json.dumps([{'score': -1, 'level': 1},
                                        {'score': 'bad', 'level': 2},
                                        {'score': 500, 'level': 2}]))
            self.assertEqual(game.HighScores(path).entries, [{'score': 500, 'level': 2, 'name': 'John Doe'}])
            path.write_text('broken json')
            self.assertEqual(game.HighScores(path).entries, [])

    def test_game_over_saves_once_after_final_explosion_and_new_game_resets(self):
        with tempfile.TemporaryDirectory() as folder:
            board = game.HighScores(Path(folder) / 'scores.json')
            session = game.GameSession()
            session.progress.score = 1234
            session.progress.level = 4
            session.player.lives = 1
            session.player.hit()
            session.finish_if_dead(board)
            self.assertFalse(session.game_over)
            self.assertEqual(board.entries, [])
            session.player.update(3)
            session.finish_if_dead(board, space_held=True)
            self.assertTrue(session.game_over)
            self.assertFalse(session.restart_ready)
            session.finish_if_dead(board)
            self.assertTrue(session.entering_name)
            self.assertEqual(board.entries, [])
            session.player_name = 'Ada'
            self.assertTrue(session.submit_name(board))
            self.assertFalse(session.submit_name(board))
            self.assertEqual(board.entries, [{'score': 1234, 'level': 4, 'name': 'Ada'}])
            new = game.GameSession()
            self.assertEqual(new.player.lives, 3)
            self.assertEqual(new.progress.score, 0)
            self.assertEqual(new.progress.level, 1)
            self.assertEqual(len(new.enemy_group), game.DEFAULT_HORDE_SIZE)
            self.assertEqual(new.player.lightning_charges, 0)
            self.assertEqual(new.player.rainbow_charges, 0)
            self.assertFalse(new.game_over)
            self.assertFalse(new.bullet_group)
            self.assertFalse(new.enemy_bullets)

    def test_game_over_screen_space_restarts_without_exiting_or_firing(self):
        previous_size = game.WIDTH, game.HEIGHT
        sessions = []
        factory = game.GameSession

        def new_session():
            session = factory()
            if not sessions:
                session.player.lives = 0
                session.progress.score = 1234
            sessions.append(session)
            return session

        events = [[], [pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE)], [],
                  [pg.event.Event(pg.TEXTINPUT, text='Ada'),
                   pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN),
                   pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE)],
                  [pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE)]]
        fake_clock = unittest.mock.Mock()
        fake_clock.tick.return_value = 16
        try:
            with tempfile.TemporaryDirectory() as folder:
                board = game.HighScores(Path(folder) / 'scores.json')
                with patch.object(game, 'HighScores', return_value=board), \
                        patch.object(game, 'GameSession', side_effect=new_session), \
                        patch.object(pg.time, 'Clock', return_value=fake_clock), \
                        patch.object(pg.event, 'get', side_effect=events), \
                        patch.object(game.Player, 'shoot') as shoot, \
                        patch.object(game, 'draw_highscores', wraps=game.draw_highscores) as draw:
                    self.assertEqual(game.main(), 0)
                    draw.assert_called_once()
                    shoot.assert_not_called()
                self.assertEqual(len(sessions), 2)
                self.assertTrue(sessions[0].game_over)
                self.assertFalse(sessions[1].game_over)
                self.assertEqual(sessions[1].progress.score, 0)
                self.assertEqual(board.entries, [{'score': 1234, 'level': 1, 'name': 'Ada'}])
        finally:
            game.WIDTH, game.HEIGHT = previous_size
            pg.init()
            pg.display.set_mode(previous_size)

    def test_player_shots_emit_muzzle_flash_without_extra_projectiles(self):
        effects, bullets = pg.sprite.Group(), pg.sprite.Group()
        player = game.Player(effects=effects)
        player.shoot(bullets)
        self.assertEqual(len(bullets), 1)
        self.assertEqual(len(effects), 1)
        flash = next(iter(effects))
        self.assertIsInstance(flash, game.MuzzleFlash)
        self.assertEqual(flash.rect.topleft, (player.rect.centerx - 32, player.rect.top - 56))
        first = flash.image
        effects.update(0.1)
        self.assertIsNot(flash.image, first)
        effects.update(game.MUZZLE_DURATION)
        self.assertFalse(effects)
        self.assertEqual(len(bullets), 1)
        player.hit()
        player.shoot(bullets)
        self.assertFalse(effects)

    def test_enemy_shots_emit_purple_muzzle_flash_at_cannon(self):
        effects, bullets = pg.sprite.Group(), pg.sprite.Group()
        enemy = game.Enemy(500, 100, effects=effects)
        enemy.shot_remaining = 0
        enemy.update_weapon(game.STEP, bullets)
        self.assertEqual(len(bullets), 1)
        self.assertEqual(len(effects), 1)
        flash = next(iter(effects))
        self.assertIs(flash.frames, game.muzzle_frames(enemy=True))
        self.assertEqual(flash.rect.topleft, (enemy.rect.centerx - 32, enemy.rect.bottom - 56))
        enemy.update_weapon(game.STEP, bullets)
        self.assertEqual(len(effects), 1)
        self.assertEqual(next(iter(bullets)).rect.size, (5, 7))

    def test_muzzle_frames_cool_to_rising_smoke_and_are_cached(self):
        for enemy in (False, True):
            frames = game.muzzle_frames(enemy)
            self.assertIs(frames, game.muzzle_frames(enemy))
            self.assertEqual(len(frames), 30)
            first, last = frames[0], frames[-2]
            self.assertTrue(any(first.get_at((x, y)).a and first.get_at((x, y)).r > 200
                                for x in range(64) for y in range(112)))
            smoke = [(x, y) for x in range(64) for y in range(112)
                     if last.get_at((x, y)).a > 0]
            self.assertTrue(smoke)
            self.assertLess(sum(y for x, y in smoke) / len(smoke), 54)
            self.assertTrue(all(last.get_at((x, y))[:3] == (165, 180, 195)
                                for x, y in smoke))

    def test_start_screen_prompt_fades_in_and_out(self):
        start = game.StartScreen((1920, 1080))
        self.assertEqual(start.prompt_alpha, 0)
        start.update(0.7)
        self.assertAlmostEqual(start.prompt_alpha, 128, delta=1)
        start.update(0.7)
        self.assertEqual(start.prompt_alpha, 255)
        start.update(1.4)
        self.assertEqual(start.prompt_alpha, 0)
        self.assertLessEqual(start.logo.get_width(), 1920)
        self.assertLessEqual(start.logo.get_height(), 1080)

    def test_start_screen_waits_for_space_before_creating_game(self):
        events = [[], [pg.event.Event(pg.MOUSEBUTTONDOWN, button=1)],
                  [pg.event.Event(pg.KEYDOWN, key=pg.K_F1)],
                  [pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE)]]
        previous_size = game.WIDTH, game.HEIGHT
        try:
            with patch.object(pg.event, 'get', side_effect=events), \
                    patch.object(game, 'GameSession') as session, \
                    patch.object(game.StartScreen, 'draw') as draw:
                self.assertEqual(game.main(), 0)
                session.assert_not_called()
                self.assertEqual(draw.call_count, 3)
        finally:
            game.WIDTH, game.HEIGHT = previous_size
            pg.init()
            pg.display.set_mode(previous_size)

    def test_highscore_empty_names_randomize_and_named_scores_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scores.json'
            board = game.HighScores(path)
            with patch.object(game.random, 'choice', side_effect=['John Doe', 'Jane Doe']) as choice:
                board.add(100, 1, '')
                board.add(200, 2, '   ')
                self.assertEqual(choice.call_count, 2)
            board.add(300, 3, '  Väinö Virtanen  ')
            self.assertEqual([entry['name'] for entry in board.entries],
                             ['Väinö Virtanen', 'Jane Doe', 'John Doe'])
            self.assertEqual(game.HighScores(path).entries, board.entries)

    def test_name_input_supports_spaces_unicode_backspace_and_enter(self):
        with tempfile.TemporaryDirectory() as folder:
            board = game.HighScores(Path(folder) / 'scores.json')
            session = game.GameSession()
            session.player.lives = 0
            session.finish_if_dead(board)
            session.handle_name_event(pg.event.Event(pg.TEXTINPUT, text='Väinö Virtanen!'), board)
            session.handle_name_event(pg.event.Event(pg.KEYDOWN, key=pg.K_BACKSPACE), board)
            self.assertEqual(session.player_name, 'Väinö Virtanen')
            session.handle_name_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE), board)
            self.assertTrue(session.entering_name)
            self.assertEqual(board.entries, [])
            self.assertTrue(session.handle_name_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN), board))
            self.assertEqual(board.entries[0]['name'], 'Väinö Virtanen')
            self.assertFalse(session.entering_name)
            self.assertFalse(session.submit_name(board))
            self.assertEqual(len(board.entries), 1)
            session.entering_name = True
            session.player_name = ''
            session.handle_name_event(pg.event.Event(pg.TEXTINPUT, text='x' * 100), board)
            self.assertEqual(len(session.player_name), game.MAX_PLAYER_NAME)

    def test_cannon_upgrades_cap_damage_and_color_at_four(self):
        player = game.Player()
        bullets = pg.sprite.Group()
        player.shoot(bullets)
        original = next(iter(bullets))
        self.assertEqual(original.damage, 1)
        red = game.cannon_fire_frames(2)[0].get_at((32, 28))
        blue = game.cannon_fire_frames(3)[0].get_at((32, 28))
        white = game.cannon_fire_frames(4)[0].get_at((32, 28))
        self.assertGreater(red.r, red.g)
        self.assertGreater(red.r, red.b)
        self.assertGreater(blue.b, blue.r)
        self.assertGreater(blue.b, blue.g)
        self.assertEqual(white.r, white.g)
        self.assertEqual(white.g, white.b)
        for power in range(2, 12):
            player.collect(game.PowerUp(0, 0, kind='cannon'))
            self.assertEqual(player.cannon_power, min(power, game.MAX_CANNON_POWER))
            player.shoot(bullets)
            shot = bullets.sprites()[-1]
            self.assertEqual(shot.damage, min(power, game.MAX_CANNON_POWER))
            if power >= 4:
                self.assertIs(shot.frames, game.cannon_fire_frames(4))
        self.assertEqual(original.damage, 1)
        self.assertIs(original.frames, game.fire_frames())
        self.assertEqual(player.rainbow_charges, 0)
        self.assertEqual(player.lightning_charges, 0)
        self.assertEqual(game.EnemyBullet(0, 0).damage, 1)

    def test_upgraded_shot_damages_hp_and_overkill_awards_score_only_once(self):
        sprites, enemies, bullets, powerups = (pg.sprite.Group() for _ in range(4))
        enemy = game.Enemy(500, 100, sprites, enemies, level=5)
        progress, drops = game.LevelProgress(), game.PowerUpDrops()
        game.Bullet(*enemy.rect.center, bullets, damage=3)
        game.resolve_enemy_hits(bullets, enemies, sprites, powerups, drops, progress)
        self.assertEqual(enemy.hitpoints, 2)
        self.assertIs(enemy.image, enemy.flash_image)
        self.assertEqual(progress.score, 0)
        game.Bullet(*enemy.rect.center, bullets, damage=10)
        game.Bullet(*enemy.rect.center, bullets, damage=10)
        with patch.object(drops, 'try_drop_cannon') as cannon:
            game.resolve_enemy_hits(bullets, enemies, sprites, powerups, drops, progress)
            cannon.assert_called_once()
        self.assertEqual(enemy.hitpoints, 0)
        self.assertFalse(enemy.alive())
        self.assertEqual(progress.score, 100)
        self.assertEqual(len(bullets), 1)

    def test_cannon_power_survives_respawn_and_level_transition_but_resets_on_restart(self):
        session = game.GameSession()
        session.player.collect(game.PowerUp(0, 0, kind='cannon'))
        session.player.hit()
        session.player.update(3)
        self.assertEqual(session.player.cannon_power, 2)
        for enemy in list(session.enemy_group):
            enemy.kill()
        session.progress.update(game.STEP, session.all_sprites, session.enemy_group,
                                session.bullet_group, session.enemy_bullets, session.player)
        session.progress.update(game.LEVEL_TRANSITION_DURATION, session.all_sprites,
                                session.enemy_group, session.bullet_group, session.enemy_bullets, session.player)
        self.assertEqual(session.player.cannon_power, 2)
        self.assertEqual(game.GameSession().player.cannon_power, 1)

    def test_cannon_powerup_has_independent_drop_probability_and_cooldown(self):
        drops = game.PowerUpDrops()
        sprites, powerups = pg.sprite.Group(), pg.sprite.Group()
        drops.cooldown = drops.life_cooldown = drops.lightning_cooldown = 12
        with patch.object(game.random, 'random', return_value=0.025):
            self.assertFalse(drops.try_drop_cannon((500, 100), sprites, powerups))
        with patch.object(game.random, 'random', return_value=0.024):
            self.assertTrue(drops.try_drop_cannon((500, 100), sprites, powerups))
            self.assertFalse(drops.try_drop_cannon((500, 100), sprites, powerups))
            drops.update(12)
            self.assertTrue(drops.try_drop_cannon((500, 100), sprites, powerups))
        self.assertTrue(all(powerup.kind == 'cannon' for powerup in powerups))

    def test_cannon_drops_stop_at_max_power_for_real_session(self):
        session = game.GameSession()
        session.player.cannon_power = game.MAX_CANNON_POWER
        with patch.object(game.random, 'random', return_value=0):
            self.assertFalse(session.drops.try_drop_cannon((500, 100), session.all_sprites, session.powerups))
            self.assertTrue(session.drops.try_drop((500, 100), session.all_sprites, session.powerups))
        self.assertTrue(all(drop.kind != 'cannon' for drop in session.powerups))
        self.assertEqual(game.GameSession().player.cannon_power, 1)

    def test_simultaneous_powerups_are_spaced_and_stay_inside_screen(self):
        for center in ((500, 100), (0, 0), (game.WIDTH, game.HEIGHT)):
            drops = game.PowerUpDrops()
            sprites, powerups = pg.sprite.Group(), pg.sprite.Group()
            with patch.object(game.random, 'random', return_value=0):
                self.assertTrue(drops.try_drop(center, sprites, powerups))
                self.assertTrue(drops.try_drop_life(center, sprites, powerups))
                self.assertTrue(drops.try_drop_lightning(center, sprites, powerups))
                self.assertTrue(drops.try_drop_cannon(center, sprites, powerups))
            self.assertEqual(len(powerups), 4)
            for drop in powerups:
                self.assertTrue(pg.Rect(0, 0, game.WIDTH, game.HEIGHT).contains(drop.rect))
                self.assertFalse(any(drop.rect.inflate(game.POWERUP_GAP * 2, game.POWERUP_GAP * 2)
                                     .colliderect(other.rect) for other in powerups if other is not drop))
            powerups.update(0.5)
            items = list(powerups)
            for index, drop in enumerate(items):
                self.assertFalse(any(drop.rect.colliderect(other.rect) for other in items[index + 1:]))

    def test_levels_select_pngs_then_birds_then_recovered_rect_enemy(self):
        for level in range(1, 5):
            first = game.Enemy(300, 100, level=level)
            second = game.Enemy(500, 100, level=level)
            self.assertIs(first.normal_image, game.ship_image(f'vihu{level}.png', game.ENEMY_SIZE))
            self.assertIs(second.normal_image, first.normal_image)
            self.assertFalse(first.is_bird)
        for level in range(game.BIRD_FIRST_LEVEL, game.RECT_ENEMY_FIRST_LEVEL):
            bird = game.Enemy(300, 100, level=level)
            self.assertTrue(bird.is_bird)
            self.assertIs(bird.frames, game.bird_frames(bird.bird_color))
            self.assertEqual(bird.hitpoints, level)
        for level in (game.RECT_ENEMY_FIRST_LEVEL, 12):
            enemy = game.Enemy(300, 100, level=level)
            self.assertFalse(enemy.is_bird)
            self.assertIs(enemy.normal_image, game.rect_enemy_image())
            enemy.update(enemy.jump_duration / 2 / enemy.speed_multiplier)
            self.assertLess(enemy.rect.y, 100)

    def test_birds_flap_and_move_at_constant_horizontal_speed_without_jumping(self):
        bird = game.Enemy(300, 100, level=5)
        bird.animation_age = 0.0
        first = bird.image
        for _ in range(6):
            before = bird.base_x
            bird.update(0.18)
            self.assertAlmostEqual(bird.base_x - before, game.BIRD_FLIGHT_SPEED * bird.speed_multiplier * 0.18)
            self.assertEqual(bird.base_y, 100)
            self.assertFalse(bird.is_dropping)
        self.assertGreater(len({pg.image.tobytes(frame, 'RGBA') for frame in bird.frames}), 1)
        bird.animation_age = 0.0
        bird.update(0.18)
        self.assertIsNot(bird.image, first)
        bird.take_hit()
        bird.update(0.05)
        self.assertIs(bird.image, bird.flash_image)
        bird.update(game.ENEMY_HIT_FLASH)
        self.assertIs(bird.image, bird.normal_image)

    def test_bird_wave_flies_without_disappearing_or_overlapping(self):
        sprites, enemies = pg.sprite.Group(), pg.sprite.Group()
        game.spawn_enemies(sprites, enemies, level=5)
        items = list(enemies)
        for _ in range(600):
            enemies.update(0.1)
            for index, bird in enumerate(items):
                self.assertFalse(any(bird.rect.colliderect(other.rect) for other in items[index + 1:]))
        self.assertEqual(len(enemies), game.DEFAULT_HORDE_SIZE)
        self.assertTrue(all(0 <= bird.rect.left and bird.rect.right <= game.WIDTH for bird in enemies))
        self.assertTrue(any(bird.base_y > 64 + game.ENEMY_SIZE[1] + game.ENEMY_GAP for bird in enemies))

    def test_recovered_rect_enemy_retains_original_eyes_and_bottom_cutouts(self):
        image = game.rect_enemy_image()
        self.assertEqual(image.get_size(), game.ENEMY_SIZE)
        original = pg.transform.scale(image, (24, 32))
        self.assertEqual(original.get_at((1, 1)), pg.Color(255, 255, 255))
        for position in ((6, 6), (15, 6), (1, 23), (19, 23), (9, 29)):
            self.assertEqual(original.get_at(position).a, 0)

    def test_f5_skip_preserves_player_and_builds_next_wave_immediately(self):
        session = game.GameSession()
        session.player.lives = 2
        session.player.cannon_power = 4
        session.player.rainbow_charges = 2
        session.player.lightning_charges = 1
        session.player.rainbow_remaining = 0.3
        session.progress.score = 1234
        session.progress.level = 4
        session.progress.transition_remaining = 1
        old_enemies = list(session.enemy_group)
        bullet = game.Bullet(100, 200, session.bullet_group)
        enemy_bullet = game.EnemyBullet(100, 200, session.enemy_bullets)
        drop = game.PowerUp(100, 200, session.all_sprites, session.powerups)
        self.assertTrue(session.skip_level())
        self.assertEqual(session.progress.level, 5)
        self.assertFalse(session.progress.transitioning)
        self.assertEqual(session.progress.score, 1234)
        self.assertEqual(session.player.lives, 2)
        self.assertEqual(session.player.cannon_power, 4)
        self.assertEqual(session.player.rainbow_charges, 2)
        self.assertEqual(session.player.lightning_charges, 1)
        self.assertEqual(session.player.rainbow_remaining, 0)
        self.assertEqual(len(session.enemy_group), game.DEFAULT_HORDE_SIZE)
        self.assertTrue(all(enemy.is_bird and enemy.hitpoints == 5 for enemy in session.enemy_group))
        self.assertFalse(any(enemy.alive() for enemy in old_enemies))
        self.assertFalse(bullet.alive())
        self.assertFalse(enemy_bullet.alive())
        self.assertFalse(drop.alive())
        session.game_over = True
        self.assertFalse(session.skip_level())
        self.assertEqual(session.progress.level, 5)

    def test_f5_keyboard_dispatch_ignores_key_repeat(self):
        previous_size = game.WIDTH, game.HEIGHT
        events = [pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_F5),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_F5, repeat=True),
                  pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE)]
        try:
            with patch.object(pg.event, 'get', return_value=events), \
                    patch.object(game.GameSession, 'skip_level') as skip:
                self.assertEqual(game.main(), 0)
                skip.assert_called_once()
        finally:
            game.WIDTH, game.HEIGHT = previous_size
            pg.init()
            pg.display.set_mode(previous_size)

    def test_enemy_types_repeat_every_six_levels_without_resetting_difficulty(self):
        for level in range(1, 19):
            enemy = game.Enemy(300, 100, level=level)
            kind = (level - 1) % 6 + 1
            self.assertEqual(enemy.hitpoints, level)
            self.assertAlmostEqual(enemy.speed_multiplier, 1.1 ** (level - 1))
            self.assertEqual(enemy.is_bird, kind == 5)
            if kind <= 4:
                self.assertIs(enemy.normal_image, game.ship_image(f'vihu{kind}.png', game.ENEMY_SIZE))
            elif kind == 6:
                self.assertIs(enemy.normal_image, game.rect_enemy_image())

    def test_birds_match_small_colored_pixel_wings(self):
        for color in game.BIRD_COLORS:
            frames = game.bird_frames(color)
            for frame in frames:
                visible = [frame.get_at((x, y)) for x in range(frame.get_width())
                           for y in range(frame.get_height()) if frame.get_at((x, y)).a]
                self.assertTrue(visible)
                self.assertTrue(all(pixel[:3] == color for pixel in visible))
                self.assertLessEqual(frame.get_bounding_rect().height, 12)

    def test_dense_rainbow_has_no_gaps_between_emission_batches(self):
        player = game.Player()
        player.rainbow_charges = 1
        player.start_rainbow()
        bullets = pg.sprite.Group()
        for _ in range(3):
            player.update_rainbow(game.STEP, (game.WIDTH, player.rect.top), None, bullets)
            bullets.update(game.STEP)
        self.assertEqual(len(bullets), 36)
        positions = sorted(bullet.pos.x for bullet in bullets)
        self.assertLess(max(right - left for left, right in zip(positions, positions[1:])), 4)


if __name__ == '__main__':
    unittest.main()
