# Constants which define various game parameters. These are used by 
# many of the modules, and so I've placed them all here so they can
# be safely inherited with a bulk "from constants import * "

#============================================================= 
# To use special characters from ASCII Code Page 437 (the terminal 16x16 tileset) pass the decimal value 
# for each of these characters to libtcod.console_put_char_ex as char.
# https://en.wikipedia.org/wiki/Code_page_437
#============================================================= 

import libtcodpy as libtcod

#actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 60
# size of the playing area. This should be (window size) - (GUI size)
MAP_WIDTH = 80
MAP_HEIGHT = 43

# rooms are usually carved out below ground
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

# buildings are built on the surface
BUILDING_MAX_SIZE = 10
BUILDING_MIN_SIZE = 6
MAX_BUILDINGS = 10

#sizes and coords for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 17
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2  #this makes sure that the messages get placed next to the health bar
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH -2
MSG_HEIGHT = PANEL_HEIGHT -1
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30
INVENTORY_WIDTH = 50

# gameplay constants
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
HEAL_AMOUNT = 4
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

ASTRONAUTS_IN_LANDER = 9

LIMIT_FPS = 20  #20 frames-per-second maximum
PLAYER_SPEED = 1
DEFAULT_SPEED = 8
DEFAULT_ATTACK_SPEED = 20

# FOV algorithm
FOV_ALGO = 1 # 0 is default FOV algorithm in libtcod.map_compute_fov but number 1 works better
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

# The map details
color_wall = libtcod.dark_red
color_ground = libtcod.flame
color_building = libtcod.darker_red

# ASCII Code Page 437 characters:
GRAVEL = 176
BOULDER = 7
LEFT_DOOR = 29
RIGHT_DOOR = 29
TOP_DOOR = 18
BOTTOM_DOOR = 18

# Globals
game_msgs = []