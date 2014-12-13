import libtcodpy as libtcod
import math
import textwrap
import shelve

#actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 52
MAP_WIDTH = 80
MAP_HEIGHT = 45
INVENTORY_WIDTH = 50

#sizes and coords for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH -2
MSG_HEIGHT = PANEL_HEIGHT -1

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

HEAL_AMOUNT = 4
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

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
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, item=None):
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
        self.item = item # I don't understand how this works! How can items be both an Item class and Object class/object?
        if self.item:
            self.item.owner = self
        
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
        #return the distance to another object from this object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)        
        
    def distance(self, x, y):
        #returns the distance between an object and a tile
        return math.sqrt( (x - self.x)**2 + (y - self.y)**2 )
        
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
            
    def heal(self, amount):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class Item:
    def __init__(self, use_function=None):
        self.use_function = use_function
    #a generic method calls the item's use_function:
    def use(self):
        #call the use_function if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            # This call to use_function includes the () because this is when it actually gets called. 
            # Above, where it doesn't have the (), it doesn't actually get called.
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) #destroy after use unless the use was aborted
                
    def pick_up(self):
        #it needs to be added to the player's inventory and removed from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)
            
    def drop(self):
        #add to the map and remove from the player's inventory. Place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
            
def target_tile(max_range=None):
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    global key, mouse
    while True:
        # render the screen, which erases the inventory screen and shows the names of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()
        
        (x, y) = (mouse.cx, mouse.cy)
        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and 
            (max_range is None or player.distance(x, y) <= max_range) ):
            return (x, y)
        # Give the player ways to cancel, if they right click or press escape:
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) # have to return a tuple with 2 output args
            
def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-click to cancel
    while True:
        (x, y) = target_tile(max_range)
        if x is None: #player canceled
            return None
            
        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj
            
def cast_heal():
    # This method becomes the use_function property in the relevant Item object. So when Item.use_function() gets called, it calls
    # this method, if the item had this passed as the parameter for use_function upon creation.
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
        
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find the closest enemy inside a max range and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.', libtcod.azure)
        return 'cancelled'
        
    message('A lightning bolt strikes the ' + monster.name + ' with a loud thunderclap! The damage is '
        + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def closest_monster(max_range):
    closest_enemy = None
    closest_dist = max_range + 1
    
    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def cast_confuse():
    #ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_green)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
    
    #replace the monster's AI with the confused AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster #you need to tell the new component who owns it every time you replace a component during runtime
    message('The ' + monster.name + ' starts to stumble around!', libtcod.light_green)
    
def cast_fireball():
    #ask the player for a target tile at which to throw a fireball:
    message('Left-click a tile for the fireball or right-click to cancel.', libtcod.light_red)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
    
    for obj in objects: 
        # damage every fighter within range, including the player. To avoid damaging the player, add " and obj != player"
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

#============================================================= 
# AI modules and death states
#============================================================= 

#for most types of AI that have different states, you can simply have a "state" property in the AI component, 
#like this: 
#class MultiStateAI:
#    def __init__(self):
#        self.state = 'chasing'
#    def take_turn(self):
#        if self.state == 'chasing': ...
#        elif self.state == 'running away': ...
# This is preferable to swapping AI components like a state machine which can get overly complicated.

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
            
class ConfusedMonster:
    #AI for a confused monster. Must take previous AI as argument so it can revert to it after a while
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))            
            self.num_turns -= 1
        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)            
            
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
    global map, objects
    
    objects = [player]    
    
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
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        
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
            
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)
    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 70:
                #creating a healing potion:
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
            elif dice < 70+10: 
                # chance of lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '?', 'lightning scroll', libtcod.light_azure, item=item_component)
            elif dice < 70+10+10:
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '*', 'fireball scroll', libtcod.orange, item=item_component)
            else: 
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)
                
            objects.append(item)
            item.send_to_back() #make items appear below other objects
#-------------------------------------------------------------
def message(new_msg, color=libtcod.white):      
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        game_msgs.append( (line, color) )
            
def menu(header, options, width):
    #header is title at top of window. Options is list of strings. Height is implied by options length
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    #calculate total height for the header after auto-wrap, and then one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0 #otherwise there is a blank line on top of the menu if there's no header
    height = len(options) + header_height
    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)
    #print the header with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
    
    #print all the options
    y = header_height
    #ord() and chr() work together to convert between letters and ASCII codes
    letter_index = ord('a') 
    for option_text in options: 
        text = '(' +chr(letter_index) + ') ' + option_text 
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1
        
    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
    
    #present the rot console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    #convert the ASCII code to an index. If it corresponds to an option, return the index.
    index = key.c - ord('a') # key.c is the ASCII code of the character that was pressed
    if index >= 0 and index < len(options): return index
    return None
    
