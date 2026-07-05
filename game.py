import os
import math
import json
import random
import pygame

CONFIG = {
    "FPS": 60,
    "SPRITES_DIR": os.path.join(os.path.dirname(__file__), "sprites"),
    "SONGS_DIR": os.path.join(os.path.dirname(__file__), "songs"),
    "SFX_DIR": os.path.join(os.path.dirname(__file__), "sfx"),
    "SCREEN_SCALE_DIVISOR": 10,
    "BG_SCALE": 2,
    "BG_PARALLAX": 0.1,
    "PLAYER_X_FRAC": 0.30,
    "GROUND_HEIGHT_MULTIPLIER": 3,
    "H_SPEED_MULT": 10.386, 
    "GRAVITY_MULT": 79.0,
    "JUMP_V0_MULT": 18.3592,
    "TERM_VEL_MULT": 30.1194,
    "SNAP_SPEED": 500.0
}

SPRITE_CACHE = {}

def get_cached_sprite(filename, target_size, method="stretch"):
    if not filename:
        surf = pygame.Surface(target_size, pygame.SRCALPHA)
        surf.fill((255, 255, 255, 100))
        return surf
        
    composite_key = (filename, target_size[0], target_size[1], method)
    if composite_key in SPRITE_CACHE:
        return SPRITE_CACHE[composite_key]
        
    path = os.path.join(CONFIG["SPRITES_DIR"], filename)
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert_alpha()
            sw, sh = img.get_size()
            tw, th = target_size
            
            if method == "fit":
                src_ratio, tgt_ratio = sw / sh, tw / th
                new_w, new_h = (tw, int(tw / src_ratio)) if src_ratio > tgt_ratio else (int(th * src_ratio), th)
                scaled_sub = pygame.transform.smoothscale(img, (new_w, new_h))
                surf = pygame.Surface(target_size, pygame.SRCALPHA)
                surf.blit(scaled_sub, ((tw - new_w) // 2, th - new_h))
            else:
                surf = pygame.transform.smoothscale(img, target_size)
            SPRITE_CACHE[composite_key] = surf
            return surf
        except Exception as e:
            print(f"Error loading sprite {filename}: {e}")
            
    surf = pygame.Surface(target_size, pygame.SRCALPHA)
    surf.fill((255, 0, 255))
    SPRITE_CACHE[composite_key] = surf
    return surf

def load_bg_tile(filename, scr_h):
    path = os.path.join(CONFIG["SPRITES_DIR"], filename)
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert()
            scale = (scr_h / img.get_size()[1]) * CONFIG["BG_SCALE"]
            tile_w = int(img.get_size()[0] * scale)
            return pygame.transform.smoothscale(img, (tile_w, int(img.get_size()[1] * scale))), tile_w
        except Exception: pass
    return pygame.Surface((scr_h, scr_h)), scr_h

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def draw_text_with_outline(surface, text, font, text_color, outline_color, pos):
    x, y = pos
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
        surface.blit(font.render(text, True, outline_color), (x + dx, y + dy))
    surface.blit(font.render(text, True, text_color), (x, y))

def load_all_levels():
    if os.path.exists("levels.json"):
        with open("levels.json", "r") as f:
            return json.load(f).get("levels", [])
    return []

def process_level_data(level_raw_dict):
    registry = {}
    if os.path.exists("objects.json"):
        with open("objects.json", "r") as f:
            registry = json.load(f)
            
    processed_objects = []
    for item in level_raw_dict.get("level", []):
        obj_id = item.get("id")
        if obj_id in registry:
            combined = {**registry[obj_id], **item}
            combined["rotation"] = float(item.get("rotation", 0.0))
            processed_objects.append(combined)
    return processed_objects

class RhythmEngine:
    def __init__(self, scr_w, scr_h):
        self.SCR_W, self.SCR_H = scr_w, scr_h
        self.BLOCK_PX = scr_h // CONFIG["SCREEN_SCALE_DIVISOR"]
        self.GRAVITY = CONFIG["GRAVITY_MULT"] * self.BLOCK_PX
        self.JUMP_V0 = CONFIG["JUMP_V0_MULT"] * self.BLOCK_PX
        self.TERM_VEL = CONFIG["TERM_VEL_MULT"] * self.BLOCK_PX
        self.GROUND_H = self.BLOCK_PX * CONFIG["GROUND_HEIGHT_MULTIPLIER"]
        self.ROT_RATE = 180.0 / (2 * (self.JUMP_V0 / self.GRAVITY))
        self.ground_top_absolute = scr_h - self.GROUND_H
        self.player_screen_x = int(scr_w * CONFIG["PLAYER_X_FRAC"])
        self.player_center_x = self.player_screen_x + (self.BLOCK_PX / 2)
        self.levels_list = load_all_levels()
        self.current_level_idx = self.active_level_data = None
        self.all_objects = self.active_blocks = self.active_hazards = self.active_decos = []
        self.music_loaded = self.song_played_this_attempt = False
        self.song_offset = 0.0
        self.DEFAULT_BG_COLOR, self.DEFAULT_GROUND_COLOR = (125, 157, 156), (87, 111, 114)
        self.current_bg, self.current_ground = list(self.DEFAULT_BG_COLOR), list(self.DEFAULT_GROUND_COLOR)
        self.fade_bg_target = self.fade_bg_start = self.fade_g_target = self.fade_g_start = None
        self.fade_bg_duration = self.fade_bg_elapsed = self.fade_g_duration = self.fade_g_elapsed = 0.0
        self.triggers = []
        self.ignore_mouse_click_frame = False
        self.player_y = self.vel_y = self.rotation = self.target_rotation = self.camera_grid_x = self.ground_x = self.bg_x = self.camera_y = self.target_camera_y = 0.0
        self.on_ground = True
        self.is_snapping = self.is_dead = False
        self.death_delay_timer = 0.0
        self.death_particles = []
        self.death_sound = None
        death_sound_path = os.path.join(CONFIG["SFX_DIR"], "death.mp3")
        if os.path.exists(death_sound_path):
            try: self.death_sound = pygame.mixer.Sound(death_sound_path)
            except Exception as e: print(f"Error loading death sound: {e}")

    def load_level_index(self, idx):
        self.current_level_idx = idx
        self.active_level_data = self.levels_list[idx]
        self.all_objects = process_level_data(self.active_level_data)
        self.DEFAULT_BG_COLOR = hex_to_rgb(self.active_level_data.get("bg_color", "#7D9D9C"))
        self.DEFAULT_GROUND_COLOR = hex_to_rgb(self.active_level_data.get("ground_color", "#576F72"))
        self.music_loaded = False
        song_filename = self.active_level_data.get("song", "")
        self.song_offset = float(self.active_level_data.get("songoffset", 0.0))
        if song_filename:
            song_path = os.path.join(CONFIG["SONGS_DIR"], song_filename)
            if os.path.exists(song_path):
                try:
                    pygame.mixer.music.load(song_path)
                    self.music_loaded = True
                except Exception: pass
        self.reset_game()

    def handle_death(self):
        if self.is_dead: return
        self.is_dead, self.death_delay_timer, self.death_particles = True, 0.5, []
        px = self.player_screen_x + (self.BLOCK_PX // 2)
        py = int(self.player_y - self.camera_y) + (self.BLOCK_PX // 2)
        
        for _ in range(30):
            angle, speed = random.uniform(0, 2 * math.pi), random.uniform(200.0, 500.0)
            self.death_particles.append({
                "x": float(px), "y": float(py),
                "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                "size": random.uniform(4.0, 8.0)
            })
        if self.music_loaded: pygame.mixer.music.stop()
        if self.death_sound: self.death_sound.play()

    def reset_game(self):
        self.player_y = float(self.ground_top_absolute - self.BLOCK_PX)
        self.vel_y = self.rotation = self.target_rotation = self.camera_grid_x = self.ground_x = self.bg_x = self.camera_y = self.target_camera_y = 0.0
        self.on_ground, self.ignore_mouse_click_frame = True, True
        self.is_snapping = self.is_dead = False
        self.death_delay_timer = 0.0
        self.song_played_this_attempt = False
        self.current_bg, self.current_ground = list(self.DEFAULT_BG_COLOR), list(self.DEFAULT_GROUND_COLOR)
        self.fade_bg_target = self.fade_g_target = None
        self.triggers = sorted([obj for obj in self.all_objects if obj.get("type") == "trigger"], key=lambda x: x["grid_x"])

    def update(self, dt, ground_tile_w, bg_tile_w):
        if self.is_dead:
            self.death_delay_timer -= dt
            for p in self.death_particles:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
            if self.death_delay_timer <= 0.0: self.reset_game()
            return

        self.camera_grid_x += CONFIG["H_SPEED_MULT"] * dt
        if self.music_loaded and not self.song_played_this_attempt and self.camera_grid_x > 0.0:
            pygame.mixer.music.play(start=self.song_offset)
            self.song_played_this_attempt = True

        keys = pygame.key.get_pressed()
        mouse_pressed = pygame.mouse.get_pressed()[0]
        if not mouse_pressed: self.ignore_mouse_click_frame = False

        if self.on_ground and (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP] or (mouse_pressed and not self.ignore_mouse_click_frame)):
            self.vel_y = -self.JUMP_V0
            self.on_ground = self.is_snapping = False

        if not self.on_ground:
            self.vel_y = min(self.vel_y + self.GRAVITY * dt, self.TERM_VEL)
            self.player_y += self.vel_y * dt
            self.rotation -= self.ROT_RATE * dt
        elif self.is_snapping:
            step = CONFIG["SNAP_SPEED"] * dt
            if self.rotation > self.target_rotation:
                self.rotation = max(self.rotation - step, self.target_rotation)
            elif self.rotation < self.target_rotation:
                self.rotation = min(self.rotation + step, self.target_rotation)
            if self.rotation == self.target_rotation: self.is_snapping = False

        self.ground_x = (self.ground_x - (CONFIG["H_SPEED_MULT"] * self.BLOCK_PX) * dt) % -ground_tile_w
        self.bg_x = (self.bg_x - (CONFIG["H_SPEED_MULT"] * self.BLOCK_PX) * dt * CONFIG["BG_PARALLAX"]) % -bg_tile_w

        while self.triggers and self.camera_grid_x >= self.triggers[0]["grid_x"]:
            t = self.triggers.pop(0)
            duration, rgb = max(t.get("fade_time", 0.1), 0.001), hex_to_rgb(t.get("hex_color", "#FFFFFF"))
            if t.get("trigger_target", "bg") == "bg":
                self.fade_bg_start, self.fade_bg_target, self.fade_bg_duration, self.fade_bg_elapsed = tuple(self.current_bg), rgb, duration, 0.0
            else:
                self.fade_g_start, self.fade_g_target, self.fade_g_duration, self.fade_g_elapsed = tuple(self.current_ground), rgb, duration, 0.0

        if self.fade_bg_target:
            self.fade_bg_elapsed += dt
            self.current_bg = list(lerp_color(self.fade_bg_start, self.fade_bg_target, min(self.fade_bg_elapsed / self.fade_bg_duration, 1.0)))
            if self.fade_bg_elapsed >= self.fade_bg_duration: self.fade_bg_target = None
        if self.fade_g_target:
            self.fade_g_elapsed += dt
            self.current_ground = list(lerp_color(self.fade_g_start, self.fade_g_target, min(self.fade_g_elapsed / self.fade_g_duration, 1.0)))
            if self.fade_g_elapsed >= self.fade_g_duration: self.fade_g_target = None

        player_outer_hb = pygame.Rect(self.player_screen_x, int(self.player_y), self.BLOCK_PX, self.BLOCK_PX)
        inner_w = inner_h = int(self.BLOCK_PX * 0.3)
        inner_offset = (self.BLOCK_PX - inner_w) // 2
        player_inner_hb = pygame.Rect(self.player_screen_x + inner_offset, int(self.player_y) + inner_offset, inner_w, inner_h)
        
        self.active_blocks, self.active_hazards, self.active_decos = [], [], []

        for obj in self.all_objects:
            otype = obj.get("type")
            if otype not in ["block", "hazard", "deco"]: continue
            
            obj_w_px = int(obj.get("w", 1.0) * self.BLOCK_PX)
            obj_h_px = int(obj.get("h", 1.0) * self.BLOCK_PX)
            screen_x = int(((obj["grid_x"] - self.camera_grid_x) * self.BLOCK_PX) + self.player_screen_x) - (obj_w_px // 2)
            if screen_x < -obj_w_px or screen_x > self.SCR_W: continue

            screen_y = int(self.ground_top_absolute - ((obj.get("grid_y", 0.0) + obj.get("h", 1.0)) * self.BLOCK_PX))
            visual_rect = pygame.Rect(screen_x, screen_y, obj_w_px, obj_h_px)
            hb_w_units, hb_h_units = obj.get("hitbox_w"), obj.get("hitbox_h")
            
            if hb_w_units is not None and hb_h_units is not None:
                hb_w_px, hb_h_px = int(hb_w_units * self.BLOCK_PX), int(hb_h_units * self.BLOCK_PX)
                hb_x = (screen_x + (obj_w_px // 2) + int(obj.get("hitbox_offset_x", 0.0) * self.BLOCK_PX)) - (hb_w_px // 2)
                hb_y = (screen_y + (obj_h_px // 2) - int(obj.get("hitbox_offset_y", 0.0) * self.BLOCK_PX)) - (hb_h_px // 2)
                hitbox_rect = pygame.Rect(hb_x, hb_y, hb_w_px, hb_h_px)
            else:
                hitbox_rect = visual_rect.copy()

            pack = {"meta": obj, "visual": visual_rect, "hitbox": hitbox_rect}
            if otype == "block": self.active_blocks.append(pack)
            elif otype == "hazard": self.active_hazards.append(pack)
            elif otype == "deco": self.active_decos.append(pack)

        for item in self.active_blocks:
            if player_inner_hb.colliderect(item["hitbox"]) and player_inner_hb.bottom > item["hitbox"].top + 1.5:
                self.vel_y = 0.0
                self.handle_death()
                return

        landed_on_something = False
        if player_outer_hb.bottom >= self.ground_top_absolute:
            self.player_y, self.vel_y, landed_on_something = float(self.ground_top_absolute - self.BLOCK_PX), 0.0, True
            if not self.on_ground:
                self.on_ground, self.target_rotation, self.is_snapping = True, round(self.rotation / 90.0) * 90.0, True

        for item in self.active_blocks:
            b_rect = item["hitbox"]
            if b_rect.left < player_outer_hb.right and b_rect.right > player_outer_hb.left:
                if (player_outer_hb.bottom + max(0.0, self.vel_y * dt) >= b_rect.top) and (player_outer_hb.top < b_rect.top):
                    self.player_y, self.vel_y, landed_on_something = float(b_rect.top - self.BLOCK_PX), 0.0, True
                    if not self.on_ground:
                        self.on_ground, self.target_rotation, self.is_snapping = True, round(self.rotation / 90.0) * 90.0, True
                    break

        self.on_ground = landed_on_something
        self.target_camera_y = self.camera_y = 0.0
        player_outer_hb.y = int(self.player_y)

        for item in self.active_hazards:
            if player_outer_hb.colliderect(item["hitbox"]):
                self.handle_death()
                return