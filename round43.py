import pygame as pg
import math
import random

pg.init()
clock = pg.time.Clock()
screen = pg.display.set_mode((1280, 720), pg.SRCALPHA)

class Bullet(pg.sprite.Sprite):
    def __init__(self, start_x, start_y, target_pos, *groups):
        super().__init__(*groups)
        self.image = pg.Surface((10, 10))
        pg.draw.circle(self.image, (255, 255, 0), (5, 5), 5)
        self.rect = self.image.get_rect()
        self.pos = pg.math.Vector2(start_x, start_y)
        self.rect.center = self.pos
        direction = pg.math.Vector2(target_pos) - self.pos
        if direction.length() == 0:
            direction = pg.math.Vector2(0, -1)  # Oletussuunta ylöspäin
        else:
            direction = direction.normalize()  # Muutetaan yksikkövektoriksi (pituus = 1)

        # Ammuksen nopeus pikseleinä per frame
        self.speed = 10
        self.velocity = direction * self.speed

    def update(self):
        # Päivitetään sijainti vektorilla
        self.pos += self.velocity
        self.rect.center = self.pos

        # Tuhoaa ammuksen automaattisesti, jos se lentää ulos ruudulta (esim. 800x600 alueelta)
        if self.rect.bottom < 0 or self.rect.top > 720 or self.rect.right < 0 or self.rect.left > 1280:
            self.kill()

