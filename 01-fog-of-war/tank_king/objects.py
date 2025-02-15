"""
This file provides objects that can be used to make up
a basic playground for the challenges.

This code is provided so that you can focus on implementing
a fog of war, without needed
Feel free to modify everything in this file to your liking.
"""
import random
import time
from random import choice, gauss

import pygame

from wclib import SIZE
from .utils import clamp, from_polar, load_image, random_in_rect, distance

SCREEN = pygame.Rect(0, 0, *SIZE)


class Object:
    """The base class for all objects of the game."""

    def __init__(self, pos, sprite: pygame.Surface):
        self.pos = pygame.Vector2(pos)
        self.size = pygame.Vector2(sprite.get_size())
        self.sprite = sprite

    def __str__(self):
        return f"<{self.__class__.__name__}(pos={self.pos}, size={self.size})>"

    @property
    def rect(self):
        return pygame.Rect(self.pos, self.size)

    def draw(self, screen):
        screen.blit(self.sprite, self.pos)

    def logic(self, **kwargs):
        pass


class Object8Directional(Object):
    SCALE = 3
    SIZE = 16
    SHEET = "blue_ghost"

    ACCELERATION = 0.5
    DAMPING = 0.85

    # Asymptotic velocity will be solution of
    # x = x * DAMPING + ACCELERATION
    # That is,
    # x = ACCELERATION / (1 - DAMPING)

    def __init__(self, pos):
        self.velocity = pygame.Vector2()
        self.acceleration = pygame.Vector2()

        super().__init__(pos, self.get_image())

    def get_image(self):
        angle = self.velocity.as_polar()[1]
        idx = int((-angle + 90 + 45 / 2) % 360 / 360 * 8)
        sheet = load_image(self.SHEET, self.SCALE)
        unit = self.SIZE * self.SCALE
        return sheet.subsurface(idx * unit, 0, unit, unit)

    def logic(self, **kwargs):
        self.velocity *= self.DAMPING
        self.velocity += self.acceleration
        self.pos += self.velocity
        self.sprite = self.get_image()

        self.pos.x = clamp(self.pos.x, 0, SIZE[0])
        self.pos.y = clamp(self.pos.y, 0, SIZE[1])


class Player(Object8Directional):
    def logic(self, **kwargs):
        pressed = pygame.key.get_pressed()
        direction_x = pressed[pygame.K_RIGHT] - pressed[pygame.K_LEFT]
        direction_y = pressed[pygame.K_DOWN] - pressed[pygame.K_UP]

        self.acceleration = pygame.Vector2(direction_x, direction_y) * self.ACCELERATION
        super().logic(**kwargs)


class Ghost(Object8Directional):
    SHEET = "pink_ghost"
    ACCELERATION = 0.2
    DAMPING = 0.9

    def __init__(self, pos=None):
        if pos is None:
            pos = random_in_rect(SCREEN)
        super().__init__(pos)
        self.goal = self.new_goal()

    def new_goal(self):
        direction = from_polar(60, gauss(self.velocity.as_polar()[1], 30))
        return self.rect.center + direction

    def logic(self, **kwargs):
        middle_area = SCREEN.inflate(-30, -30)
        while self.rect.collidepoint(self.goal) or not middle_area.collidepoint(
                self.goal
        ):
            self.goal = self.new_goal()

        self.acceleration = (
                                    self.goal - self.rect.center
                            ).normalize() * self.ACCELERATION
        super().logic(**kwargs)


class SolidObject(Object):
    SHEET_RECT = [
        (0, 0, 24, 31),
        (24, 0, 24, 24),
        (48, 0, 24, 24),
        (72, 0, 16, 24),
        (88, 0, 48, 43),
        (136, 0, 16, 16),
    ]
    SCALE = 3

    def __init__(self, pos):
        sheet = load_image("tileset", self.SCALE)
        sheet.set_colorkey(0xFFFFFF)
        rect = choice(self.SHEET_RECT)
        rect = [x * self.SCALE for x in rect]
        super().__init__(pos, sheet.subsurface(rect))

    @classmethod
    def generate_many(cls, nb=16, max_tries=1000):
        objects = []
        tries = 0  # avoids infinite loop
        while len(objects) < nb and tries < max_tries:
            pos = random_in_rect(SCREEN)
            obj = cls(pos)
            if not any(obj.rect.colliderect(other.rect) for other in objects):
                objects.append(obj)
        return objects


class LightGlow:
    def __init__(self, radius=125):
        self.radius = radius
        self.surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        # self.surf.fill((255, 255, 255))

        # pygame.draw.circle(self.surf, (255, 255, 255), self.surf.get_rect().center, self.surf.get_width() // 2)
        layers = 25
        self.glow = 11
        for i in range(layers):
            # k = 255 - 255 // (i + 1) + 50
            k = i * self.glow
            k = clamp(k, 0, 255)
            pygame.draw.circle(self.surf, (k, k, k), self.surf.get_rect().center, radius - i * 5)
        self.update_glow()
        self.blink_timer = time.time()
        self.is_blinking = False
        self.blink_k = 1

    def blink(self):
        self.blink_timer = time.time()
        self.is_blinking = True

    def update_glow(self):
        self.glow += 1
        self.surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        layers = 25
        self.glow = clamp(self.glow, 0, 255)
        for i in range(layers):
            k = i * self.glow
            k = clamp(k, 0, 255)
            pygame.draw.circle(self.surf, (k, k, k), self.surf.get_rect().center, self.radius - i * 3)


class DarkOverlay:
    def __init__(self):
        self.surf = pygame.Surface(SCREEN.size)
        self.light = LightGlow()
        self.cell_size = 16 * 2
        self.grid = [[0 * random.random() for _ in range(SCREEN.w // self.cell_size)] for _ in range(SCREEN.h // self.cell_size)]

    def draw(self, surf: pygame.Surface, pos):
        # self.light.update_glow()
        size = self.cell_size
        for row in range(len(self.grid)):
            for col in range(len(self.grid[row])):
                k = self.grid[row][col]
                if k > 0:
                    k -= 0.1
                    self.grid[row][col] = clamp(k, 25, 255)
                k = int(self.grid[row][col])
                center = (col * size + size // 2, row * size + size // 2)
                if distance(center, pos) < self.light.radius:
                    color = 55
                    self.grid[row][col] = color
                    k = color
                    k -= (11 - self.light.glow) * 2
                k = clamp(k, 0, 255)
                pygame.draw.rect(self.surf, (k, k, k), (col * size, row * size, size, size))
        self.surf.blit(self.light.surf, self.light.surf.get_rect(center=pos), special_flags=pygame.BLEND_RGBA_MAX)
        surf.blit(self.surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
