import math
import os
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple

import pygame
from pygame import Vector2


WIDTH, HEIGHT = 900, 700
FPS = 60


class GameState(Enum):
    PLAYING = auto()
    WORLD_COMPLETE = auto()
    GAME_OVER = auto()


@dataclass
class WorldConfig:
    world_number: int
    player_speed: float
    starting_lives: int
    aura_gain_per_pickup: int
    enemy_spawn_rate: float
    aura_spawn_rate: float
    enemy_level_range: Tuple[int, int]
    boss_level: int
    aura_required_for_boss_spawn: int


WORLD_CONFIGS: List[WorldConfig] = [
    WorldConfig(1, 4.8, 6, 12, 0.012, 0.018, (1, 2), 4, 220),
    WorldConfig(2, 5.0, 6, 11, 0.014, 0.017, (1, 3), 5, 300),
    WorldConfig(3, 5.2, 5, 10, 0.016, 0.016, (2, 4), 6, 390),
    WorldConfig(4, 5.4, 5, 9, 0.018, 0.015, (3, 5), 7, 500),
    WorldConfig(5, 5.6, 4, 8, 0.020, 0.014, (4, 6), 8, 620),
    WorldConfig(6, 5.8, 4, 7, 0.022, 0.013, (5, 7), 9, 760),
    WorldConfig(7, 6.0, 3, 6, 0.026, 0.012, (6, 8), 10, 920),
]


