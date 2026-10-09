import json
import math
import random
from functools import lru_cache
from pathlib import Path

import pygame as pg

WIDTH, HEIGHT = 1920, 1080
FPS = 156
STEP = 1 / FPS
ASSETS = Path(__file__).resolve().parent / "assets"
PLAYER_SPEED = 312  # Pikseliä sekunnissa, aiempi 2 px * 156 FPS.
BULLET_SPEED = 1560
SPACE_FIRE_INTERVAL = 0.15
LIGHTNING_CHARGES = 3
LIGHTNING_DROP_CHANCE = 0.025
CANNON_DROP_CHANCE = 0.025
MAX_CANNON_POWER = 4
POWERUP_SIZE = 48
POWERUP_GAP = 8
LIGHTNING_DURATION = 0.35
ENEMY_BULLET_SPEED = 420
ENEMY_BULLET_SIZE = (21, 32)
ENEMY_BULLET_HITBOX = (5, 7)
ENEMY_BULLET_ANCHOR = (10, 22)
MUZZLE_FPS = 60
MUZZLE_DURATION = 0.5
ENEMY_SHOT_INTERVAL = (2.5, 5.5)
RAINBOW_SPEED = 3432
RAINBOW_DURATION = 0.5
RAINBOW_CHARGES = 3
RAINBOW_EMISSION_RATE = 1872  # 12 S-kirjainta/askeleessa, noin 1,83 px välein.
POWERUP_DROP_CHANCE = 0.025
POWERUP_DROP_COOLDOWN = 12.0
RAINBOW_HUE_SPEED = 240
RAINBOW_PARTICLE_HUE_SPEED = 1080
STARTING_LIVES = 3
EXTRA_LIFE_DROP_CHANCE = 0.025
RESPAWN_PROTECTION = 2.0
EXPLOSION_HOLD = 0.5
ENEMY_SIZE = (36, 48)
ENEMY_GAP = 48
DEFAULT_HORDE_SIZE = 40
ENEMY_HIT_FLASH = 0.12
LEVEL_TRANSITION_DURATION = 2.4
ENEMY_SCORE = 100
MAX_PLAYER_NAME = 24
HIGHSCORE_PATH = Path(__file__).resolve().parent / "highscores.json"


@lru_cache(maxsize=None)
def ship_image(name, size):
    return pg.transform.scale(pg.image.load(ASSETS / name).convert_alpha(), size)


