import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import random
import unittest
import pygame as pg
import round43 as game


class TunnelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.display.set_mode((game.WIDTH, game.HEIGHT))

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def test_every_third_level_waits_for_title_and_then_starts_tunnel(self):
        for level in (3, 6, 9, 12):
            session = game.GameSession()
            for enemy in list(session.enemy_group):
                enemy.kill()
            progress = session.progress
            progress.level = level - 1
            args = (session.all_sprites, session.enemy_group, session.bullet_group,
                    session.enemy_bullets, session.player)
            progress.update(game.STEP, *args)
            self.assertEqual(progress.level, level)
            self.assertTrue(progress.transitioning)
            self.assertIsNone(progress.tunnel)
            progress.update(game.LEVEL_TRANSITION_DURATION - 0.01, *args)
            self.assertIsNone(progress.tunnel)
            progress.update(0.02, *args)
            self.assertIsNotNone(progress.tunnel)
            self.assertFalse(session.enemy_group)
            y = session.player.rect.y
            progress.tunnel.update(0.1, session.player)
            self.assertLess(session.player.rect.y, y)
            progress.update(game.STEP, *args)
            self.assertEqual(progress.level, level)

    def test_vertical_input_combines_with_auto_rise_and_clamps_bottom(self):
        tunnel = game.Tunnel(3)
        player = game.Player()
        tunnel.reset_player(player)
        start = tunnel.player_y
        tunnel.update(0.1, player, vertical=-1)
        self.assertAlmostEqual(tunnel.player_y, start - (game.PLAYER_SPEED + tunnel.speed) * 0.1)
        tunnel.update(1, player, vertical=1)
        self.assertEqual(player.rect.bottom, game.HEIGHT)
        tunnel.update(0.1, player)
        self.assertLess(player.rect.bottom, game.HEIGHT)
        self.assertEqual(player.pos_y, tunnel.player_y)

    def test_difficulty_and_random_layout(self):
        tunnels = [game.Tunnel(level, random.Random(43)) for level in (3, 6, 9, 12)]
        for easy, hard in zip(tunnels, tunnels[1:]):
            self.assertGreater(easy.width, hard.width)
            self.assertLess(len(easy.nodes), len(hard.nodes))
            self.assertLess(easy.speed, hard.speed)
        self.assertNotEqual(game.Tunnel(6, random.Random(1)).nodes,
                            game.Tunnel(6, random.Random(2)).nodes)

    def test_tunnels_do_not_skip_enemy_types(self):
        for level, enemy_type in zip((1, 2, 4, 5, 7, 8, 10, 11), (1, 2, 3, 4, 5, 6, 7, 1)):
            sprites, enemies = pg.sprite.Group(), pg.sprite.Group()
            game.spawn_enemies(sprites, enemies, horde=1, level=level)
            enemy = next(iter(enemies))
            self.assertEqual(enemy.enemy_type, enemy_type)
            self.assertEqual(enemy.hitpoints, level)

    def test_plasma_moves_without_changing_tunnel_geometry(self):
        tunnel = game.Tunnel(6, random.Random(43))
        nodes = list(tunnel.nodes)
        first = pg.image.tobytes(tunnel.image, 'RGB')
        screen = pg.Surface((game.WIDTH, game.HEIGHT))
        tunnel.draw(screen, 0.5)
        self.assertNotEqual(first, pg.image.tobytes(tunnel.image, 'RGB'))
        self.assertEqual(tunnel.nodes, nodes)
        y = (tunnel.top + tunnel.bottom) // 2
        self.assertEqual(tunnel.image.get_at((round(tunnel.center_at(y)), y))[:3], (0, 0, 0))
        self.assertFalse(tunnel.hits_wall(pg.Rect(round(tunnel.center_at(y)), y, 1, 1)))

    def test_no_straight_vertical_route_remains_in_generated_tunnels(self):
        for level in (3, 6, 9, 12, 30, 84):
            for seed in range(12):
                tunnel = game.Tunnel(level, random.Random(seed))
                centers = [x for _, x in tunnel.nodes]
                # Edes nollalevyinen alus ei mahdu samalla x:llä joka mutkasta.
                self.assertGreater(max(centers) - min(centers), tunnel.width)

    def test_later_tunnels_require_more_lateral_correction(self):
        for seed in range(6):
            required = []
            for level in (3, 6, 9, 12):
                tunnel = game.Tunnel(level, random.Random(seed))
                free_width = tunnel.width - game.ENEMY_SIZE[0]
                required.append(sum(max(0, abs(a[1] - b[1]) - free_width)
                                    for a, b in zip(tunnel.nodes, tunnel.nodes[1:])))
            self.assertEqual(required, sorted(required))

    def test_generated_tunnels_are_navigable_at_player_speed(self):
        for level in (3, 6, 9, 12, 60):
            for seed in range(4):
                with self.subTest(level=level, seed=seed):
                    tunnel = game.Tunnel(level, random.Random(seed))
                    player = game.Player()
                    tunnel.reset_player(player)
                    for _ in range(game.FPS * 25):
                        # Seuraa aluksen keskikohdan kohdalla olevaa keskilinjaa.
                        target = tunnel.center_at(player.rect.centery - tunnel.speed * game.STEP)
                        delta = target - (player.pos_x + player.rect.width / 2)
                        direction = max(-1, min(1, delta / (game.PLAYER_SPEED * game.STEP)))
                        player.move(direction, game.STEP)
                        player.update(game.STEP)
                        tunnel.update(game.STEP, player)
                        self.assertEqual(player.lives, game.STARTING_LIVES)
                        if tunnel.complete:
                            break
                    self.assertTrue(tunnel.complete)

    def test_wall_hit_costs_one_life_and_restarts_same_tunnel(self):
        tunnel = game.Tunnel(6, random.Random(43))
        player = game.Player()
        tunnel.reset_player(player)
        nodes = list(tunnel.nodes)
        tunnel.player_y = tunnel.bottom - 100
        player.pos_x = 10
        player.rect.x = 10
        tunnel.update(game.STEP, player)
        self.assertEqual(player.lives, game.STARTING_LIVES - 1)
        y = tunnel.player_y
        tunnel.update(1, player)
        self.assertEqual(tunnel.player_y, y)
        self.assertEqual(player.lives, game.STARTING_LIVES - 1)
        player.update(10)
        tunnel.update(game.STEP, player)
        self.assertFalse(tunnel.restarting)
        self.assertEqual(tunnel.nodes, nodes)
        self.assertGreater(player.rect.top, tunnel.bottom)
        self.assertGreater(player.invulnerable_remaining, 0)

    def test_collision_checks_bends_inside_ship_height(self):
        tunnel = game.Tunnel(3)
        tunnel.width = 100
        tunnel.bands = [pg.Rect(450, 400, 100, tunnel.bottom - 400),
                        pg.Rect(510, 380, 100, 20), pg.Rect(450, 72, 100, 308)]
        self.assertTrue(tunnel.hits_wall(pg.Rect(485, 358, 30, 44)))
        self.assertFalse(tunnel.hits_wall(pg.Rect(0, tunnel.bottom + 1, 30, 44)))

    def test_exit_advances_once_and_restores_combat_position(self):
        session = game.GameSession()
        for enemy in list(session.enemy_group):
            enemy.kill()
        progress = session.progress
        progress.level = 3
        progress.start_level(session.all_sprites, session.enemy_group, session.player)
        tunnel = progress.tunnel
        tunnel.player_y = tunnel.top - session.player.height - 1
        tunnel.update(game.STEP, session.player)
        self.assertTrue(tunnel.complete)
        args = (session.all_sprites, session.enemy_group, session.bullet_group,
                session.enemy_bullets, session.player)
        progress.update(game.STEP, *args)
        self.assertEqual(progress.level, 4)
        self.assertIsNone(progress.tunnel)
        self.assertEqual(session.player.rect.bottom, game.HEIGHT - 20)
        progress.update(game.LEVEL_TRANSITION_DURATION, *args)
        self.assertEqual(len(session.enemy_group), game.DEFAULT_HORDE_SIZE)
        self.assertEqual(progress.level, 4)

    def test_debug_skip_enters_and_leaves_tunnel(self):
        session = game.GameSession()
        session.skip_level()
        session.skip_level()
        self.assertEqual(session.progress.level, 3)
        self.assertTrue(session.progress.transitioning)
        self.assertFalse(session.enemy_group)
        session.progress.update(game.LEVEL_TRANSITION_DURATION, session.all_sprites,
                                session.enemy_group, session.bullet_group,
                                session.enemy_bullets, session.player)
        self.assertIsNotNone(session.progress.tunnel)
        session.skip_level()
        self.assertEqual(session.progress.level, 4)
        self.assertIsNone(session.progress.tunnel)
        self.assertEqual(len(session.enemy_group), game.DEFAULT_HORDE_SIZE)


if __name__ == '__main__':
    unittest.main()
