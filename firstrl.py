import libtcodpy as libtcod
import math
import textwrap
#actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 52
MAP_WIDTH = 80
MAP_HEIGHT = 45

#sizes and coords for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH -2
MSG_HEIGHT = PANEL_HEIGHT -1
game_msgs = [] #create the list of game message tuples with their colors

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3

LIMIT_FPS = 20  #20 frames-per-second maximum

# FOV algorithm
FOV_ALGO = 1 # 0 is default FOV algorithm in libtcod.map_compute_fov
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
fov_recompute = True # boolean for letting us know when to recompute the map fov

# The map
color_dark_wall = libtcod.Color(0,0,100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50,50,150)
color_light_ground = libtcod.Color(200,180,50)
class Tile:
    # a tile in the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked #is it passable?
        self.explored = False
        # by default if it is blocked (not passable) it also blocks sight
        # I think this code could also be: "if block_sight:" and have "block_sight=False" above
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
        
# Drawable objects
class Object:
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.fighter = fighter
        if self.fighter: #if the fighter component was defined then let it know who owns it
            self.fighter.owner = self
        self.ai = ai
        if self.ai:
            self.ai.owner = self
        
    def move(self, dx, dy):
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy
            
    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
 
        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)
        
    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)        
        
    def draw(self):
        # set the color and then draw the object at its position
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
        
    def clear(self):
        # erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
        
    def send_to_back(self):
        #make this thing get drawn first, so that everything else appears above it if on the same tile
        #otherwise monster corpses get drawn on top of monsters sometimes
        global objects
        objects.remove(self)
        objects.insert(0, self)
        
class Fighter:
    #combat related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
        
    def take_damage(self, damage):
        if damage > 0:
            self.hp -= damage
            if self.hp <= 0: # if it died, do the appropriate thing according to its death_function
                function = self.death_function
                if function is not None:
                    function(self.owner)
            
    def attack(self, target):
        damage = self.power - target.fighter.defense
        if damage > 0:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' +str(damage)+ ' hit points.', libtcod.white)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.yellow)
#------------------------------------------------------------- 
# AI modules and death states
#------------------------------------------------------------- 
class BasicMonster:
    #AI module for a basic monster
    def take_turn(self):
        #the monster takes its turn. If you can see it it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            # move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            # if close enough, attack!
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)
            
def player_death(player):
    global game_state
    message('Game Over!', libtcod.red)
    game_state = 'dead'
    # transform player into a corpse:
    player.char = '%'
    player.color = libtcod.dark_red
    
def monster_death(monster):
    # transform into a corpse which doesn't block, can't move, and can't be attacked
    message(monster.name.capitalize() + ' dies!', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None # important to make sure they dont keep acting! Unless they're a ghost...
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    
    
#-------------------------------------------------------------        
class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h        
        
    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)        
        
    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)        
#-------------------------------------------------------------
def is_blocked(x,y):
    #first see if the map tile itself is blocking
    if map[x][y].blocked:
        return True
    #now check for any objects that are blocking
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
    
    return False
#-------------------------------------------------------------
def create_room(room):
    global map
    # make the tiles in a rectangle passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    global map
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def make_map():
    global map
    # fill map with blocked=True or blocked=False tiles
    # By using Python's range function this creates the list of tiles, even though its
    # just two for statements.
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT)]
            for x in range(MAP_WIDTH)]
    
    rooms = []
    num_rooms = 0
    
    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        new_room = Rect(x, y, w, h)
        #Check for intersections with previously existing rooms
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
        if not failed:
            # paint it to the map's tiles
            create_room(new_room)
            (new_x, new_y) = new_room.center()
            place_objects(new_room) #add some contents to this room
            
            if num_rooms == 0:
                #start the player in the center of the first room
                player.x = new_x
                player.y = new_y
            else:
                # all rooms after the first get connected with a tunnel
                (prev_x, prev_y) = rooms[num_rooms - 1].center()
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
 
            #finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1
