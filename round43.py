import pygame as pg

pg.init()
clock = pg.time.Clock()
screen = pg.display.set_mode((1280, 720), pg.SRCALPHA)

class Player:
    def __init__(self):
        self.x = screen.get_width() // 2
        self.y = screen.get_height()
        self.radius = 64
        self.surface = pg.Surface((64, 64))
        pg.draw.circle(self.surface, (255, 0, 0), )

    def draw(self, surface):
        surface.blit(self.surface, (self.x, self.y))

    def update(self, amount: int):
        self.x += amount

player = Player()

running = True
while running:
    for e in pg.event.get():
        if e.type == pg.QUIT:
            running = False
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                running = False
            if e.key == pg.K_a:
                player.update(-1)
            if e.key == pg.K_d:
                player.update(1)

    screen.fill((0, 0, 0))

    player.draw(screen)
    dt = clock.tick(156) / 1000
    pg.display.flip()

pg.quit()