class Player(pg.sprite.Sprite):
    def __init__(self, *groups ):
        super().__init__(*groups)
        self.radius = 64
        self.image = pg.Surface((128, 128))
        self.rect = self.image.get_rect()
        self.rect.x = screen.get_width() // 2 - self.radius
        self.rect.y = screen.get_height() - self.radius

        for r in range(self.radius, 1, -1):
            pg.draw.circle(self.image, (256 - r * 4, 0, 0), (self.radius, self.radius), r)

    def shoot(self, bullet_group):
        mouse_pos = pg.mouse.get_pos()
        start_x = self.rect.centerx
        start_y = self.rect.centery - (self.radius // 2)
        Bullet(start_x, start_y, mouse_pos, bullet_group)

class Enemy(pg.sprite.Sprite):
    def __init__(self, start_x, start_y, *groups):
        super().__init__(*groups)
        self.width = 24
        self.height = 32
        self.image = pg.Surface((self.width, self.height))
        self.rect = self.image.get_rect()
        pg.draw.rect(self.image, (255, 255, 255), (0, 0, self.rect.w, self.rect.h))
        pg.draw.rect(self.image, (0, 0, 0), (5, 5, 6, 6))
        pg.draw.rect(self.image, (0, 0, 0), (14, 5, 6, 6))
        pg.draw.rect(self.image, (0, 0, 0), (0, 22, 6, 8))
        pg.draw.rect(self.image, (0, 0, 0), (18, 22, 6, 8))
        pg.draw.rect(self.image, (0, 0, 0), (8, 28, 10, 6))
        self.base_x = float(start_x)
        self.base_y = float(start_y)

        self.rect = self.image.get_rect()
        self.rect.x = int(self.base_x)
        self.rect.y = int(self.base_y)

        self.direction = 1
        self.jump_distance = 20
        self.jump_duration = 400
        self.jump_height = 15
        self.jump_cooldown = 800
        self.jump_start_time = pg.time.get_ticks() - random.randint(0, self.jump_duration)
        self.is_dropping = False

    def update(self):
        current_time = pg.time.get_ticks()
        progress = (current_time - self.jump_start_time) / self.jump_duration

        if progress >= 1.0:
            progress = 0.0
            self.jump_start_time = current_time

            if self.is_dropping:
                self.base_y += self.height + 5
                self.direction *= -1
                self.is_dropping = False
            else:
                self.base_x += self.jump_distance * self.direction
                next_landing_x = self.base_x + (self.jump_distance * self.direction)
                if next_landing_x + self.width > 1280:
                    self.base_x = 1280 - self.width
                    self.is_dropping = True
                    # Jos se osuu vasempaan reunaan: kiinnitetään base_x nollaan ja käsketään tippua
                elif next_landing_x < 0:
                    self.base_x = 0
                    self.is_dropping = True

                # Tarkistetaan ruudun rajat seuraavaa loikkaa varten (oletusleveys 800)
                next_landing_x = self.base_x + (self.jump_distance * self.direction)
                if next_landing_x + self.width > 1280 or next_landing_x < 0:
                    # Jos seuraava loikka menisi yli rajojen, asetetaan seuraavaksi vuoroksi tippuminen
                    self.is_dropping = True

        if self.is_dropping:
            current_x = self.base_x
            current_y = self.base_y + (self.height * progress)
        else:
            current_x = self.base_x + (self.jump_distance * self.direction * progress)
            jump_y = math.sin(progress * math.pi) * self.jump_height
            current_y = self.base_y - jump_y

            # Päivitetään lopulliset koordinaatit rectiin
        self.rect.x = int(current_x)
        self.rect.y = int(current_y)


class Particle(pg.sprite.Sprite):
    def __init__(self, x, y, *groups):
        super().__init__(*groups)

        # 1. Määritetään räjähdyksen värivaiheet Pygamen Color-olioina
        self.color_red = pg.Color(255, 0, 0)
        self.color_yellow = pg.Color(255, 255, 0)
        self.color_white = pg.Color(255, 255, 255)
        self.color_black = pg.Color(20, 20, 20)  # Täysin mustan sijaan tummanharmaa näkyy mustalla taustalla "savuna"

        # Luodaan tyhjä pinta, johon väri päivitetään update-metodissa
        self.image = pg.Surface((4, 4))
        self.image.fill(self.color_red)
        self.rect = self.image.get_rect()

        # Sijainti float-muodossa
        self.pos_x = float(x)
        self.pos_y = float(y)
        self.rect.center = (int(self.pos_x), int(self.pos_y))

        # Fysiikat (Satunnainen suunta ja voima)
        angle = math.radians(random.uniform(0, 360))
        power = random.uniform(0.5, 8.0)  # Hieman lisää potkua alkuräjähdykseen

        self.vel_x = math.cos(angle) * power
        self.vel_y = math.sin(angle) * power

        self.gravity = 0.03
        self.friction = 0.95  # Hieman enemmän ilmanvastusta, jotta "savu" pysähtyy ilmaan

        # Elinikä frameina
        self.max_lifetime = random.randint(50, 90)
        self.lifetime = self.max_lifetime

    def update(self):
        # 1. Fysiikkapäivitykset
        self.vel_y += self.gravity
        self.vel_x *= self.friction
        self.vel_y *= self.friction

        self.pos_x += self.vel_x
        self.pos_y += self.vel_y

        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)

        # 2. VÄRIN MUUTOS ELINJÄLJELLÄ (0.0 -> 1.0)
        # Lasketaan progress: 0.0 (alussa) -> 1.0 (lopussa)
        progress = (self.max_lifetime - self.lifetime) / self.max_lifetime

        # Jaetaan elinaika kolmeen yhtä suureen vaiheeseen (0.33 välein)
        if progress < 0.33:
            # Vaihe 1: Punaisesta Keltaiseen
            # Skaalataan progress välille 0.0 - 1.0 tämän vaiheen sisällä
            stage_progress = progress / 0.33
            current_color = self.color_red.lerp(self.color_yellow, stage_progress)
        elif progress < 0.66:
            # Vaihe 2: Keltaisesta Valkoiseen
            stage_progress = (progress - 0.33) / 0.33
            current_color = self.color_yellow.lerp(self.color_white, stage_progress)
        else:
            # Vaihe 3: Valkoisesta Mustaan (Savu)
            stage_progress = (progress - 0.66) / 0.34
            current_color = self.color_white.lerp(self.color_black, stage_progress)

        # Täytetään hiukkasen pinta uudella värillä
        self.image.fill(current_color)

        # 3. Eliniän seuranta
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()


class RainbowBeamParticle(pg.sprite.Sprite):
    def __init__(self, x, y, angle, font, *groups):
        super().__init__(*groups)
        self.font = font
        self.pos_x = float(x)
        self.pos_y = float(y)

        # Suuri alkunopeus, jotta säde syöksyy nopeasti eteenpäin
        self.speed = 22.0
        self.vel_x = math.cos(angle) * self.speed
        self.vel_y = math.sin(angle) * self.speed

        # Pyörimisnopeus (Sincos-tyylinen)
        self.spin_speed = 80
        self.current_angle = random.randint(0, 360)

        # Luodaan tyhjä pinta
        self.image = pg.Surface((1, 1), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos_x), int(self.pos_y)))

    def update(self):
        # Liikutetaan hiukkasta eteenpäin
        self.pos_x += self.vel_x
        self.pos_y += self.vel_y

        elapsed = pg.time.get_ticks() / 1000.0

        # 1. PYÖRITYS AKSELIN YMPÄRI
        self.current_angle = (self.current_angle + self.spin_speed * (1 / 156)) % 360

        # 2. TIHEÄ GRADIENTTI (Liikkuu vasemmalta ylhäältä oikealle alas)
        rainbow_speed = 160
        # Muutettu kerrointa (0.5), jotta värien vaihtuvuus on entistä tiheämpää ja tarkempaa
        spatial_factor = (self.pos_x + self.pos_y) * 0.5
        hue = (spatial_factor + elapsed * rainbow_speed) % 360

        color = pg.Color(0, 0, 0)
        color.hsva = (hue, 100, 100, 100)

        # 3. TIHEÄ RENDERÖINTI
        # Käytetään rotozoomia luomaan pyörivä kirjain
        letter_surf = self.font.render("B", True, color)
        self.image = pg.transform.rotozoom(letter_surf, self.current_angle, 1.0)

        self.rect = self.image.get_rect(center=(int(self.pos_x), int(self.pos_y)))

        # Tuhotaan hiukkanen heti, jos se poistuu pelialueelta
        if self.pos_x < -50 or self.pos_x > 1330 or self.pos_y < -50 or self.pos_y > 770:
            self.kill()