#-------------------------------------------------------------    
def place_objects(room):
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        #choose a spot for the monster
        x = libtcod.random_get_int(0, room.x1, room.x2)
        y = libtcod.random_get_int(0, room.y1, room.y2)
        
        #Example for how to create a variety of objects:
#        #chances: 20% monster A, 40% monster B, 10% monster C, 30% monster D:
#        choice = libtcod.random_get_int(0, 0, 100)
#        if choice < 20:
#            #create monster A
#        elif choice < 20+40:
#            #create monster B
#        elif choice < 20+40+10:
#            #create monster C
#        else:
#            #create monster D        
        if not is_blocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80: #80% chance of an orc
                #Create an orc
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
            else:
                #Create a troll
                fighter_component = Fighter(hp=16, defense=1, power=4, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
            
            objects.append(monster)
#-------------------------------------------------------------
def message(new_msg, color=libtcod.white):      
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        game_msgs.append( (line, color) )
            
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #Render a bar. First calculate the width of the bar:
    bar_width = int(float(value) / maximum * total_width)
    
    #render background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
    #then render bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    #finally, some centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
        name + ': ' + str(value) + '/' + str(maximum))
        
def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    #go through all tiles and set background according to FOV
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            wall = map[x][y].block_sight
            if not visible:
                if map[x][y].explored:
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
            else:
                #visible things
                if wall:
                    libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                map[x][y].explored = True
    for object in objects:
        if object != player:
            object.draw()
    player.draw() #if we didn't draw this separately, corpses and items sometimes get drawn over the player
    
    # blit the contents of "con" to the root console to display them
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
    
    #prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1
        
    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        libtcod.light_red, libtcod.darker_red)
    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
    
#-------------------------------------------------------------        
def player_move_or_attack(dx, dy):
    global fov_recompute
    
    #the coordinates the player is moving to or attacking into
    x = player.x + dx
    y = player.y + dy
    
    #Is there an attackable object there?
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break #prevents attacking multiple overlapping things
            
    #attack if target found, otherwise move
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def get_names_under_mouse():
    global mouse
    
    #return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)    
    #create a list with the names of all objects under the mouse AND in FOV 
    names = [obj.name for obj in objects if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    names = ', '.join(names) #concatenates the names into a big string, separated by a comma
    return names.capitalize() 
    
def handle_keys():
    global fov_recompute
    global key

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  #exit game

    #movement keys
    if game_state == 'playing':
        if key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)
            
        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
             
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
             
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)
            
        else:
            return 'didnt_take_turn'
         
#############################################
# Initialization & Main Loop
#############################################
 
libtcod.console_set_custom_font('libtcod-1.5.1/data/fonts/arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
# off screen console "con"
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
# GUI panel console "panel"
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS)

#Creating the object representing the player:
fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death) #creating the fighter aspect of the player
player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
objects = [player]

make_map()

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

game_state = 'playing'
player_action = None
message('Welcome Player One! This is a test of a roguelike game engine in Python and Libtcod.', libtcod.red)

mouse = libtcod.Mouse()
key = libtcod.Key()
#-------------------------------------------------------------
# The Main Loop!
while not libtcod.console_is_window_closed():
    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
    render_all()
   
    libtcod.console_flush()
    
    for object in objects:
        object.clear()

    #handle keys and exit game if needed
    player_action = handle_keys()
    if player_action == 'exit':
        break
    if game_state == 'playing' and player_action != 'didnt_take_turn': #let monsters take their turn
        for object in objects:
            if object.ai:
                object.ai.take_turn()
                
                
#############################################
# To Do list:
# * Break out modules into their own files- objects, graphics, main program loop and globals
# * Set it outside on Martian soil- red colors, day/night cycle. Enlarge the play area.
# * Scientists, laborers, engineers, with specializations:
#   Botanist (farmer), Engineer (builder), Laborer (?? operators?). Use the object component method described in 
#   tutorial 6.
# * Test out AI by having characters randomly walk from one building to another to simulate
#   a schedule. Have them say where they are going if the player bumps in to them.
#############################################