class MusicManager:
    def __init__(self, playlist: List[str], switch_seconds: int = 300):
        self.playlist = playlist
        self.switch_ms = switch_seconds * 1000
        self.current_index = -1
        self.current_track_name = "No Track"
        self.next_switch_time = 0
        self.enabled = False
        self.sfx = {}

    def init_audio(self):
        try:
            pygame.mixer.init()
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def load_sfx(self):
        if not self.enabled:
            return
        for name, path in {"shoot": "shoot.wav", "explosion": "explosion.wav"}.items():
            if os.path.exists(path):
                try:
                    self.sfx[name] = pygame.mixer.Sound(path)
                except pygame.error:
                    pass

    def play_sfx(self, name: str):
        snd = self.sfx.get(name)
        if snd:
            snd.play()

    def _try_play_track(self, index: int) -> bool:
        if not self.enabled or not self.playlist:
            return False

        path = self.playlist[index % len(self.playlist)]
        if not os.path.exists(path):
            return False

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            self.current_index = index % len(self.playlist)
            self.current_track_name = os.path.basename(path)
            self.next_switch_time = pygame.time.get_ticks() + self.switch_ms
            return True
        except pygame.error:
            return False

    def start(self):
        if not self.enabled:
            return
        for idx in range(len(self.playlist)):
            if self._try_play_track(idx):
                return

    def update(self):
        if not self.enabled or self.current_index == -1:
            return
        now = pygame.time.get_ticks()
        if now >= self.next_switch_time:
            for step in range(1, len(self.playlist) + 1):
                if self._try_play_track(self.current_index + step):
                    return
            self.next_switch_time = now + self.switch_ms

    def time_to_switch(self) -> int:
        if not self.enabled or self.current_index == -1:
            return 0
        return max(0, (self.next_switch_time - pygame.time.get_ticks()) // 1000)


class Star:
    def __init__(self):
        self.pos = Vector2(random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        self.speed = random.uniform(0.4, 2.2)
        self.size = random.randint(1, 3)

    def update(self):
        self.pos.y += self.speed
        if self.pos.y > HEIGHT:
            self.pos.y = random.uniform(-20, 0)
            self.pos.x = random.uniform(0, WIDTH)

    def draw(self, surface: pygame.Surface, tint: Tuple[int, int, int]):
        color = (
            min(255, 140 + tint[0] // 2),
            min(255, 140 + tint[1] // 2),
            min(255, 140 + tint[2] // 2),
        )
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), self.size)


class AuraPickup:
    def __init__(self):
        self.pos = Vector2(random.uniform(24, WIDTH - 24), random.uniform(24, HEIGHT - 24))
        self.radius = 9
        self.pulse = random.random() * math.tau

    def update(self):
        self.pulse += 0.12

    def draw(self, surface: pygame.Surface):
        pulse_r = self.radius + math.sin(self.pulse) * 2.0
        pygame.draw.circle(surface, (90, 220, 255), (int(self.pos.x), int(self.pos.y)), int(pulse_r))
        pygame.draw.circle(surface, (170, 250, 255), (int(self.pos.x), int(self.pos.y)), int(pulse_r * 0.55))


class Bullet:
    def __init__(self, pos: Vector2, vel: Vector2, damage: int, color: Tuple[int, int, int], radius: int = 4):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = damage
        self.color = color
        self.radius = radius
        self.alive = True
        self.trail: List[Vector2] = []

    def update(self):
        self.trail.append(Vector2(self.pos))
        if len(self.trail) > 7:
            self.trail.pop(0)
        self.pos += self.vel
        if self.pos.x < -20 or self.pos.x > WIDTH + 20 or self.pos.y < -20 or self.pos.y > HEIGHT + 20:
            self.alive = False

    def draw(self, surface: pygame.Surface):
        for i, p in enumerate(self.trail):
            alpha = int(30 + i * 18)
            r = max(1, int(self.radius * (i + 1) / len(self.trail)))
            trail_surface = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(trail_surface, (*self.color, alpha), (r * 2, r * 2), r)
            surface.blit(trail_surface, (p.x - r * 2, p.y - r * 2))

        pygame.draw.circle(surface, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)


class Enemy:
    def __init__(self, level: int, pos: Vector2, boss: bool = False):
        self.level = level
        self.pos = Vector2(pos)
        self.boss = boss
        self.radius = 18 + level * 2 + (20 if boss else 0)
        self.hp = 10 + level * 6 + (80 if boss else 0)
        self.speed = 1.0 + level * 0.16 + (0.45 if boss else 0)
        self.shoot_cd = max(24, 120 - level * 6 - (30 if boss else 0))
        self.shoot_timer = random.randint(20, self.shoot_cd)
        self.glow_boost = 0
        self.wobble_seed = random.random() * math.tau

    def update(self, target: Vector2):
        to_player = target - self.pos
        if to_player.length_squared() > 0:
            dir_vec = to_player.normalize()
        else:
            dir_vec = Vector2(0, 1)

        perp = Vector2(-dir_vec.y, dir_vec.x)
        wobble = math.sin((pygame.time.get_ticks() / 220.0) + self.wobble_seed)
        velocity = dir_vec * self.speed + perp * wobble * 0.45
        self.pos += velocity
        self.pos.x = max(10, min(WIDTH - 10, self.pos.x))
        self.pos.y = max(10, min(HEIGHT - 10, self.pos.y))

        self.shoot_timer -= 1
        self.glow_boost = max(0, self.glow_boost - 1)

    def can_shoot(self) -> bool:
        return self.shoot_timer <= 0

    def reset_shoot(self):
        self.shoot_timer = self.shoot_cd
        self.glow_boost = 12

    def draw(self, surface: pygame.Surface):
        glow_r = int(self.radius + self.level * 2 + self.glow_boost)
        glow_alpha = 45 + self.level * 8 + self.glow_boost * 6
        glow_surface = pygame.Surface((glow_r * 2 + 8, glow_r * 2 + 8), pygame.SRCALPHA)
        glow_color = (255, 90, 90) if not self.boss else (255, 60, 180)
        pygame.draw.circle(glow_surface, (*glow_color, min(180, glow_alpha)), (glow_r + 4, glow_r + 4), glow_r)
        surface.blit(glow_surface, (self.pos.x - glow_r - 4, self.pos.y - glow_r - 4))

        body_color = (155, 80, 70) if not self.boss else (170, 70, 140)
        x, y = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(surface, (240, 220, 200), (x, y - self.radius // 2), self.radius // 3)
        pygame.draw.rect(surface, body_color, (x - self.radius // 3, y - self.radius // 8, self.radius * 2 // 3, self.radius))
        pygame.draw.rect(surface, (40, 40, 40), (x + self.radius // 3, y, self.radius // 2, self.radius // 5))


class Player:
    def __init__(self, config: WorldConfig):
        self.pos = Vector2(WIDTH // 2, HEIGHT - 80)
        self.speed = config.player_speed
        self.lives = config.starting_lives
        self.aura = 0
        self.radius = 18
        self.shoot_cooldown = 10
        self.shoot_timer = 0

    def weapon_level(self) -> str:
        if self.aura < 100:
            return "I"
        if self.aura < 250:
            return "II"
        if self.aura < 500:
            return "III"
        return "IV"

    def bullet_pattern(self) -> List[Vector2]:
        if self.aura < 100:
            return [Vector2(0, -9)]
        if self.aura < 250:
            return [Vector2(-1.3, -9), Vector2(1.3, -9)]
        if self.aura < 500:
            return [Vector2(-1.8, -9.4), Vector2(0, -9.6), Vector2(1.8, -9.4)]
        return [
            Vector2(-3.0, -11.0),
            Vector2(-1.4, -11.8),
            Vector2(0, -12.2),
            Vector2(1.4, -11.8),
            Vector2(3.0, -11.0),
        ]

    def update(self, keys):
        direction = Vector2(0, 0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1

        if direction.length_squared() > 0:
            direction = direction.normalize()

        self.pos += direction * self.speed
        self.pos.x = max(20, min(WIDTH - 20, self.pos.x))
        self.pos.y = max(20, min(HEIGHT - 20, self.pos.y))

        if self.shoot_timer > 0:
            self.shoot_timer -= 1

    def try_shoot(self) -> bool:
        return self.shoot_timer <= 0

    def reset_shoot(self):
        self.shoot_timer = self.shoot_cooldown

    def draw(self, surface: pygame.Surface):
        glow_strength = min(220, 60 + self.aura // 3)
        glow_radius = self.radius + 10 + min(26, self.aura // 35)
        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (90, 190, 255, glow_strength), (glow_radius, glow_radius), glow_radius)
        surface.blit(glow, (self.pos.x - glow_radius, self.pos.y - glow_radius))

        x, y = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(surface, (210, 250, 255), (x, y), self.radius)
        pygame.draw.polygon(surface, (80, 180, 255), [(x, y - 24), (x - 12, y + 18), (x + 12, y + 18)])


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Light War / מלחמת האורה")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 22)
        self.big_font = pygame.font.SysFont("consolas", 46, bold=True)

        self.music = MusicManager(["music1.mp3", "music2.mp3", "music3.mp3"], switch_seconds=300)
        self.music.init_audio()
        self.music.load_sfx()
        self.music.start()

        self.stars = [Star() for _ in range(120)]

        self.world_index = 0
        self.state = GameState.PLAYING
        self.state_timer = 0
        self.world = WORLD_CONFIGS[self.world_index]

        self.player = Player(self.world)
        self.enemies: List[Enemy] = []
        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []
        self.pickups: List[AuraPickup] = []

        self.boss_spawned = False
        self.boss_defeated = False

    def reset_world(self, keep_aura: bool = True):
        prev_aura = self.player.aura if keep_aura else 0
        self.world = WORLD_CONFIGS[self.world_index]
        self.player = Player(self.world)
        self.player.aura = prev_aura
        self.enemies.clear()
        self.player_bullets.clear()
        self.enemy_bullets.clear()
        self.pickups.clear()
        self.boss_spawned = False
        self.boss_defeated = False

    def spawn_enemy(self):
        edge = random.randint(0, 3)
        if edge == 0:
            pos = Vector2(random.uniform(0, WIDTH), -20)
        elif edge == 1:
            pos = Vector2(random.uniform(0, WIDTH), HEIGHT + 20)
        elif edge == 2:
            pos = Vector2(-20, random.uniform(0, HEIGHT))
        else:
            pos = Vector2(WIDTH + 20, random.uniform(0, HEIGHT))

        lvl = random.randint(*self.world.enemy_level_range)
        self.enemies.append(Enemy(lvl, pos))

    def spawn_boss(self):
        self.boss_spawned = True
        self.enemies.append(Enemy(self.world.boss_level, Vector2(WIDTH / 2, 80), boss=True))

    def handle_spawning(self):
        if len(self.pickups) < 8 and random.random() < self.world.aura_spawn_rate:
            self.pickups.append(AuraPickup())

        if not self.boss_spawned and self.player.aura >= self.world.aura_required_for_boss_spawn:
            self.spawn_boss()

        if not self.boss_spawned and random.random() < self.world.enemy_spawn_rate:
            self.spawn_enemy()

    def fire_player(self):
        for vel in self.player.bullet_pattern():
            offset = Vector2(vel.x * 2.2, -self.player.radius)
            self.player_bullets.append(Bullet(self.player.pos + offset, vel, damage=5, color=(150, 240, 255), radius=4))
        self.player.reset_shoot()
        self.music.play_sfx("shoot")

    def fire_enemy(self, enemy: Enemy):
        to_player = self.player.pos - enemy.pos
        if to_player.length_squared() == 0:
            to_player = Vector2(0, 1)
        direction = to_player.normalize()
        speed = 3.0 + enemy.level * 0.35 + (1.3 if enemy.boss else 0)
        self.enemy_bullets.append(Bullet(enemy.pos + direction * enemy.radius * 0.5, direction * speed, damage=1, color=(255, 130, 130), radius=5 if enemy.boss else 4))
        enemy.reset_shoot()

    def handle_collisions(self):
        # pickups
        for pickup in self.pickups[:]:
            if (pickup.pos - self.player.pos).length() <= pickup.radius + self.player.radius:
                self.player.aura += self.world.aura_gain_per_pickup
                self.pickups.remove(pickup)

        # player bullets hit enemies
        for bullet in self.player_bullets[:]:
            for enemy in self.enemies[:]:
                if (enemy.pos - bullet.pos).length() <= enemy.radius + bullet.radius:
                    enemy.hp -= bullet.damage
                    bullet.alive = False
                    if enemy.hp <= 0:
                        self.player.aura += 10 + enemy.level * 4 + (45 if enemy.boss else 0)
                        if enemy.boss:
                            self.boss_defeated = True
                        self.enemies.remove(enemy)
                        self.music.play_sfx("explosion")
                    break

        # enemy bullets hit player
        for bullet in self.enemy_bullets[:]:
            if (bullet.pos - self.player.pos).length() <= bullet.radius + self.player.radius:
                bullet.alive = False
                self.player.lives -= bullet.damage
                if self.player.lives <= 0:
                    self.state = GameState.GAME_OVER

    def update_playing(self):
        keys = pygame.key.get_pressed()
        self.player.update(keys)

        self.handle_spawning()

        if keys[pygame.K_SPACE] and self.player.try_shoot():
            self.fire_player()

        for star in self.stars:
            star.update()

        for pickup in self.pickups:
            pickup.update()

        for enemy in self.enemies:
            enemy.update(self.player.pos)
            if enemy.can_shoot():
                self.fire_enemy(enemy)

        for bullet in self.player_bullets:
            bullet.update()
        for bullet in self.enemy_bullets:
            bullet.update()

        self.player_bullets = [b for b in self.player_bullets if b.alive]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

        self.handle_collisions()

        if self.boss_spawned and self.boss_defeated and self.state == GameState.PLAYING:
            self.state = GameState.WORLD_COMPLETE
            self.state_timer = FPS * 2

    def update(self):
        self.music.update()

        if self.state == GameState.PLAYING:
            self.update_playing()
        elif self.state == GameState.WORLD_COMPLETE:
            for star in self.stars:
                star.update()
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.world_index += 1
                if self.world_index >= len(WORLD_CONFIGS):
                    self.state = GameState.GAME_OVER
                else:
                    self.state = GameState.PLAYING
                    self.reset_world(keep_aura=True)

    def draw_background(self):
        aura_factor = min(1.0, self.player.aura / 900.0)
        tint = (
            int(20 + 70 * aura_factor),
            int(10 + 50 * aura_factor),
            int(30 + 90 * aura_factor),
        )
        self.screen.fill((8 + tint[0] // 4, 8 + tint[1] // 4, 16 + tint[2] // 4))

        for star in self.stars:
            star.draw(self.screen, tint)

        tint_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        tint_surface.fill((*tint, 28))
        self.screen.blit(tint_surface, (0, 0))

    def draw_hud(self):
        track = self.music.current_track_name if self.music.enabled else "Audio Off"
        switch_s = self.music.time_to_switch()
        world_txt = self.font.render(f"World: {self.world.world_number}", True, (230, 240, 255))
        aura_txt = self.font.render(f"Aura: {self.player.aura}", True, (170, 240, 255))
        lives_txt = self.font.render(f"Lives: {self.player.lives}", True, (255, 200, 200))
        weapon_txt = self.font.render(f"Weapon Lv: {self.player.weapon_level()}", True, (255, 255, 140))
        track_txt = self.font.render(f"Track: {track} ({switch_s}s)", True, (220, 220, 220))

        self.screen.blit(world_txt, (16, 12))
        self.screen.blit(aura_txt, (16, 38))
        self.screen.blit(lives_txt, (16, 64))
        self.screen.blit(weapon_txt, (16, 90))
        self.screen.blit(track_txt, (16, 116))

        if not self.boss_spawned:
            req = self.world.aura_required_for_boss_spawn
            boss_txt = self.font.render(f"Boss spawn at Aura {req}", True, (255, 170, 255))
            self.screen.blit(boss_txt, (WIDTH - boss_txt.get_width() - 16, 12))
        else:
            boss_alive = any(e.boss for e in self.enemies)
            status = "ACTIVE" if boss_alive else "DEFEATED"
            boss_txt = self.font.render(f"Boss: {status}", True, (255, 150, 220))
            self.screen.blit(boss_txt, (WIDTH - boss_txt.get_width() - 16, 12))

    def draw_entities(self):
        for pickup in self.pickups:
            pickup.draw(self.screen)
        for bullet in self.player_bullets:
            bullet.draw(self.screen)
        for bullet in self.enemy_bullets:
            bullet.draw(self.screen)
        for enemy in self.enemies:
            enemy.draw(self.screen)
        self.player.draw(self.screen)

    def draw_overlays(self):
        if self.state == GameState.WORLD_COMPLETE:
            msg = self.big_font.render(f"World {self.world.world_number} Complete!", True, (220, 255, 220))
            sub = self.font.render("Preparing next world...", True, (220, 240, 255))
            self.screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 44))
            self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 18))

        if self.state == GameState.GAME_OVER:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 165))
            self.screen.blit(overlay, (0, 0))
            msg = "Victory! All worlds cleared." if self.world_index >= len(WORLD_CONFIGS) else "Game Over"
            title = self.big_font.render(msg, True, (255, 220, 220))
            info = self.font.render("Press R to restart or ESC to quit", True, (220, 220, 220))
            self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 48))
            self.screen.blit(info, (WIDTH // 2 - info.get_width() // 2, HEIGHT // 2 + 18))

    def draw(self):
        self.draw_background()
        self.draw_entities()
        self.draw_hud()
        self.draw_overlays()
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if self.state == GameState.GAME_OVER and event.key == pygame.K_r:
                        self.world_index = 0
                        self.state = GameState.PLAYING
                        self.reset_world(keep_aura=False)

            self.update()
            self.draw()

        pygame.quit()


if __name__ == "__main__":
    Game().run()