class RainbowBeam:
    """Luokka, joka synnyttää hiukkasia tiheäksi jonoksi tulituksen aikana."""

    @staticmethod
    def fire(start_x, start_y, target_pos, font, bullet_group):
        dx = target_pos[0] - start_x
        dy = target_pos[1] - start_y
        angle = math.atan2(dy, dx)

        # Luodaan yhdellä framella 6 hiukkasta peräkkäin hyvin pienellä välillä (4 pikseliä),
        # jolloin ne limittyvät täysin päällekkäin ja muodostavat kiinteän nestemäisen pötkön.
        for i in range(6):
            spawn_x = start_x + math.cos(angle) * (i * 4)
            spawn_y = start_y + math.sin(angle) * (i * 4)
            RainbowBeamParticle(spawn_x, spawn_y, angle, font, bullet_group)


def main() -> int:
    beam_font = pg.font.SysFont("Arial", 32, bold=True)
    bullet_group = pg.sprite.Group()
    all_sprites = pg.sprite.Group()
    enemy_group = pg.sprite.Group()
    horde = 32
    cols = 8

    for h in range(horde):
        row = h // cols
        col = h % cols
        # Lasketaan aloituspaikat siten, että ne mahtuvat ruudulle nätisti
        start_x = 200 + col * 80
        start_y = 64 + row * 64
        Enemy(start_x, start_y, all_sprites, enemy_group)

    player = Player(all_sprites)
    running = True
    particles = 300
    while running:
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    running = False
            elif e.type == pg.MOUSEBUTTONDOWN:
                if e.button == 1:  # Vasen klikkaus
                    player.shoot(bullet_group)

        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            player.rect.x += -1
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            player.rect.x += 1
        mouse_buttons = pg.mouse.get_pressed()

        if mouse_buttons[2]:  # 2 tarkoittaa oikeaa hiiren painiketta (pohjassa pito)
            mouse_pos = pg.mouse.get_pos()
            start_x = player.rect.centerx
            start_y = player.rect.centery - (player.radius // 2)

            # Kutsutaan asetta joka framella, jolloin säde alkaa muodostua pelaajasta
            # ja pitkittyy sitä mukaa kun hiukkaset syöksyvät eteenpäin
            RainbowBeam.fire(start_x, start_y, mouse_pos, beam_font, bullet_group)
        screen.fill((0, 0, 0))
        all_sprites.update()
        bullet_group.update()
        hits = pg.sprite.groupcollide(bullet_group, enemy_group, True, True)
        for bullet, enemies in hits.items():
            for enemy in enemies:
                # 💥 TÄSSÄ POIMITAAN VIHOLLISEN KOORDINAATIT:
                # Käytetään center-koordinaatteja, jotta räjähdys syntyy keskelle vihollista
                expl_x = enemy.rect.centerx
                expl_y = enemy.rect.centery

                # Luodaan räjähdys ja lisätään se all_sprites-ryhmään piirtämistä varten
                for _ in range(particles):
                    Particle(expl_x, expl_y, all_sprites)
            # Tähän voi myöhemmin lisätä esim. pisteiden laskun tai räjähdysefektin

        # TAPA 2: Viholliset vs Pelaaja
        # spritecollidevertaa yhtä spritea ryhmään. False tarkoittaa, ettei pelaaja tuhoudu automaattisesti (peli vain loppuu).
        if pg.sprite.spritecollide(player, enemy_group, False):
            print("game over, man. it's game over!")
            running = False
        all_sprites.draw(screen)
        bullet_group.draw(screen)

        dt = clock.tick(156) / 1000
        pg.display.flip()

    pg.quit()

if __name__ == '__main__':
    main()