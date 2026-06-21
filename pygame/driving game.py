import pygame
import random

pygame.init()

WIDTH, HEIGHT = 800, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Highway Rush")

clock = pygame.time.Clock()
FPS = 60

ROAD_WIDTH = 420
ROAD_X = (WIDTH - ROAD_WIDTH) // 2
LANES = 3
LANE_WIDTH = ROAD_WIDTH // LANES

WHITE = (255, 255, 255)
BLACK = (15, 15, 15)
GRAY = (55, 55, 55)
YELLOW = (255, 215, 0)
RED = (235, 80, 80)
BLUE = (70, 170, 255)
GREEN = (100, 220, 120)

title_font = pygame.font.SysFont("arial", 56, bold=True)
main_font = pygame.font.SysFont("arial", 32)
small_font = pygame.font.SysFont("arial", 22)

road_offset = 0


class Player:
    def __init__(self):
        self.lane = 1
        self.width = 70
        self.height = 120
        self.x = ROAD_X + self.lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2
        self.y = HEIGHT - 150
        self.target_x = self.x

    def move_left(self):
        if self.lane > 0:
            self.lane -= 1
            self.target_x = ROAD_X + self.lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2

    def move_right(self):
        if self.lane < LANES - 1:
            self.lane += 1
            self.target_x = ROAD_X + self.lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2

    def update(self):
        self.x += (self.target_x - self.x) * 0.18

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self):
        pygame.draw.rect(screen, BLUE, self.rect(), border_radius=15)
        pygame.draw.rect(screen, BLACK, (self.x + 10, self.y + 20, 50, 25), border_radius=8)
        pygame.draw.rect(screen, BLACK, (self.x + 10, self.y + 75, 50, 25), border_radius=8)


class TrafficCar:
    def __init__(self, speed):
        self.width = 70
        self.height = 120
        self.lane = random.randint(0, LANES - 1)
        self.x = ROAD_X + self.lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2
        self.y = -self.height
        self.speed = speed
        self.color = random.choice([RED, GREEN, YELLOW])

    def update(self):
        self.y += self.speed

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self):
        pygame.draw.rect(screen, self.color, self.rect(), border_radius=15)
        pygame.draw.rect(screen, BLACK, (self.x + 10, self.y + 20, 50, 25), border_radius=8)
        pygame.draw.rect(screen, BLACK, (self.x + 10, self.y + 75, 50, 25), border_radius=8)


def draw_road():
    global road_offset

    screen.fill((30, 160, 30))

    pygame.draw.rect(screen, GRAY, (ROAD_X, 0, ROAD_WIDTH, HEIGHT))

    for lane in range(1, LANES):
        x = ROAD_X + lane * LANE_WIDTH
        for y in range(-40, HEIGHT, 80):
            pygame.draw.rect(screen, WHITE, (x - 4, y + road_offset, 8, 40))

    road_offset += 8
    if road_offset >= 80:
        road_offset = 0


def draw_popup(title, subtitle, alpha):
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(180)
    overlay.fill(BLACK)
    screen.blit(overlay, (0, 0))

    box = pygame.Surface((500, 250), pygame.SRCALPHA)
    box.fill((35, 35, 45, alpha))

    box_rect = box.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(box, box_rect)

    title_text = title_font.render(title, True, WHITE)
    sub_text = main_font.render(subtitle, True, (220, 220, 220))

    screen.blit(title_text, title_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
    screen.blit(sub_text, sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30)))


player = Player()
traffic = []

spawn_timer = 0
score = 0
speed = 7

state = "menu"
popup_alpha = 0

running = True

while running:
    clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            if state == "menu" and event.key == pygame.K_SPACE:
                state = "playing"

            elif state == "gameover" and event.key == pygame.K_r:
                player = Player()
                traffic.clear()
                spawn_timer = 0
                score = 0
                speed = 7
                popup_alpha = 0
                state = "playing"

            elif state == "playing":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    player.move_left()

                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    player.move_right()

    draw_road()

    if state == "playing":
        spawn_timer += 1

        if spawn_timer > 40:
            traffic.append(TrafficCar(speed))
            spawn_timer = 0

        player.update()

        for car in traffic[:]:
            car.update()
            car.draw()

            if car.rect().colliderect(player.rect()):
                state = "gameover"

            if car.y > HEIGHT:
                traffic.remove(car)
                score += 1

                if score % 10 == 0:
                    speed += 0.5

        player.draw()

        score_text = main_font.render(f"Score: {score}", True, WHITE)
        screen.blit(score_text, (20, 20))

    elif state == "menu":
        player.draw()

        popup_alpha = min(255, popup_alpha + 8)
        draw_popup("HIGHWAY RUSH", "Press SPACE to Start", popup_alpha)

    elif state == "gameover":
        for car in traffic:
            car.draw()

        player.draw()

        popup_alpha = min(255, popup_alpha + 8)

        draw_popup(
            "CRASHED!",
            f"Score: {score}   |   Press R to Restart",
            popup_alpha
        )

    pygame.display.flip()

pygame.display.quit()