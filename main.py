import sys
import os
import math
import pygame
from game import CONFIG, RhythmEngine, get_cached_sprite, load_bg_tile, draw_text_with_outline

def main():
    pygame.init()
    pygame.mixer.init()
    info = pygame.display.Info()
    SCR_W, SCR_H = info.current_w, info.current_h
    screen = pygame.display.set_mode((SCR_W, SCR_H), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Rhythm Engine Architecture")
    clock = pygame.time.Clock()

    engine = RhythmEngine(SCR_W, SCR_H)

    bg_base_tile, bg_tile_w = load_bg_tile("bg.png", SCR_H)
    bg_cols = math.ceil(SCR_W / bg_tile_w) + 2
    player_base_tile = get_cached_sprite("player.png", (engine.BLOCK_PX, engine.BLOCK_PX))
    ground_tile_w = engine.BLOCK_PX * CONFIG["GROUND_HEIGHT_MULTIPLIER"]
    ground_base_tile = get_cached_sprite("ground.png", (ground_tile_w, engine.GROUND_H))
    ground_cols = math.ceil(SCR_W / ground_tile_w) + 2

    bg_overlay = pygame.Surface((bg_tile_w, bg_base_tile.get_height())).convert()
    ground_overlay = pygame.Surface((ground_tile_w, engine.GROUND_H)).convert_alpha()

    font_path = os.path.join(CONFIG["SPRITES_DIR"], "mainfont.ttf")
    font = pygame.font.Font(font_path, 24) if os.path.exists(font_path) else pygame.font.SysFont("sans", 24, bold=True)
    menu_font = pygame.font.Font(font_path, 36) if os.path.exists(font_path) else pygame.font.SysFont("sans", 36, bold=True)

    show_hitboxes = game_paused = False
    in_menu = True
    menu_scroll_y = 0
    max_scroll_y = 0

    fade_state = "none"
    fade_timer = 0.0
    pending_level_idx = None

    dt = 1.0 / CONFIG["FPS"]
    running = True

    while running:
        mx, my = pygame.mouse.get_pos()
        
        cols = 3
        start_x, start_y = 50, 100
        gap_x, gap_y = 320, 180
        card_w, card_h = 280, 140
        
        total_rows = math.ceil(len(engine.levels_list) / cols)
        max_scroll_y = max(0, (start_y + total_rows * gap_y) - (SCR_H - 50))
        
        level_buttons = []
        for idx in range(len(engine.levels_list)):
            r = idx // cols
            c = idx % cols
            rx = start_x + c * gap_x
            ry = start_y + r * gap_y - menu_scroll_y
            card_rect = pygame.Rect(rx, ry, card_w, card_h)
            level_buttons.append((card_rect, idx))

        quit_btn_rect = pygame.Rect(SCR_W - 180, 20, 150, 45)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if in_menu and fade_state == "none":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:
                        menu_scroll_y = max(0, menu_scroll_y - 35)
                    elif event.button == 5:
                        menu_scroll_y = min(max_scroll_y, menu_scroll_y + 35)
                    elif event.button == 1:
                        if quit_btn_rect.collidepoint(mx, my):
                            running = False
                        for r, idx in level_buttons:
                            if r.collidepoint(mx, my):
                                pending_level_idx = idx
                                fade_state = "out"
                                fade_timer = 0.0

            elif not in_menu and fade_state == "none" and not engine.is_dead:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_paused = not game_paused
                        if game_paused and engine.music_loaded: pygame.mixer.music.pause()
                        elif not game_paused and engine.music_loaded:
                            pygame.mixer.music.unpause()
                            engine.ignore_mouse_click_frame = True
                    if event.key == pygame.K_h and not game_paused:
                        show_hitboxes = not show_hitboxes
                if game_paused and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_resume_rect.collidepoint(mx, my):
                        game_paused = False
                        if engine.music_loaded and engine.song_played_this_attempt: pygame.mixer.music.unpause()
                        engine.ignore_mouse_click_frame = True 
                    elif btn_restart_rect.collidepoint(mx, my):
                        engine.reset_game()
                        game_paused = False
                    elif btn_exit_rect.collidepoint(mx, my):
                        if engine.music_loaded: pygame.mixer.music.stop()
                        game_paused = False
                        in_menu = True

        if fade_state == "out":
            fade_timer += dt
            if fade_timer >= 0.5:
                fade_timer = 0.5
                fade_state = "in"
                engine.load_level_index(pending_level_idx)
                in_menu = False
        elif fade_state == "in":
            fade_timer -= dt
            if fade_timer <= 0.0:
                fade_timer = 0.0
                fade_state = "none"

        if not in_menu and not game_paused and fade_state == "none":
            engine.update(dt, ground_tile_w, bg_tile_w)

        if in_menu:
            screen.fill((20, 24, 35))
            draw_text_with_outline(screen, "SELECT LEVEL", menu_font, (255, 255, 255), (0, 0, 0), (50, 25))
            
            q_hover = quit_btn_rect.collidepoint(mx, my)
            pygame.draw.rect(screen, (180, 50, 50) if q_hover else (140, 40, 40), quit_btn_rect, 0, 6)
            draw_text_with_outline(screen, "QUIT", font, (255, 255, 255), (0, 0, 0), (quit_btn_rect.centerx - (font.size("QUIT")[0] // 2), quit_btn_rect.centery - (font.size("QUIT")[1] // 2)))

            for card_rect, idx in level_buttons:
                if card_rect.bottom < 0 or card_rect.top > SCR_H: continue
                
                lvl = engine.levels_list[idx]
                hover = card_rect.collidepoint(mx, my)
                pygame.draw.rect(screen, (40, 50, 70) if hover else (30, 38, 55), card_rect, 0, 10)
                pygame.draw.rect(screen, (0, 212, 255) if hover else (60, 75, 100), card_rect, 3, 10)
                
                draw_text_with_outline(screen, lvl.get("name", "Unknown"), font, (255, 255, 255), (0, 0, 0), (card_rect.x + 20, card_rect.y + 25))
                draw_text_with_outline(screen, f"Objects: {len(lvl.get('level', []))}", font, (150, 170, 190), (0, 0, 0), (card_rect.x + 20, card_rect.y + 75))

        else:
            screen.fill((30, 30, 40))
            bx = int(engine.bg_x) % bg_tile_w
            bg_draw_y = SCR_H - bg_base_tile.get_height()
            bg_overlay.fill(engine.current_bg)
            for c in range(bg_cols):
                dest_x = bx + (c - 1) * bg_tile_w
                screen.blit(bg_base_tile, (dest_x, bg_draw_y))
                screen.blit(bg_overlay, (dest_x, bg_draw_y), special_flags=pygame.BLEND_RGB_MULT)

            render_ground_top = int(engine.ground_top_absolute - engine.camera_y)
            gx = int(engine.ground_x) % ground_tile_w
            if gx > 0: gx -= ground_tile_w
            ground_overlay.fill(tuple(engine.current_ground) + (255,))
            for c in range(ground_cols):
                dest_x = gx + c * ground_tile_w
                screen.blit(ground_base_tile, (dest_x, render_ground_top))
                screen.blit(ground_overlay, (dest_x, render_ground_top), special_flags=pygame.BLEND_RGBA_MULT)

            for group in [engine.active_decos, engine.active_blocks, engine.active_hazards]:
                for item in group:
                    rendered_pos = (item["visual"].x, int(item["visual"].y - engine.camera_y))
                    sprite_tex = get_cached_sprite(item["meta"].get("sprite"), item["visual"].size, item["meta"].get("spritemethod", "stretch"))
                    
                    if item["meta"]["rotation"] != 0.0:
                        sprite_tex = pygame.transform.rotate(sprite_tex, -item["meta"]["rotation"])
                        new_rect = sprite_tex.get_rect(topleft=rendered_pos)
                        screen.blit(sprite_tex, new_rect.topleft)
                    else:
                        screen.blit(sprite_tex, rendered_pos)
                        
                    # UPDATED: Conditional check avoids drawing structural debugging boxes over purely decoration (deco) layer paths
                    if show_hitboxes and item["meta"]["type"] != "deco":
                        shifted_hb = item["hitbox"].copy()
                        shifted_hb.y -= int(engine.camera_y)
                        pygame.draw.rect(screen, (255, 0, 0) if item["meta"]["type"] == "hazard" else (0, 0, 255), shifted_hb, 2)

            if not engine.is_dead:
                rot_surf = pygame.transform.rotate(player_base_tile, engine.rotation)
                render_p_y = int(engine.player_y - engine.camera_y)
                rot_rect = rot_surf.get_rect(center=(int(engine.player_center_x), int(render_p_y + (engine.BLOCK_PX / 2))))
                screen.blit(rot_surf, rot_rect.topleft)
                
                if show_hitboxes:
                    # Outer box (Landed / Physics boundary Check)
                    shifted_player_outer_hb = pygame.Rect(engine.player_screen_x, int(engine.player_y), engine.BLOCK_PX, engine.BLOCK_PX)
                    shifted_player_outer_hb.y -= int(engine.camera_y)
                    pygame.draw.rect(screen, (255, 255, 255), shifted_player_outer_hb, 1)
                    
                    # UPDATED: Render the 0.3x inner hitbox on screen inside debugging mode
                    inner_w = int(engine.BLOCK_PX * 0.3)
                    inner_h = int(engine.BLOCK_PX * 0.3)
                    inner_offset_x = (engine.BLOCK_PX - inner_w) // 2
                    inner_offset_y = (engine.BLOCK_PX - inner_h) // 2
                    shifted_player_inner_hb = pygame.Rect(engine.player_screen_x + inner_offset_x, int(engine.player_y) + inner_offset_y, inner_w, inner_h)
                    shifted_player_inner_hb.y -= int(engine.camera_y)
                    pygame.draw.rect(screen, (255, 255, 0), shifted_player_inner_hb, 1)
            else:
                progress = max(0.0, min(1.0, (0.5 - engine.death_delay_timer) / 0.5))
                particle_alpha_val = int((1.0 - progress) * 255)
                
                for p in engine.death_particles:
                    p_radius = int(p["size"])
                    if p_radius > 0 and particle_alpha_val > 0:
                        p_surf = pygame.Surface((p_radius * 2, p_radius * 2), pygame.SRCALPHA)
                        pygame.draw.circle(p_surf, (255, 255, 255, particle_alpha_val), (p_radius, p_radius), p_radius, 0)
                        screen.blit(p_surf, (int(p["x"]) - p_radius, int(p["y"]) - p_radius))

            if game_paused:
                pause_surface = pygame.Surface((SCR_W, SCR_H), pygame.SRCALPHA)
                pause_surface.fill((15, 15, 20, 150)) 
                screen.blit(pause_surface, (0, 0))
                panel_rect = pygame.Rect((SCR_W - 400) // 2, (SCR_H - 380) // 2, 400, 380)
                pygame.draw.rect(screen, (45, 45, 55), panel_rect, 0, 12)
                pygame.draw.rect(screen, (80, 80, 95), panel_rect, 3, 12)
                
                lname = engine.active_level_data.get("name", "LEVEL")
                draw_text_with_outline(screen, lname, menu_font, (255, 255, 255), (0, 0, 0), (panel_rect.centerx - (menu_font.size(lname)[0] // 2), panel_rect.y + 30))
                
                btn_w, btn_h, btn_x = 280, 50, panel_rect.centerx - 140
                btn_resume_rect = pygame.Rect(btn_x, panel_rect.y + 110, btn_w, btn_h)
                btn_restart_rect = pygame.Rect(btn_x, panel_rect.y + 180, btn_w, btn_h)
                btn_exit_rect = pygame.Rect(btn_x, panel_rect.y + 250, btn_w, btn_h)

                for r, txt in [(btn_resume_rect, "RESUME"), (btn_restart_rect, "RESTART"), (btn_exit_rect, "EXIT LEVEL")]:
                    hover = r.collidepoint(mx, my)
                    pygame.draw.rect(screen, (70, 75, 90) if hover else (55, 58, 70), r, 0, 6)
                    pygame.draw.rect(screen, (120, 130, 150) if hover else (75, 80, 95), r, 2, 6)
                    
                    text_x = r.centerx - (font.size(txt)[0] // 2)
                    text_y = r.centery - (font.size(txt)[1] // 2)
                    draw_text_with_outline(screen, txt, font, (255, 255, 255) if hover else (210, 210, 210), (0, 0, 0), (text_x, text_y))

            draw_text_with_outline(screen, f"FPS: {int(clock.get_fps())}  [H] Hitboxes", font, (0, 255, 0), (0, 0, 0), (16, 16))

        if fade_state != "none":
            fade_surf = pygame.Surface((SCR_W, SCR_H))
            fade_surf.fill((0, 0, 0))
            fade_surf.set_alpha(int((fade_timer / 0.5) * 255))
            screen.blit(fade_surf, (0, 0))

        pygame.display.flip()
        dt = min(clock.tick_busy_loop(CONFIG["FPS"]) / 1000.0, 0.05)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()