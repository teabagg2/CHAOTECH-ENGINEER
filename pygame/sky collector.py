import pygame
import random
import math

pygame.init()

WIDTH, HEIGHT = 900, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Sky Collector")

clock = pygame.time.Clock()

WHITE = (255, 255, 255)
BLACK = (20, 20, 30)
BLUE = (80, 180, 255)
RED = (255, 80, 80)
YELLOW = (255, 215, 0)
GREEN = (100, 255, 140)
PURPLE = (180, 100, 255)
GRAY = (120, 120, 120)

font_large = pygame.font.SysFont("arial", 52, bold=True)
font_medium = pygame.font.SysFont("arial", 32)
font_small = pygame.font.SysFont("arial", 22)


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.life = 30
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-4, 4)
        self.size = random.randint(2, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self):
        if self.life > 0:
            pygame.draw.circle(
                screen,
                self.color,
                (int(self.x), int(self.y)),
                self.size
            )


class Player:
    def __init__(self):
        self.width = 70
        self.height = 25
        self.x = WIDTH // 2 - self.width // 2
        self.y = HEIGHT - 70
        self.speed = 8

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def move(self, keys):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= self.speed

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += self.speed

        self.x = max(0, min(WIDTH - self.width, self.x))

    def draw(self):
        pygame.draw.rect(screen, BLUE, self.rect, border_radius=12)

        pygame.draw.circle(
            screen,
            WHITE,
            (self.x + 15, self.y + 12),
            4
        )

        pygame.draw.circle(
            screen,
            WHITE,
            (self.x + self.width - 15, self.y + 12),
            4
        )


class FallingObject:
    def __init__(self, dangerous=False):
        self.dangerous = dangerous
        self.size = random.randint(18, 28)
        self.x = random.randint(0, WIDTH - self.size)
        self.y = -self.size
        self.speed = random.uniform(3, 6)

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.size, self.size)

    def update(self, difficulty):
        self.y += self.speed + difficulty

    def draw(self):
        color = RED if self.dangerous else YELLOW
        pygame.draw.circle(
            screen,
            color,
            (int(self.x + self.size // 2),
             int(self.y + self.size // 2)),
            self.size // 2
        )


def draw_background():
    screen.fill(BLACK)

    for y in range(0, HEIGHT, 40):
        alpha = y / HEIGHT
        color = (
            int(20 + alpha * 30),
            int(20 + alpha * 30),
            int(40 + alpha * 50)
        )

        pygame.draw.rect(
            screen,
            color,
            (0, y, WIDTH, 40)
        )

    for i in range(30):
        pygame.draw.circle(
            screen,
            WHITE,
            (
                (i * 137) % WIDTH,
                (i * 97) % HEIGHT
            ),
            1
        )


def reset_game():
    return {
        "player": Player(),
        "objects": [],
        "particles": [],
        "score": 0,
        "timer": 0,
        "game_over": False
    }


game = reset_game()

running = True

while running:
    clock.tick(60)

    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if game["game_over"] and event.key == pygame.K_r:
                game = reset_game()

    draw_background()

    if not game["game_over"]:
        game["player"].move(keys)

        game["timer"] += 1

        difficulty = game["score"] / 20

        spawn_rate = max(15, 45 - int(difficulty))

        if game["timer"] % spawn_rate == 0:
            dangerous = random.random() < 0.25
            game["objects"].append(FallingObject(dangerous))

        for obj in game["objects"][:]:
            obj.update(difficulty)

            if obj.rect.colliderect(game["player"].rect):
                if obj.dangerous:
                    for _ in range(40):
                        game["particles"].append(
                            Particle(
                                obj.x,
                                obj.y,
                                RED
                            )
                        )

                    game["game_over"] = True

                else:
                    game["score"] += 1

                    for _ in range(15):
                        game["particles"].append(
                            Particle(
                                obj.x,
                                obj.y,
                                YELLOW
                            )
                        )

                game["objects"].remove(obj)

            elif obj.y > HEIGHT:
                game["objects"].remove(obj)

        for particle in game["particles"][:]:
            particle.update()

            if particle.life <= 0:
                game["particles"].remove(particle)

    for obj in game["objects"]:
        obj.draw()

    game["player"].draw()

    for particle in game["particles"]:
        particle.draw()

    score_text = font_medium.render(
        f"Score: {game['score']}",
        True,
        WHITE
    )

    level_text = font_small.render(
        f"Difficulty: {1 + game['score'] // 10}",
        True,
        GRAY
    )

    screen.blit(score_text, (20, 20))
    screen.blit(level_text, (20, 60))

    instructions = font_small.render(
        "Move: A/D or Arrow Keys",
        True,
        GRAY
    )

    screen.blit(instructions, (WIDTH - 240, 25))

    if game["game_over"]:
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))

        game_over_text = font_large.render(
            "GAME OVER",
            True,
            RED
        )

        final_score = font_medium.render(
            f"Final Score: {game['score']}",
            True,
            WHITE
        )

        restart_text = font_small.render(
            "Press R to Restart",
            True,
            GREEN
        )

        screen.blit(
            game_over_text,
            game_over_text.get_rect(center=(WIDTH // 2, 240))
        )

        screen.blit(
            final_score,
            final_score.get_rect(center=(WIDTH // 2, 310))
        )

        screen.blit(
            restart_text,
            restart_text.get_rect(center=(WIDTH // 2, 360))
        )

    pygame.display.flip()

pygame.quit()