def fire_color(value):
    """Flaming-Junen lämpöpaletti."""
    value = max(0, min(255, int(value)))
    if value < 35:
        return (0, 0, 0)
    if value < 90:
        return (value * 2, 0, 0)
    if value < 150:
        return (255, (value - 90) * 3, 0)
    if value < 220:
        return (255, 180 + value - 150, (value - 150) // 2)
    return (255, 245, 210)


@lru_cache(maxsize=1)
def fire_frames():
    """Pieni lämpökenttä, jäähdytys ja sivuttaisvaellus kuten Flaming-Junessa.

    Lasketaan animaatio kerran, jotta tulipallojen määrä ei lisää simulointityötä.
    Liekki käännetään ammuksen taakse eli alaspäin.
    """
    rng = random.Random(43)
    width, height = 16, 28
    heat = [[0] * width for _ in range(height + 1)]
    frames = []
    for tick in range(64):
        for x in range(width):
            edge = abs(x - (width - 1) / 2) / (width / 2)
            heat[height][x] = int(rng.randint(180, 255) * max(0, 1 - edge ** 2))
        for y in range(height - 1, -1, -1):
            for x in range(1, width - 1):
                source = max(1, min(width - 2, x + rng.choice((-1, 0, 1))))
                value = (heat[y + 1][source - 1] + heat[y + 1][source]
                         + heat[y + 1][source + 1] + heat[y][x]) / 4 / 0.968
                heat[y][x] = max(0, min(255, int(value - rng.randint(2, 12))))
        if tick < 32:  # Lämmitetään kenttä ennen animaation tallentamista.
            continue
        flame = pg.Surface((width, height), pg.SRCALPHA)
        for y in range(height):
            for x in range(width):
                value = heat[y + 1][x]
                if value >= 35:
                    flame.set_at((x, height - 1 - y), (*fire_color(value), min(255, value * 2)))
        image = pg.Surface((64, 96), pg.SRCALPHA)
        for radius in range(26, 5, -2):
            pg.draw.circle(image, (255, 85, 0, 5 + (26 - radius)), (32, 28), radius)
        image.blit(pg.transform.scale(flame, (32, 56)), (16, 28))
        pg.draw.circle(image, (255, 105, 0, 255), (32, 28), 10)
        pg.draw.circle(image, (255, 195, 45, 255), (32, 26), 7)
        pg.draw.circle(image, (255, 245, 210, 255), (32, 24), 4)
        frames.append(image)
    return tuple(frames)


def cannon_fire_frames(power):
    return _cannon_fire_frames(min(3, max(0, power - 1)))


@lru_cache(maxsize=4)
def _cannon_fire_frames(stage):
    if stage == 0:
        return fire_frames()
    frames = []
    for source in fire_frames():
        image = source.copy()
        pixels = pg.PixelArray(image)
        for x in range(source.get_width()):
            for y in range(source.get_height()):
                color = source.get_at((x, y))
                if stage == 1:
                    tint = (color.r, round(color.g * 0.45), round(color.b * 0.3))
                elif stage == 2:
                    tint = (round(color.r * 0.35), round(color.g * 0.65), color.r)
                else:
                    brightness = max(color.r, color.g, color.b)
                    tint = (brightness, brightness, brightness)
                pixels[x, y] = (*tint, color.a)
        del pixels
        frames.append(image)
    return tuple(frames)


class Bullet(pg.sprite.Sprite):
    def __init__(self, start_x, start_y, *groups, damage=1):
        super().__init__(*groups)
        self.pos = pg.Vector2(start_x, start_y)
        self.age = 0.0
        self.damage = damage
        self.frames = cannon_fire_frames(damage)
        self.image = self.frames[0]
        # Hohto ja liekkihäntä eivät kasvata osuma-aluetta.
        self.rect = pg.Rect(0, 0, 16, 20)
        self.rect.center = self.pos

    def update(self, dt):
        self.age += dt
        self.pos.y -= BULLET_SPEED * dt
        self.rect.center = self.pos
        self.image = self.frames[int(self.age * 30) % len(self.frames)]
        if self.pos.y + 68 < 0:
            self.kill()

    def draw(self, surface):
        surface.blit(self.image, (round(self.pos.x) - 32, round(self.pos.y) - 28))


@lru_cache(maxsize=1)
def purple_fire_frames():
    frames = []
    for source in fire_frames():
        image = source.copy()
        # Oranssin lämpöpaletin punainen/keltaisuus muutetaan purppuraksi.
        # Alpha ja lämpökentän animaatio säilyvät samoina.
        pixels = pg.PixelArray(image)
        for x in range(image.get_width()):
            for y in range(image.get_height()):
                color = source.get_at((x, y))
                pixels[x, y] = (max(color.g, int(color.r * 0.8)), color.b,
                                color.r, color.a)
        del pixels
        frames.append(pg.transform.scale(pg.transform.flip(image, False, True), ENEMY_BULLET_SIZE))
    return tuple(frames)


class EnemyBullet(Bullet):
    def __init__(self, start_x, start_y, *groups):
        super().__init__(start_x, start_y, *groups)
        self.frames = purple_fire_frames()
        self.image = self.frames[0]
        self.rect.size = ENEMY_BULLET_HITBOX
        self.rect.center = self.pos

    def update(self, dt):
        self.age += dt
        self.pos.y += ENEMY_BULLET_SPEED * dt
        self.rect.center = self.pos
        self.image = self.frames[int(self.age * 30) % len(self.frames)]
        if self.pos.y - ENEMY_BULLET_ANCHOR[1] > HEIGHT:
            self.kill()

    def draw(self, surface):
        surface.blit(self.image, (round(self.pos.x) - ENEMY_BULLET_ANCHOR[0],
                                  round(self.pos.y) - ENEMY_BULLET_ANCHOR[1]))


def muzzle_frames(enemy=False):
    return _muzzle_frames(bool(enemy))


@lru_cache(maxsize=2)
def _muzzle_frames(enemy):
    """Lyhyt lämpökentän purkaus, jäähdytys, sivuttaisvaellus ja nouseva savu."""
    rng = random.Random(442)
    width, height = 12, 18
    heat = [[0] * width for _ in range(height + 1)]
    smoke = [(rng.uniform(-5, 5), rng.uniform(-9, 9), rng.uniform(22, 42),
              rng.uniform(3, 6)) for _ in range(7)]
    frames = []
    for tick in range(round(MUZZLE_DURATION * MUZZLE_FPS)):
        age = tick / MUZZLE_FPS
        for x in range(width):
            edge = abs(x - (width - 1) / 2) / (width / 2)
            heat[height][x] = int(rng.randint(200, 255) * max(0, 1 - edge ** 2)) if age < 0.09 else 0
        updated = [[0] * width for _ in range(height + 1)]
        updated[height] = heat[height][:]
        for y in range(height - 1, -1, -1):
            for x in range(1, width - 1):
                source = max(1, min(width - 2, x + rng.choice((-1, 0, 1))))
                value = (heat[y + 1][source - 1] + heat[y + 1][source]
                         + heat[y + 1][source + 1]) / 3
                updated[y][x] = max(0, int(value * 0.94 - rng.randint(4, 12)))
        heat = updated
        image = pg.Surface((64, 112), pg.SRCALPHA)
        # Savu nousee ylöspäin myös alaspäin ampuvan vihollisen tykistä.
        smoke_strength = min(1.0, age / 0.08) * max(0, 1 - age / MUZZLE_DURATION)
        for offset, drift, rise, radius in smoke:
            center = (round(32 + offset + drift * age), round(54 - rise * age))
            size = round(radius + age * 10)
            for ring in range(size, 0, -1):
                alpha = round(65 * smoke_strength * (1 - ring / (size + 1)))
                pg.draw.circle(image, (165, 180, 195, alpha), center, ring)
        flame = pg.Surface((width, height), pg.SRCALPHA)
        for y in range(height):
            for x in range(width):
                value = heat[y + 1][x]
                if value >= 35:
                    red, green, blue = fire_color(value)
                    color = (max(green, int(red * 0.8)), blue, red) if enemy else (red, green, blue)
                    flame.set_at((x, y), (*color, min(255, value * 2)))
        flame = pg.transform.scale(flame, (24, 36))
        if enemy:
            flame = pg.transform.flip(flame, False, True)
        image.blit(flame, (20, 56 if enemy else 20))
        # Välitön pieni lämpöpurkaus, joka sammuu ennen savua.
        burst = max(0.0, 1 - age / 0.1)
        if burst > 0:
            center = (32, 58 if enemy else 54)
            pg.draw.circle(image, (155, 100, 255, round(110 * burst)) if enemy
                           else (255, 150, 40, round(110 * burst)), center, max(1, round(8 * burst)))
            pg.draw.circle(image, (255, 245, 225, round(255 * burst)), center, max(1, round(3 * burst)))
        frames.append(image)
    return tuple(frames)


class MuzzleFlash(pg.sprite.Sprite):
    def __init__(self, x, y, *groups, enemy=False):
        super().__init__(*groups)
        self.frames = muzzle_frames(enemy)
        self.image = self.frames[0]
        self.rect = self.image.get_rect(topleft=(round(x) - 32, round(y) - 56))
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        if self.age >= MUZZLE_DURATION:
            self.kill()
        else:
            self.image = self.frames[min(len(self.frames) - 1, int(self.age * MUZZLE_FPS))]


@lru_cache(maxsize=4)
def shield_glow(ship):
    """Pehmeä vaaleansininen hohto aluksen siluetista, additiivisesti piirretty."""
    width, height = ship.get_size()
    glow = pg.Surface((width + 80, height + 80))
    silhouette = pg.mask.from_surface(ship).to_surface(
        setcolor=(65, 155, 220), unsetcolor=(0, 0, 0)).convert()
    for padding, strength in ((64, 0.35), (40, 0.55), (20, 0.8), (8, 1.0)):
        layer = pg.Surface(glow.get_size())
        expanded = pg.transform.smoothscale(silhouette, (width + padding, height + padding))
        expanded.fill((round(255 * strength),) * 3, special_flags=pg.BLEND_RGB_MULT)
        layer.blit(expanded, expanded.get_rect(center=layer.get_rect().center))
        # Pienennys ja suurennus pehmentävät reunat ilman kovaa kehystä.
        soft = pg.transform.smoothscale(layer, (max(1, layer.get_width() // 8),
                                               max(1, layer.get_height() // 8)))
        soft = pg.transform.smoothscale(soft, layer.get_size())
        glow.blit(soft, (0, 0), special_flags=pg.BLEND_RGB_ADD)
    return glow


class Player(pg.sprite.Sprite):
    def __init__(self, *groups, effects=None):
        super().__init__(*groups)
        self.width, self.height = ENEMY_SIZE
        self.image = ship_image(random.choice(tuple(f"pelaaja{i}.png" for i in range(1, 5))), ENEMY_SIZE)
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 20))
        self.pos_x = float(self.rect.x)
        self.lives = STARTING_LIVES
        self.fragments = []
        self.invulnerable_remaining = 0.0
        self.ship_surface = self.image
        self.shield_glow = shield_glow(self.ship_surface)
        self.explosion_age = 0.0
        self.explosion_outward_duration = 0.0
        self.cannon_power = 1
        self.lightning_charges = 0
        self.space_fire_remaining = 0.0
        self.effects = effects if effects is not None else pg.sprite.Group()
        self.rainbow_charges = 0
        self.rainbow_remaining = 0.0
        self.rainbow_emission = 0.0
        self.rainbow_clock = 0.0

    @property
    def active(self):
        return self.lives > 0 and not self.fragments

    def hit(self):
        if not self.active or self.invulnerable_remaining > 0:
            return False
        self.lives -= 1
        self.explosion_age = 0.0
        self.rainbow_remaining = 0.0
        for x in range(self.width):
            for y in range(self.height):
                color = self.ship_surface.get_at((x, y))
                if color.a:
                    origin = pg.Vector2(self.rect.x + x, self.rect.y + y)
                    velocity = pg.Vector2(1, 0).rotate(random.uniform(0, 360)) * random.uniform(500, 900)
                    self.fragments.append([origin, velocity, 0.0, color, random.randint(4, 8),
                                           random.uniform(0.15, 1.0) ** 0.5 * HEIGHT / 2])
        self.explosion_outward_duration = max(
            (fragment[5] / fragment[1].length() for fragment in self.fragments), default=0.0)
        self.image = pg.Surface(self.rect.size, pg.SRCALPHA)
        return True

    def update(self, dt):
        self.invulnerable_remaining = max(0.0, self.invulnerable_remaining - dt)
        if not self.fragments:
            return
        self.explosion_age += dt
        return_age = self.explosion_age - self.explosion_outward_duration - EXPLOSION_HOLD
        remaining = []
        for fragment in self.fragments:
            origin, velocity, distance, color, size, max_distance = fragment
            speed = velocity.length()
            if return_age <= 0:
                distance = min(max_distance, speed * self.explosion_age)
            else:
                distance = max(0.0, max_distance - speed * return_age)
            fragment[2] = distance
            if return_age <= 0 or distance > 0:
                remaining.append(fragment)
        self.fragments = remaining
        if not remaining and self.lives > 0:
            self.image = self.ship_surface
            self.invulnerable_remaining = RESPAWN_PROTECTION

    def draw_fragments(self, surface):
        for origin, velocity, distance, color, size, max_distance in self.fragments:
            position = origin + velocity.normalize() * distance
            surface.fill(color, (round(position.x - size / 2),
                                 round(position.y - size / 2), size, size))

    def draw_shield(self, surface):
        if self.active and self.invulnerable_remaining > 0:
            surface.blit(self.shield_glow,
                         self.shield_glow.get_rect(center=self.rect.center),
                         special_flags=pg.BLEND_RGB_ADD)

    def collect(self, powerup):
        if powerup.kind == "life":
            self.lives += 1
        elif powerup.kind == "cannon":
            self.cannon_power = min(MAX_CANNON_POWER, self.cannon_power + 1)
        elif powerup.kind == "lightning":
            self.lightning_charges += LIGHTNING_CHARGES
        else:
            self.rainbow_charges += RAINBOW_CHARGES

    def move(self, direction, dt):
        if not self.active:
            return
        self.pos_x = max(0, min(WIDTH - self.rect.width, self.pos_x + direction * PLAYER_SPEED * dt))
        self.rect.x = round(self.pos_x)

    def shoot(self, bullet_group):
        if self.active:
            Bullet(self.rect.centerx, self.rect.top, bullet_group, damage=self.cannon_power)
            MuzzleFlash(*self.rect.midtop, self.effects)

    def update_space_fire(self, held, dt, bullets):
        if not held or not self.active:
            self.space_fire_remaining = 0.0
            return
        self.space_fire_remaining -= dt
        while self.space_fire_remaining <= 0:
            self.shoot(bullets)
            self.space_fire_remaining += SPACE_FIRE_INTERVAL

    def fire_lightning(self, enemies, all_sprites, powerups, drops, progress):
        if not self.active or progress.transitioning or self.lightning_charges <= 0 or not enemies:
            return False
        enemy = random.choice(enemies.sprites())
        self.lightning_charges -= 1
        Lightning(self.rect.midtop, enemy.rect.center, all_sprites)
        MuzzleFlash(*self.rect.midtop, self.effects)
        damage_enemy(enemy, all_sprites, powerups, drops, progress, lethal=True)
        return True

    def start_rainbow(self):
        if not self.active or self.rainbow_charges <= 0 or self.rainbow_remaining > 0:
            return False
        self.rainbow_charges -= 1
        MuzzleFlash(*self.rect.midtop, self.effects)
        self.rainbow_remaining = RAINBOW_DURATION
        self.rainbow_emission = 0.0
        return True

    def update_rainbow(self, dt, target, font, bullet_group):
        self.rainbow_clock += dt
        active_time = min(dt, self.rainbow_remaining)
        if active_time <= 0:
            return
        self.rainbow_emission += active_time * RAINBOW_EMISSION_RATE
        count = int(self.rainbow_emission + 1e-9)
        self.rainbow_emission -= count
        RainbowBeam.fire(self.rect.centerx, self.rect.top, target, font, bullet_group, count,
                         hue=(self.rainbow_clock * RAINBOW_HUE_SPEED) % 360)
        self.rainbow_remaining = max(0.0, self.rainbow_remaining - dt)
        if self.rainbow_remaining < 1e-9:
            self.rainbow_remaining = 0.0


BIRD_FIRST_LEVEL = 5
RECT_ENEMY_FIRST_LEVEL = 6
ENEMY_CYCLE_LENGTH = 6
BIRD_COLORS = ((255, 65, 75), (65, 245, 245), (255, 80, 245), (250, 250, 75))
BIRD_ANIMATION_FPS = 6
BIRD_FLIGHT_SPEED = 20
BIRD_FLIGHT_AXIS = "x"


@lru_cache(maxsize=1)
def rect_enemy_image():
    """Palautettu commitista 3e8021c: alkuperäiset kuusi pg.draw.rect-komentoa."""
    image = pg.Surface((24, 32), pg.SRCALPHA)
    pg.draw.rect(image, (200, 255, 200), (0, 0, 24, 32))
    pg.draw.rect(image, (0, 0, 0, 0), (5, 5, 6, 6))
    pg.draw.rect(image, (0, 0, 0, 0), (14, 5, 6, 6))
    pg.draw.rect(image, (0, 0, 0, 0), (0, 22, 6, 8))
    pg.draw.rect(image, (0, 0, 0, 0), (18, 22, 6, 8))
    pg.draw.rect(image, (0, 0, 0, 0), (8, 28, 10, 6))
    pg.draw.rect(image, (0, 0, 0, 0), (0, 0, 4, 4))
    pg.draw.rect(image, (0, 0, 0, 0), (20, 0, 4, 4))
    return pg.transform.scale(image, ENEMY_SIZE)


@lru_cache(maxsize=4)
def bird_frames(color=BIRD_COLORS[1]):
    """Referenssikuvan pienet, yksiväriset pikselisiivet ja keskimmäinen vartalo."""
    frames = []
    for slope in (-0.4, 0.0, 0.4, 0.0):
        image = pg.Surface((12, 16), pg.SRCALPHA)
        for distance in range(1, 6):
            y = 7 + round(slope * distance)
            for x in (5 - distance, 6 + distance):
                image.set_at((x, y), color)
        pg.draw.rect(image, color, (5, 8, 2, 1))
        frames.append(pg.transform.scale(image, ENEMY_SIZE))
    return tuple(frames)


class Enemy(pg.sprite.Sprite):
    def __init__(self, start_x, start_y, *groups, enemy_group=None, level=1, effects=None):
        super().__init__(*groups)
        self.width, self.height = ENEMY_SIZE
        self.level = level
        self.enemy_type = (level - 1) % ENEMY_CYCLE_LENGTH + 1
        self.is_bird = self.enemy_type == BIRD_FIRST_LEVEL
        if self.is_bird:
            self.bird_color = random.choice(BIRD_COLORS)
            self.frames = bird_frames(self.bird_color)
        elif self.enemy_type == RECT_ENEMY_FIRST_LEVEL:
            self.frames = (rect_enemy_image(),)
        else:
            self.frames = (ship_image(f"vihu{self.enemy_type}.png", ENEMY_SIZE),)
        self.image = self.frames[0]
        self.normal_image = self.image
        self.flash_frames = []
        for source in self.frames:
            flash = source.copy()
            flash.fill((255, 255, 255, 0), special_flags=pg.BLEND_RGBA_ADD)
            self.flash_frames.append(flash)
        self.flash_image = self.flash_frames[0]
        self.animation_age = random.uniform(0, 4 / BIRD_ANIMATION_FPS) if self.is_bird else 0.0
        self.hitpoints = level
        self.speed_multiplier = 1.1 ** (level - 1)
        self.flash_remaining = 0.0
        self.rect = self.image.get_rect(topleft=(start_x, start_y))
        self.base_x, self.base_y = float(start_x), float(start_y)
        self.direction = 1
        self.jump_distance = 20
        self.jump_duration = 0.4
        self.jump_height = 15
        self.jump_cooldown = random.uniform(0.35, 1.3)
        self.phase = 0.0
        self.is_dropping = False
        self.enemy_group = enemy_group
        self.effects = effects if effects is not None else pg.sprite.Group()
        self.drop_y = None
        self.shot_remaining = random.uniform(*ENEMY_SHOT_INTERVAL)

    def take_hit(self, damage=1):
        if self.hitpoints <= 0:
            return False
        self.hitpoints = max(0, self.hitpoints - damage)
        if self.hitpoints == 0:
            self.kill()
            return True
        self.flash_remaining = ENEMY_HIT_FLASH
        self.image = self.flash_image
        return False

    def next_drop_y(self):
        """Ohita vastakkaiseen suuntaan kulkevat ja varatut laskeutumisrivit."""
        spacing = self.height + ENEMY_GAP
        target_y = self.base_y + spacing
        landing_direction = -self.direction
        enemies = self.enemy_group if self.enemy_group is not None else ()
        occupied = []
        for enemy in enemies:
            if enemy is self:
                continue
            if enemy.direction != landing_direction:
                occupied.append(enemy.base_y)
            if enemy.is_dropping and -enemy.direction != landing_direction:
                occupied.append(enemy.drop_y)
        while any(row is not None and abs(row - target_y) < 1 for row in occupied):
            target_y += spacing
        return target_y

    def update_weapon(self, dt, bullet_group):
        self.shot_remaining -= dt
        if self.shot_remaining <= 0:
            EnemyBullet(self.rect.centerx, self.rect.bottom + 12, bullet_group)
            MuzzleFlash(*self.rect.midbottom, self.effects, enemy=True)
            self.shot_remaining += random.uniform(*ENEMY_SHOT_INTERVAL)

    def update_flight(self, dt):
        distance = BIRD_FLIGHT_SPEED * dt
        previous = (self.base_x, self.base_y, self.direction, self.is_dropping, self.drop_y)
        wrapped = False
        if BIRD_FLIGHT_AXIS == "y":
            self.base_y += distance
            if self.base_y > HEIGHT:
                self.base_y = -float(self.height) + (self.base_y - HEIGHT)
                wrapped = True
        elif self.is_dropping:
            self.base_y = min(self.drop_y, self.base_y + distance)
            if self.base_y >= self.drop_y:
                self.direction *= -1
                self.is_dropping = False
                self.drop_y = None
        else:
            next_x = self.base_x + distance * self.direction
            self.base_x = max(0.0, min(WIDTH - self.width, next_x))
            if next_x < 0 or next_x > WIDTH - self.width:
                self.is_dropping = True
                self.drop_y = self.next_drop_y()
        candidate = self.rect.copy()
        candidate.topleft = (round(self.base_x), round(self.base_y))
        path = candidate if wrapped else self.rect.union(candidate)
        if self.is_dropping:
            path = path.union(pg.Rect(round(self.base_x), round(self.drop_y), self.width, self.height))
        if self.enemy_group is not None:
            for enemy in self.enemy_group:
                if enemy is self:
                    continue
                occupied = enemy.rect
                if enemy.is_dropping:
                    occupied = occupied.union(pg.Rect(round(enemy.base_x), round(enemy.drop_y),
                                                       enemy.width, enemy.height))
                if path.colliderect(occupied):
                    self.base_x, self.base_y, self.direction, self.is_dropping, self.drop_y = previous
                    return
        self.rect = candidate

    def update(self, dt):
        self.flash_remaining = max(0.0, self.flash_remaining - dt)
        self.animation_age += dt
        frame = int(self.animation_age * BIRD_ANIMATION_FPS) % len(self.frames)
        self.normal_image = self.frames[frame]
        self.flash_image = self.flash_frames[frame]
        self.image = self.flash_image if self.flash_remaining > 0 else self.normal_image
        dt *= self.speed_multiplier
        if self.is_bird:
            self.update_flight(dt)
            return
        previous = (self.phase, self.base_x, self.base_y, self.direction,
                    self.is_dropping, self.drop_y, self.jump_cooldown)
        previous_rect = self.rect.copy()
        self.phase += dt
        cycle = self.jump_duration + self.jump_cooldown
        while self.phase >= cycle:
            self.phase -= cycle
            self.jump_cooldown = random.uniform(0.35, 1.3)
            cycle = self.jump_duration + self.jump_cooldown
            if self.is_dropping:
                self.base_y = self.drop_y
                self.direction *= -1
                self.is_dropping = False
                self.drop_y = None
            else:
                self.base_x = max(0, min(WIDTH - self.width,
                                       self.base_x + self.jump_distance * self.direction))
                next_x = self.base_x + self.jump_distance * self.direction
                self.is_dropping = next_x < 0 or next_x + self.width > WIDTH
                if self.is_dropping:
                    self.drop_y = self.next_drop_y()
        progress = max(0.0, min(1.0, self.phase / self.jump_duration))
        if self.is_dropping:
            x = self.base_x
            y = self.base_y + (self.drop_y - self.base_y) * progress
        else:
            x = max(0, min(WIDTH - self.width,
                           self.base_x + self.jump_distance * self.direction * progress))
            y = self.base_y - math.sin(progress * math.pi) * self.jump_height
        candidate = self.rect.copy()
        candidate.topleft = (round(x), round(y))
        if self.enemy_group is not None:
            path = previous_rect.union(candidate)
            if self.is_dropping:
                path = path.union(pg.Rect(round(self.base_x), round(self.base_y),
                                          self.width, self.height))
                path = path.union(pg.Rect(round(self.base_x), round(self.drop_y),
                                          self.width, self.height))
            for enemy in self.enemy_group:
                if enemy is self:
                    continue
                # Vaakasuuntainen hyppy ei saa osua odottavaan rivinvaihtajaan.
                # Varaa myös hypyn korkeus ja koko seuraavan loikan leveys.
                occupied = enemy.rect.union(pg.Rect(round(enemy.base_x), round(enemy.base_y),
                                                    enemy.width, enemy.height))
                if enemy.is_dropping:
                    occupied = occupied.union(pg.Rect(round(enemy.base_x), round(enemy.drop_y),
                                                       enemy.width, enemy.height))
                if self.is_dropping and not previous[4]:
                    occupied.inflate_ip(2 * enemy.jump_distance, 2 * (enemy.jump_height + 4))
                if path.colliderect(occupied):
                    (self.phase, self.base_x, self.base_y, self.direction,
                     self.is_dropping, self.drop_y, self.jump_cooldown) = previous
                    return  # Odota, kunnes toinen vihollinen on väistänyt liikeradalta.
        self.rect = candidate


class Particle(pg.sprite.Sprite):
    def __init__(self, x, y, *groups):
        super().__init__(*groups)
        self.image = pg.Surface((4, 4), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.pos = pg.Vector2(x, y)
        angle = random.uniform(0, math.tau)
        self.velocity = pg.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(78, 1248)
        self.max_lifetime = random.uniform(50 / FPS, 90 / FPS)
        self.lifetime = self.max_lifetime

    def update(self, dt):
        self.velocity.y += 730 * dt
        self.velocity *= 0.95 **     (dt * FPS)
        self.pos += self.velocity * dt
        self.rect.center = self.pos
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.kill()
            return
        progress = 1 - self.lifetime / self.max_lifetime
        colors = (pg.Color(255, 0, 0), pg.Color(255, 255, 0), pg.Color(255, 255, 255), pg.Color(20, 20, 20))
        phase = min(2, int(progress * 3))
        self.image.fill(colors[phase].lerp(colors[phase + 1], progress * 3 - phase))


@lru_cache(maxsize=36)
def beam_letter(angle):
    font = pg.font.SysFont("Arial", 32, bold=True)
    return pg.transform.rotozoom(font.render("S", True, (255, 255, 255)), angle * 10, 1.0)


class RainbowBeamParticle(pg.sprite.Sprite):
    def __init__(self, x, y, angle, font, *groups, hue=0.0):
        super().__init__(*groups)
        self.pos = pg.Vector2(x, y)
        self.velocity = pg.Vector2(math.cos(angle), math.sin(angle)) * RAINBOW_SPEED
        self.age = 0.0
        self.birth_hue = hue
        self.hue = hue % 360
        self.current_angle = random.randrange(360)
        self.image = pg.Surface((1, 1), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=self.pos)

    def update(self, dt):
        self.pos += self.velocity * dt
        self.age += dt
        self.current_angle = (self.current_angle + 80 * dt) % 360
        color = pg.Color(0, 0, 0)
        # Väri riippuu vain ajasta, joten liikesuunta ei voi kumota värikiertoa.
        self.hue = (self.birth_hue + self.age * RAINBOW_PARTICLE_HUE_SPEED) % 360
        color.hsva = (self.hue, 100, 100, 100)
        self.image = beam_letter(int(self.current_angle // 10)).copy()
        self.image.fill(color, special_flags=pg.BLEND_RGBA_MULT)
        self.rect = self.image.get_rect(center=self.pos)
        if self.pos.x < -50 or self.pos.x > WIDTH + 50 or self.pos.y < -50 or self.pos.y > HEIGHT + 50:
            self.kill()

    def draw(self, surface):
        surface.blit(self.image, self.rect)


class RainbowBeam:
    @staticmethod
    def fire(start_x, start_y, target_pos, font, bullet_group, count=6, *, hue=0.0):
        angle = math.atan2(target_pos[1] - start_y, target_pos[0] - start_x)
        for i in range(count):
            offset = i * RAINBOW_SPEED / RAINBOW_EMISSION_RATE
            RainbowBeamParticle(start_x + math.cos(angle) * offset,
                                start_y + math.sin(angle) * offset, angle, font, bullet_group,
                                hue=hue + i * RAINBOW_PARTICLE_HUE_SPEED / RAINBOW_EMISSION_RATE)


class Lightning(pg.sprite.Sprite):
    """Välitön osuma ratkaistaan erikseen; haarat ovat pelkkä visuaalinen efekti."""
    def __init__(self, start, target, *groups):
        super().__init__(*groups)
        self.age = 0.0
        self.paths = []
        start, target = pg.Vector2(start), pg.Vector2(target)
        delta = target - start
        direction = delta.normalize() if delta.length_squared() else pg.Vector2(0, -1)
        side = pg.Vector2(-direction.y, direction.x)
        segments = max(8, int(delta.length() / 28))
        main = [start]
        for index in range(1, segments):
            progress = index / segments
            main.append(start + delta * progress + side * random.uniform(-28, 28))
        main.append(target)
        self.paths.append(main)
        # Sivuharat ja niiden pienemmät haarat tekevät luonnollisen salaman.
        for index in range(2, segments, max(1, segments // 8)):
            branch_direction = direction.rotate(random.choice((-1, 1)) * random.uniform(35, 100))
            length = random.uniform(50, 170)
            branch = [main[index]]
            for step in range(1, 6):
                branch.append(main[index] + branch_direction * length * step / 5
                              + side * random.uniform(-14, 14))
            self.paths.append(branch)
            twig_direction = branch_direction.rotate(random.choice((-45, 45)))
            self.paths.append([branch[2], branch[2] + twig_direction * 25 + side * 8,
                               branch[2] + twig_direction * 60])
        points = [point for path in self.paths for point in path]
        left, top = math.floor(min(p.x for p in points)) - 12, math.floor(min(p.y for p in points)) - 12
        right, bottom = math.ceil(max(p.x for p in points)) + 12, math.ceil(max(p.y for p in points)) + 12
        self.rect = pg.Rect(left, top, right - left + 1, bottom - top + 1)
        self.image = pg.Surface(self.rect.size, pg.SRCALPHA)
        for index, path in enumerate(self.paths):
            local = [(round(point.x - left), round(point.y - top)) for point in path]
            for width, color in ((16, (45, 110, 255, 30)), (9, (65, 165, 255, 70)),
                                 (4, (130, 215, 255, 220)), (2, (235, 250, 255, 255))):
                pg.draw.lines(self.image, color, False, local, width if index == 0 else max(1, width // 2))

    def update(self, dt):
        self.age += dt
        if self.age >= LIGHTNING_DURATION:
            self.kill()
            return
        flicker = 1.0 if int(self.age * 60) % 3 else 0.65
        self.image.set_alpha(round(255 * (1 - self.age / LIGHTNING_DURATION) * flicker))


class PowerUp(pg.sprite.Sprite):
    def __init__(self, x, y, *groups, kind="rainbow"):
        self.kind = kind
        super().__init__(*groups)
        self.image = pg.Surface((48, 48), pg.SRCALPHA)
        if kind == "cannon":
            pg.draw.circle(self.image, (255, 80, 35, 100), (24, 24), 23)
            pg.draw.circle(self.image, (255, 175, 90), (24, 24), 22, 2)
            font = pg.font.SysFont("Arial", 24, bold=True)
            text = font.render("C+", True, (255, 245, 225))
            self.image.blit(text, text.get_rect(center=(24, 24)))
        elif kind == "lightning":
            pg.draw.circle(self.image, (70, 170, 255, 110), (24, 24), 23)
            pg.draw.circle(self.image, (150, 225, 255), (24, 24), 22, 2)
            pg.draw.polygon(self.image, (240, 250, 255),
                            ((28, 5), (12, 27), (23, 25), (18, 43), (36, 19), (25, 21)))
        else:
            for i in range(24):
                color = pg.Color(0, 0, 0)
                color.hsva = (i * 15, 100, 100, 100)
                angle = i * math.tau / 24
                pg.draw.circle(self.image, color,
                               (round(24 + math.cos(angle) * 18), round(24 + math.sin(angle) * 18)), 5)
            font = pg.font.SysFont("Arial", 24, bold=True)
            text = font.render("+1" if kind == "life" else "R", True, (255, 255, 255))
            self.image.blit(text, text.get_rect(center=(24, 24)))
        self.pos = pg.Vector2(x, y)
        self.rect = self.image.get_rect(center=self.pos)

    def update(self, dt):
        self.pos.y += 180 * dt
        self.rect.center = self.pos
        if self.rect.top > HEIGHT:
            self.kill()


class PowerUpDrops:
    def __init__(self, player=None):
        self.player = player
        self.cooldown = 0.0
        self.life_cooldown = 0.0
        self.lightning_cooldown = 0.0
        self.cannon_cooldown = 0.0

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.life_cooldown = max(0.0, self.life_cooldown - dt)
        self.lightning_cooldown = max(0.0, self.lightning_cooldown - dt)
        self.cannon_cooldown = max(0.0, self.cannon_cooldown - dt)

    def spawn_drop(self, center, all_sprites, powerups, kind):
        spacing = POWERUP_SIZE + POWERUP_GAP
        half = POWERUP_SIZE // 2
        x = max(half, min(WIDTH - half, round(center[0])))
        y = max(half, min(HEIGHT - half, round(center[1])))
        # Etsi lähin vapaa paikka; kaikki powerupit putoavat samaa nopeutta.
        def offsets(count):
            yield 0
            for index in range(1, count + 1):
                yield index * spacing
                yield -index * spacing

        for dy in offsets(HEIGHT // spacing + 1):
            for dx in offsets(WIDTH // spacing + 1):
                candidate = pg.Rect(0, 0, POWERUP_SIZE, POWERUP_SIZE)
                candidate.center = (x + dx, y + dy)
                if (candidate.left < 0 or candidate.right > WIDTH
                        or candidate.top < 0 or candidate.bottom > HEIGHT):
                    continue
                if any(candidate.inflate(POWERUP_GAP * 2, POWERUP_GAP * 2).colliderect(drop.rect)
                       for drop in powerups):
                    continue
                PowerUp(*candidate.center, all_sprites, powerups, kind=kind)
                return True
        return False

    def try_drop_cannon(self, center, all_sprites, powerups):
        if self.player is not None and self.player.cannon_power >= MAX_CANNON_POWER:
            return False
        if self.cannon_cooldown > 0 or random.random() >= CANNON_DROP_CHANCE:
            return False
        if not self.spawn_drop(center, all_sprites, powerups, "cannon"):
            return False
        self.cannon_cooldown = POWERUP_DROP_COOLDOWN
        return True

    def try_drop_lightning(self, center, all_sprites, powerups):
        if self.lightning_cooldown > 0 or random.random() >= LIGHTNING_DROP_CHANCE:
            return False
        if not self.spawn_drop(center, all_sprites, powerups, "lightning"):
            return False
        self.lightning_cooldown = POWERUP_DROP_COOLDOWN
        return True

    def try_drop_life(self, center, all_sprites, powerups):
        if self.life_cooldown > 0 or random.random() >= EXTRA_LIFE_DROP_CHANCE:
            return False
        if not self.spawn_drop(center, all_sprites, powerups, "life"):
            return False
        self.life_cooldown = POWERUP_DROP_COOLDOWN
        return True

    def try_drop(self, center, all_sprites, powerups):
        if self.cooldown > 0 or random.random() >= POWERUP_DROP_CHANCE:
            return False
        if not self.spawn_drop(center, all_sprites, powerups, "rainbow"):
            return False
        self.cooldown = POWERUP_DROP_COOLDOWN
        return True


def spawn_enemies(all_sprites, enemy_group, horde=DEFAULT_HORDE_SIZE, *, level=1):
    spacing = ENEMY_SIZE[0] + ENEMY_GAP
    cols = min(horde, max(1, (WIDTH - ENEMY_GAP) // spacing))
    formation_width = cols * spacing - ENEMY_GAP
    left = (WIDTH - formation_width) // 2
    for index in range(horde):
        enemy = Enemy(left + (index % cols) * spacing,
              64 + (index // cols) * (ENEMY_SIZE[1] + ENEMY_GAP), all_sprites, enemy_group,
              enemy_group=enemy_group, level=level, effects=all_sprites)
        enemy.phase = -random.uniform(0, 1.3)


@lru_cache(maxsize=4)
def level_title(level):
    return pg.font.SysFont("Arial", 96, bold=True).render(
        f"LEVEL {level}", True, (255, 255, 255)).convert_alpha()


@lru_cache(maxsize=64)
def dissolving_title(level, frame):
    """Vaakasuuntainen blur ja toistettava pikselien hajoaminen uloshäivytyksessä."""
    source = level_title(level)
    progress = max(0.0, min(1.0, frame / 30))
    spread = round(120 * progress ** 1.3)
    width, height = source.get_size()
    result = pg.Surface((width + 2 * spread, height), pg.SRCALPHA)
    if progress >= 1:
        return result
    # Skaalaa vain vaakasuunnassa: kirjaimet leviävät, mutta eivät pystysuunnassa.
    small = pg.transform.smoothscale(source, (max(1, round(width / (1 + spread / 3))), height))
    blurred = pg.transform.smoothscale(small, (width, height))
    blurred.set_alpha(45)
    for sample in range(-4, 5):
        result.blit(blurred, (spread + round(sample * spread / 4), 0))
    # Samat satunnaiset kohdat katoavat vähitellen, eivät välky uusiksi joka kuvassa.
    rng = random.Random(43)
    for y in range(0, height, 3):
        for x in range(0, result.get_width(), 3):
            if rng.random() < progress:
                result.fill((0, 0, 0, 0), (x, y, 3, 3))
    result.set_alpha(round(255 * (1 - progress)))
    return result


class LevelProgress:
    def __init__(self):
        self.level = 1
        self.score = 0
        self.transition_remaining = 0.0

    @property
    def transitioning(self):
        return self.transition_remaining > 0

    @property
    def text_alpha(self):
        if not self.transitioning:
            return 0
        elapsed = LEVEL_TRANSITION_DURATION - self.transition_remaining
        return round(255 * max(0.0, min(1.0, elapsed / 0.7,
                                      self.transition_remaining / 0.5)))

    def update(self, dt, all_sprites, enemies, bullets, enemy_bullets, player):
        if self.transitioning:
            self.transition_remaining = max(0.0, self.transition_remaining - dt)
            if not self.transitioning:
                spawn_enemies(all_sprites, enemies, level=self.level)
        elif not enemies and player.lives > 0:
            self.level += 1
            self.transition_remaining = LEVEL_TRANSITION_DURATION
            bullets.empty()
            enemy_bullets.empty()
            player.rainbow_remaining = 0.0


def damage_enemy(enemy, all_sprites, powerups, drops, progress, *, lethal=False, damage=1):
    if not enemy.take_hit(enemy.hitpoints if lethal else damage):
        return False
    progress.score += ENEMY_SCORE
    for _ in range(120):
        Particle(*enemy.rect.center, all_sprites)
    drops.try_drop(enemy.rect.center, all_sprites, powerups)
    drops.try_drop_life(enemy.rect.center, all_sprites, powerups)
    drops.try_drop_lightning(enemy.rect.center, all_sprites, powerups)
    drops.try_drop_cannon(enemy.rect.center, all_sprites, powerups)
    return True


def resolve_enemy_hits(bullets, enemies, all_sprites, powerups, drops, progress):
    for bullet in list(bullets):
        targets = pg.sprite.spritecollide(bullet, enemies, False)
        if not targets:
            continue
        bullet.kill()
        enemy = targets[0]
        damage_enemy(enemy, all_sprites, powerups, drops, progress, damage=getattr(bullet, "damage", 1))


def clean_player_name(name):
    if not isinstance(name, str):
        return ""
    return "".join(character for character in name if character.isprintable()).strip()[:MAX_PLAYER_NAME]


class HighScores:
    def __init__(self, path=HIGHSCORE_PATH):
        self.path = Path(path)
        self.entries = []
        self.error = ""
        try:
            entries = json.loads(self.path.read_text())
            if not isinstance(entries, list):
                raise ValueError("Invalid highscore list")
            self.entries = sorted(
                [{"score": entry["score"], "level": entry["level"],
                  "name": clean_player_name(entry.get("name", "")) or "John Doe"}
                 for entry in entries if isinstance(entry, dict)
                 and type(entry.get("score")) is int and entry["score"] >= 0
                 and type(entry.get("level")) is int and entry["level"] >= 1],
                key=lambda entry: entry["score"], reverse=True)[:10]
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.error = "Could not load high scores."

    def add(self, score, level, name=""):
        name = clean_player_name(name) or random.choice(("John Doe", "Jane Doe"))
        entry = {"score": score, "level": level, "name": name}
        self.entries.append(entry)
        self.entries.sort(key=lambda item: item["score"], reverse=True)
        self.entries = self.entries[:10]
        rank = next((index + 1 for index, item in enumerate(self.entries) if item is entry), None)
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(self.entries, indent=2) + "\n")
            temporary.replace(self.path)
            self.error = ""
        except OSError:
            self.error = "Could not save high scores."
        return rank


class GameSession:
    def __init__(self):
        self.progress = LevelProgress()
        self.drops = PowerUpDrops()
        self.bullet_group, self.all_sprites, self.enemy_group, self.powerups, self.enemy_bullets = (
            pg.sprite.Group() for _ in range(5))
        spawn_enemies(self.all_sprites, self.enemy_group)
        self.player = Player(self.all_sprites, effects=self.all_sprites)
        self.drops.player = self.player
        self.game_over = False
        self.restart_ready = False
        self.highscore_rank = None
        self.entering_name = False
        self.player_name = ""

    def skip_level(self):
        if self.game_over or self.player.lives <= 0:
            return False
        for group in (self.all_sprites, self.bullet_group, self.enemy_bullets):
            for sprite in list(group):
                if sprite is not self.player:
                    sprite.kill()
        self.progress.level += 1
        self.progress.transition_remaining = 0.0
        self.player.rainbow_remaining = 0.0
        self.player.rainbow_emission = 0.0
        spawn_enemies(self.all_sprites, self.enemy_group, level=self.progress.level)
        return True

    def finish_if_dead(self, highscores, space_held=False):
        if not self.game_over and self.player.lives <= 0 and not self.player.fragments:
            self.game_over = True
            self.restart_ready = not space_held
            self.entering_name = True

    def submit_name(self, highscores):
        if not self.entering_name:
            return False
        self.highscore_rank = highscores.add(self.progress.score, self.progress.level, self.player_name)
        self.entering_name = False
        return True

    def handle_name_event(self, event, highscores):
        if event.type == pg.TEXTINPUT:
            self.player_name = (self.player_name + "".join(
                character for character in event.text if character.isprintable()))[:MAX_PLAYER_NAME]
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_BACKSPACE:
                self.player_name = self.player_name[:-1]
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER) and not getattr(event, "repeat", False):
                return self.submit_name(highscores)
        return False


def draw_highscores(screen, highscores, session, title_font, row_font):
    shade = pg.Surface(screen.get_size(), pg.SRCALPHA)
    shade.fill((3, 8, 22, 220))
    screen.blit(shade, (0, 0))
    line_height = min(40, max(22, HEIGHT // 22))
    y = max(16, (HEIGHT - (len(highscores.entries) + (8 if session.entering_name else 5)) * line_height - 80) // 2)

    def line(text, color=(225, 240, 255), font=row_font):
        nonlocal y
        image = font.render(text, True, color)
        screen.blit(image, image.get_rect(midtop=(WIDTH // 2, y)))
        y += max(line_height, image.get_height() + 8)

    line("GAME OVER", (155, 225, 255), title_font)
    line(f"Score: {session.progress.score}    Level: {session.progress.level}")
    if session.entering_name:
        line("Enter your name:", (155, 225, 255))
        line(f"{session.player_name}_", (255, 255, 255))
        line("ENTER — save (leave blank for John Doe / Jane Doe)")
    line("HIGH SCORES", (155, 225, 255))
    for rank, entry in enumerate(highscores.entries, 1):
        color = (255, 230, 120) if rank == session.highscore_rank else (225, 240, 255)
        line(f"{rank:2}.   {entry['name']}    {entry['score']} points    Level {entry['level']}", color)
    y += line_height // 2
    if not session.entering_name:
        line("SPACE — new game    |    ESC — quit", (155, 225, 255))
    if highscores.error:
        line(highscores.error, (255, 190, 140))


class StartScreen:
    def __init__(self, size):
        self.age = 0.0
        source = pg.image.load(ASSETS / "round43-logo.png").convert_alpha()
        width, height = size
        scale = min(width / source.get_width(), height / source.get_height())
        self.logo = pg.transform.smoothscale(source, (max(1, round(source.get_width() * scale)),
                                                      max(1, round(source.get_height() * scale))))
        font = pg.font.SysFont("Arial", max(20, round(height / 36)))
        self.prompt = font.render("Press space bar to start the game", True, (255, 255, 255))
        if self.prompt.get_width() > width * 0.9:
            factor = width * 0.9 / self.prompt.get_width()
            self.prompt = pg.transform.smoothscale(self.prompt, (round(self.prompt.get_width() * factor),
                                                                max(1, round(self.prompt.get_height() * factor))))

    @property
    def prompt_alpha(self):
        return round(255 * (1 - math.cos(self.age * math.tau / 2.8)) / 2)

    def update(self, dt):
        self.age += dt

    def draw(self, screen):
        screen.fill((0, 0, 0))
        screen.blit(self.logo, self.logo.get_rect(center=screen.get_rect().center))
        self.prompt.set_alpha(self.prompt_alpha)
        screen.blit(self.prompt, self.prompt.get_rect(
            midbottom=(screen.get_width() // 2, screen.get_height() - max(24, round(screen.get_height() * 0.06)))))


def main() -> int:
    global WIDTH, HEIGHT
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT), pg.FULLSCREEN)
    WIDTH, HEIGHT = screen.get_size()
    clock = pg.time.Clock()
    background = pg.image.load(ASSETS / "space_background.jpg").convert()
    background = pg.transform.smoothscale(background, (WIDTH, HEIGHT))
    beam_font = pg.font.SysFont("Arial", 32, bold=True)
    hud_font = pg.font.SysFont("Arial", 24, bold=True)
    highscores = HighScores()
    title_font = pg.font.SysFont("Arial", 64, bold=True)
    session = None
    start_screen = StartScreen(screen.get_size())
    fire_frames()
    purple_fire_frames()
    muzzle_frames()
    muzzle_frames(enemy=True)
    for angle in range(36):
        beam_letter(angle)
    running = True
    accumulator = 0.0
    clock.tick()  # Kuvien latausaika ei kuulu ensimmäiseen peliaskeleeseen.
    while running:
        elapsed = min(clock.tick(FPS) / 1000, 0.25)
        accumulator += elapsed
        for event in pg.event.get():
            if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                if session is not None and session.entering_name:
                    session.submit_name(highscores)
                    pg.key.stop_text_input()
                running = False
            elif session is None:
                if event.type == pg.KEYDOWN and event.key == pg.K_SPACE and not getattr(event, "repeat", False):
                    session = GameSession()
                    accumulator = 0.0
            elif session.game_over:
                if session.entering_name:
                    if session.handle_name_event(event, highscores):
                        pg.key.stop_text_input()
                    continue
                if event.type == pg.KEYUP and event.key == pg.K_SPACE:
                    session.restart_ready = True
                elif (event.type == pg.KEYDOWN and event.key == pg.K_SPACE
                      and session.restart_ready and not getattr(event, "repeat", False)):
                    session = GameSession()
                    accumulator = 0.0
            elif event.type == pg.KEYDOWN and event.key == pg.K_F5 and not getattr(event, "repeat", False):
                session.skip_level()
                accumulator = 0.0
            elif event.type == pg.KEYDOWN and not session.progress.transitioning and not getattr(event, "repeat", False):
                if event.key == pg.K_SPACE:
                    session.player.shoot(session.bullet_group)
                    session.player.space_fire_remaining = SPACE_FIRE_INTERVAL
                elif event.key == pg.K_F1:
                    session.player.fire_lightning(session.enemy_group, session.all_sprites, session.powerups, session.drops, session.progress)
            elif event.type == pg.MOUSEBUTTONDOWN and not session.progress.transitioning:
                if event.button == 1:
                    session.player.shoot(session.bullet_group)
                elif event.button == 3:
                    session.player.start_rainbow()
        if not running:
            break
        if session is None:
            accumulator = 0.0
            start_screen.update(elapsed)
            start_screen.draw(screen)
            pg.display.flip()
            continue
        keys = pg.key.get_pressed()
        direction = int(keys[pg.K_RIGHT] or keys[pg.K_d]) - int(keys[pg.K_LEFT] or keys[pg.K_a])
        target = pg.mouse.get_pos()
        if session.game_over:
            accumulator = 0.0
            if not keys[pg.K_SPACE]:
                session.restart_ready = True
        while not session.game_over and accumulator + 1e-9 >= STEP:
            session.drops.update(STEP)
            session.player.move(direction, STEP)
            session.player.update_space_fire(keys[pg.K_SPACE] and not session.progress.transitioning, STEP, session.bullet_group)
            if not session.progress.transitioning:
                session.player.update_rainbow(STEP, target, beam_font, session.bullet_group)
            session.all_sprites.update(STEP)
            session.bullet_group.update(STEP)
            session.enemy_bullets.update(STEP)
            resolve_enemy_hits(session.bullet_group, session.enemy_group, session.all_sprites, session.powerups, session.drops, session.progress)
            if session.player.active:
                for powerup in pg.sprite.spritecollide(session.player, session.powerups, True):
                    session.player.collect(powerup)
                if session.player.cannon_power >= MAX_CANNON_POWER:
                    for powerup in list(session.powerups):
                        if powerup.kind == "cannon":
                            powerup.kill()
            for enemy in session.enemy_group:
                enemy.update_weapon(STEP, session.enemy_bullets)
            if session.player.active and (pg.sprite.spritecollide(session.player, session.enemy_group, False)
                    or pg.sprite.spritecollide(session.player, session.enemy_bullets, True)):
                session.player.hit()
            session.progress.update(STEP, session.all_sprites, session.enemy_group, session.bullet_group, session.enemy_bullets, session.player)
            was_game_over = session.game_over
            session.finish_if_dead(highscores, keys[pg.K_SPACE])
            if session.game_over and not was_game_over:
                pg.key.start_text_input()
                pg.key.set_text_input_rect(pg.Rect(WIDTH // 4, HEIGHT // 3, WIDTH // 2, 40))
            accumulator -= STEP
            if not running:
                break
        screen.blit(background, (0, 0))
        session.player.draw_shield(screen)
        session.all_sprites.draw(screen)
        session.player.draw_fragments(screen)
        for bullet in session.bullet_group:
            bullet.draw(screen)
        for bullet in session.enemy_bullets:
            bullet.draw(screen)
        active = f"  |  burst {session.player.rainbow_remaining:.1f} s" if session.player.rainbow_remaining else ""
        hud = hud_font.render(f"Score: {session.progress.score}  |  Level: {session.progress.level}  |  Lives: {session.player.lives}  |  Rainbow: {session.player.rainbow_charges} x {RAINBOW_DURATION:g} s  |  Lightning F1: {session.player.lightning_charges}{active}", True, (255, 255, 255))
        screen.blit(hud, (20, HEIGHT - 36))
        cannon_hud = hud_font.render(f"MAIN CANNON POWER: {session.player.cannon_power}/{MAX_CANNON_POWER} HP",
                                     True, (255, 255, 255))
        screen.blit(cannon_hud, (20, 20))
        if session.progress.transitioning and not session.game_over:
            if session.progress.transition_remaining <= 0.5:
                frame = round((1 - session.progress.transition_remaining / 0.5) * 30)
                title = dissolving_title(session.progress.level, frame)
            else:
                title = level_title(session.progress.level).copy()
                title.set_alpha(session.progress.text_alpha)
            screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        if session.game_over:
            draw_highscores(screen, highscores, session, title_font, hud_font)
        pg.display.flip()
    pg.quit()
    return 0


if __name__ == '__main__':
    main()
