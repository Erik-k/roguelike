# -*- coding: utf-8 -*-
import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

# set font
libtcod.console_set_custom_font("libtcod-1.5.1/data/fonts/arial10x10.png", libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
# set window
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
# for real time game, limit FPS. For turn based this doesn't matter
libtcod.sys_set_fps(LIMIT_FPS)

#main loop
while not libtcod.console_is_window_closed():
    libtcod.console_set_default_foreground(0, libtcod.white)
    libtcod.console_put_char(0, 1, 1, '@', libtcod.BKGND_NONE)
    libtcod.console_flush()
    