def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty']
    else:
        options = [item.name for item in inventory]
    
    index = menu(header, options, INVENTORY_WIDTH)
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None 
    return inventory[index].item
            
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
    
#==============================================================================
# Keyboard and Mouse management        
#==============================================================================
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
            #test for other keys
            key_char = chr(key.c)
            if key_char == 'g':
                #pick up an item
                for object in objects: #Is there an item in the player's tile?
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            
            if key_char == 'i':
                #show the inventory. If an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other key to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
                    
            if key_char == 'd':
                #show the inventory and drop the selected item
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other key to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
                    
            return 'didnt_take_turn'
         
#############################################
# Initialization & Main Loop
#############################################
 
libtcod.console_set_custom_font('libtcod-1.5.1/data/fonts/arial12x12.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
# off screen console "con"
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
# GUI panel console "panel"
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS)

def new_game():
    global player, inventory, game_msgs, game_state
    
    #Creating the object representing the player:
    fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death) #creating the fighter aspect of the player
    player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)

    #generate map, but at this point its not drawn to the screen    
    make_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []    
    
    #create the list of game messages and their colors.
    game_msgs = []    

    message('Welcome Player One! This is a test of a roguelike game engine in Python and Libtcod.', libtcod.red)

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
    
    #create the FOV map according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
            
    libtcod.console_clear(con)

def play_game():
    global key, mouse
    
    player_action = None
    
    mouse = libtcod.Mouse()
    key = libtcod.Key()
    while not libtcod.console_is_window_closed():
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
        render_all() #render the screen
       
        libtcod.console_flush()
        
        #erase all objects at their old locations, before they move
        for object in objects:
            object.clear()
    
        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break
        
        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt_take_turn': #let monsters take their turn
            for object in objects:
                if object.ai:
                    object.ai.take_turn()
                    
def msgbox(text, width=50):
    menu(text, [], width) #use our menu() function as a sort of "message box"

def main_menu():
    img = libtcod.image_load('menu_background1.png')
    
    while not libtcod.console_is_window_closed():
        #show the background image at 2x the normal resolution using special font characters to do sub-cell shading:
        libtcod.image_blit_2x(img, 0, 0, 0)
        
        #show the game's title and opening credits
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 
                                 'MARXIST MARTIANS!')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 
                                 'By K\'NEK-TEK')
        
        #show options and wait for the player's choice
        choice = menu('', ['New Game', 'Continue', 'Quit'], 24)
        if choice == 0: #new game
            new_game()
            play_game()
        elif choice == 1: #load game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2: #quit
            break

def save_game():
    #opens a new empty shelve, possibly overwriting an old one, to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player) 
    # This stuff with player_index prevents double-referencing the player object. We only save the index of
    # the player object in the list of the objects, we never save the player object specifically. To restore it in 
    # load_game(), we take the index and place object[player_index] into the player object.
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file.close()
    
def load_game():
    global map, objects, player, inventory, game_msgs, game_state
    
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']] #all we stored previously was the player index. The player itself was stored in objects[].
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    file.close()
    
    # Now that the core variables of the game have been restored, we can initialize the FOV map based on the loaded tiles:
    initialize_fov()
    
    

#==============================================================================
# Start the game!
#==============================================================================
main_menu()

                
                
#############################################
# To Do list:
# * If game_state == 'dead' upon saving, then give the save file a post-mortem file type.
# * Break out modules into their own files- objects, graphics, main program loop and globals
# * Set it outside on Martian soil- red colors, day/night cycle. Enlarge the play area. Buildings should
#   be placed by the map after terrain is created, as white squares which are free to interrupt the terrain.
# * Choose a really neat main menu image- something like Gagarin Deep Space.
# * Implement a help menu that shows available key commands. Display it like the inventory window.
# * Display a separate game window to practice the difference between consoles and windows.
# * Scientists, laborers, engineers, with specializations:
#   Botanist (farmer), Engineer (builder), Laborer (?? operators?). Use the object component method described in 
#   tutorial 6.
# * Test out AI by having characters randomly walk from one building to another to simulate
#   a schedule. Have them say where they are going if the player bumps in to them or clicks on them.
# * Add a computer, and if the player uses the computer it brings up an interactive command prompt, possibly
#   in a separate window until they exit it. Make it gameplay relevant.
#############################################