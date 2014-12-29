#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#============================================================= 
# To use special characters from ASCII Code Page 437 (the terminal 16x16 tileset) pass the decimal value 
# for each of these characters to console_put_char_ex as char.
# https://en.wikipedia.org/wiki/Code_page_437
#============================================================= 

import libtcodpy as libtcod
import math
import textwrap
import shelve
from time import sleep

#actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 43
INVENTORY_WIDTH = 50

#sizes and coords for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2  #this makes sure that the messages get placed next to the health bar
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH -2
MSG_HEIGHT = PANEL_HEIGHT -1
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
BUILDING_MAX_SIZE = 10
BUILDING_MIN_SIZE = 6
MAX_BUILDINGS = 10

# gameplay constants
HEAL_AMOUNT = 4
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

LIMIT_FPS = 20  #20 frames-per-second maximum
PLAYER_SPEED = 2
DEFAULT_SPEED = 8
DEFAULT_ATTACK_SPEED = 20

# FOV algorithm
FOV_ALGO = 1 # 0 is default FOV algorithm in libtcod.map_compute_fov
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
fov_recompute = True # boolean for letting us know when to recompute the map fov

# The map
color_wall = libtcod.dark_red
color_ground = libtcod.flame
color_building = libtcod.darker_red

#============================================================= 
# Implement a switch-case construction, from this website: http://code.activestate.com/recipes/410692/
# Python doesn't have switch-case statements but I want to use it.
#============================================================= 

class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
    
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:
            self.fall = True
            return True
        else:
            return False

#============================================================= 
# Drawable objects
#============================================================= 

class GamePiece:
    """Anything which can be drawn. Players, NPCs, items, stairs, etc."""
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, 
                fighter=None, ai=None, item=None, equipment=None, speed=DEFAULT_SPEED):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter: #if the fighter component was defined then let it know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item # I don't understand how this works! How can items be both an Item class and GamePiece class/object?
        if self.item:
            self.item.owner = self
        
        self.equipment = equipment
        if self.equipment: #let the Equipment component know who owns it
            self.equipment.owner = self

            #there must be an Item component for the Equipment component to work properly
            self.item = Item() # create an Item?
            self.item.owner = self

        self.speed = speed
        self.wait = 0

        # For creatures with names
        self.scifi_name = None
        self.spoken = False

    def move(self, dx, dy):
        """Move to a coordinate if it isn't blocked."""
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

        # Whenever the thing moves, it has to wait:
        self.wait = self.speed
            
    def move_towards(self, target_x, target_y):
        """
        Move towards a target_x, target_y coordinate. This method computes the A* path and uses GamePiece.move()
        to actually implement the movement.
        """
        initialize_pathmap()
        libtcod.path_compute(path, self.x, self.y, target_x, target_y)
        pathx, pathy = libtcod.path_walk(path, True)
        dx = pathx - self.x
        dy = pathy - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
 
        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)
        
    def distance_to(self, other):
        """Return the distance to another object from this object."""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)        
        
    def distance(self, x, y):
        """Returns the distance between an object and a tile."""
        return math.sqrt( (x - self.x)**2 + (y - self.y)**2 )
        
    def draw(self):
        """Set the color and then draw the object at its position."""
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
        
    def clear(self):
        """Erase the character that represents this object."""
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
        
    def send_to_back(self):
        """
        Make this thing get drawn first, so that everything else appears above it if on the same tile
        otherwise monster corpses get drawn on top of monsters sometimes.
        """
        global objects
        objects.remove(self)
        objects.insert(0, self)
        
class Fighter:
    """Combat related properties and methods (monster, player, NPC)."""
    def __init__(self, hp, defense, power, xp, death_function=None, attack_speed=DEFAULT_ATTACK_SPEED):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function
        self.attack_speed = attack_speed
        
    # @property means it is a read-only getter of the class
    # https://docs.python.org/2/library/functions.html#property
    # Any call to fighter.power, even in the fighter.attack() method, uses these new more inclusive definitions.
    # That is to say, in fighter.attack(), using self.power automatically uses these functions.
    @property
    def power(self):
        """return actual power by summing up all bonuses"""
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus

    @property
    def defense(self):
        """return actual defense by summing up all bonuses"""
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus

    @property
    def max_hp(self):
        """return actual max_hp by summing up all bonuses"""
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def take_damage(self, damage):
        if damage > 0:
            self.hp -= damage
            if self.hp <= 0: # if it died, do the appropriate thing according to its death_function
                function = self.death_function
                if function is not None:
                    function(self.owner)
                if self.owner != player:
                    player.fighter.xp += self.xp  #give xp to the player
            
    def attack(self, target):
        damage = self.power - target.fighter.defense

        if damage > 0:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' +str(damage)+ ' hit points.', libtcod.white)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.yellow)

        # Wait according to its speed
        self.owner.wait = self.attack_speed
            
    def heal(self, amount):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class Item:
    """Item class defines usage, picking up, and dropping of GamePieces."""
    def __init__(self, use_function=None):
        self.use_function = use_function
    
    def use(self):
        #Special case: if the object has the Equipment component, the "use" action is to equip/dequip
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return

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

        #Special case: automatically equip an eligible piece of equipment if the slot is unused
        equipment = self.owner.equipment
        if equipment and get_equipped_in_slot(equipment.slot) is None:
            equipment.equip()
            
    def drop(self):
        #Special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip()

        #add to the map and remove from the player's inventory. Place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
            
class Equipment:
    """Anything which can be equipped on a character."""
    def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
        self.slot = slot #slots are defined with strings
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        self.is_equipped = False

    def toggle_equip(self):
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self):
        if self.is_equipped: return

        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()

        #Equip object and show a message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self):
        # TODO: Make sure hp is below max_hp
        if not self.is_equipped: return
        self.is_equipped = False
        message('You\'ve unequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)

def get_equipped_in_slot(slot): 
    """Returns the equipment in a slot, or None if its empty."""
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj):
    """Returns a list of equipped items."""
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        #other objects such as monsters do not currently have equipment. If they do, change this.
        return []

#============================================================= 
# Targeting and spell functions
#============================================================= 

def target_tile(max_range=None):
    """Return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked."""
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
    """Returns a clicked monster inside FOV up to a range, or None if right-click to cancel."""
    while True:
        (x, y) = target_tile(max_range)
        if x is None: #player canceled
            return None
            
        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj
            
def cast_heal():
    """
    This method becomes the use_function property in the relevant Item object. So when Item.use_function() gets called, it calls
    this method, if the item had this passed as the parameter for use_function upon creation.
    """
    if player.fighter.hp >= player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
        
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    """Find the closest enemy inside a max range and damage it."""
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
    """AI module for a basic monster."""
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
                if not self.owner.spoken: 
                    message('My name is ' + self.owner.scifi_name +' and I am programmed to destroy!', libtcod.magenta)
                    self.owner.spoken = True

            
class ConfusedMonster:
    """AI for a confused monster. Must take previous AI as argument so it can revert to it after a while."""
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

def choose_random_unblocked_spot():
    """
    This function picks a random point on the map which is not blocked. It returns the x, y coordinates for
    that location.
    """
    candidates = []
    for x in range(1, MAP_WIDTH):
            for y in range(1, MAP_HEIGHT):
                if not map[x][y].blocked:
                    candidates.append((x, y))
    rand_index = libtcod.random_get_int(0, 0, len(candidates)-1)
    return candidates[rand_index]

class BasicExplorer:
    """
    AI which chooses a random point on the map and travels there. This AI tries to explore the whole map, 
    seeking out unexplored areas.
    """      
    def __init__(self):
        """Allocate a pathfinding algorithm using a new map belonging to this object."""

        #Create the path map
        self.path_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
        for x in range(1, MAP_WIDTH):
            for y in range(1, MAP_HEIGHT):
                libtcod.map_set_properties(self.path_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    def create_path(self):
        # now use the path map to create the path from the explorer's current position to another spot:
        self.path = libtcod.path_new_using_map(self.path_map)
        random_destination_x, random_destination_y = choose_random_unblocked_spot()
        libtcod.path_compute(self.path, self.owner.x, self.owner.y, random_destination_x, random_destination_y)

        originx, originy = libtcod.path_get_origin(self.path)
        destx, desty = libtcod.path_get_destination(self.path)
        print 'Created a new path with origin (' + str(originx)+', '+str(originy)+') and dest ('+str(destx)+', '+str(desty)+').'

    def take_turn(self):
        if not libtcod.path_is_empty(self.path):
            pathx, pathy = libtcod.path_walk(self.path, True)
            print 'Explorer is trying to move from (' + str(self.owner.x) + ', ' + str(self.owner.y) + ') to (' + str(pathx) + ', ' + str(pathy) +').'
            self.owner.move(pathx, pathy)
        # else:
        #     print 'The Explorer ' + self.owner.name + ' has finished their path. Choosing a new one...'
        #     self.create_path()


            
def player_death(player):
    """Turn the player into a corpse and declare game over."""
    global game_state
    message('Game Over!', libtcod.red)
    game_state = 'dead'
    # transform player into a corpse:
    player.char = '%'
    player.color = libtcod.dark_red
    
def monster_death(monster):
    """Transform into a corpse which doesn't block, can't move, and can't be attacked."""
    message(monster.name.capitalize() + ' dies! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None # important to make sure they dont keep acting! Unless they're a ghost...
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    
def namegenerator():
    """Create a random male or female demon name and return it as a string."""
    try:
        libtcod.namegen_parse('libtcod-1.5.1/data/namegen/mingos_demon.cfg')
        if libtcod.random_get_int(0, 0, 1):
            new_name = libtcod.namegen_generate('demon male')
        else:
            new_name = libtcod.namegen_generate('demon female')
        return new_name
    except:
        print 'Cannot find name generator file. Is it in ./libtcod-1.5.1/data/namegen/mingos_demon.cfg ?'


#==============================================================================
# Level and map creation  
#==============================================================================

class Tile:
    """
    A tile in the map and its properties.
    Make sure that if char, fore, or back are changed to non-default, that they are ALL changed.
    """
    def __init__(self, blocked, block_sight=True, char=' ', fore=libtcod.white, back=libtcod.black):
        self.blocked = blocked #is it passable?
        self.block_sight = block_sight
        self.char = char #for special characters like building components
        self.fore = fore #special foreground color
        self.back = back #special background color
        self.mapedge = False
        self.explored = False

class Rect:
    """A rectangle, with a center."""
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h        
        
    def center(self):
        """Returns the coordinates for the center of the rectangle."""
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)        
        
    def intersect(self, other):
        """Returns true if this rectangle intersects with another one. """
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)
       
    def middle_of_wall(self, side):
        """Returns the coordinates of the middle of a wall of a rectangle. Useful for placing a door there."""
        for case in switch(side):
            if case('left'): return ( self.x1, int((self.y1 + self.y2) / 2) )
            if case('right'): return ( self.x2, int((self.y1+self.y2)/2) )
            if case('top'): return (int((self.x1 + self.x2)/2), self.y1)
            if case('bottom'): return (int((self.x1 + self.x2)/2), self.y2)
            if case(): print 'Error: invalid side specified in Rect.middle_of_wall'

#-------------------------------------------------------------
def is_blocked(x,y):
    """Is this square blocked by a map tile, or an object?"""
    #first see if the map tile itself is blocking
    if map[x][y].blocked:
        return True
    #now check for any objects that are blocking
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
    
    return False

def create_room(room):
    """Makes the tiles in a rectangle passable."""
    global map

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_building(building):
    """Very similar to create_room but puts a border around it."""
    global map

    for x in range(building.x1, building.x2):
        for y in range(building.y1, building.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
            map[x][y].fore = color_ground
            map[x][y].back = color_ground

    #Create walls of building 
    for x in range(building.x1, building.x2+1):
        map[x][building.y1].blocked = True
        map[x][building.y1].block_sight = True
        map[x][building.y1].fore = color_building
        map[x][building.y1].back = color_building
        map[x][building.y2].blocked = True
        map[x][building.y2].block_sight = True
        map[x][building.y2].fore = color_building
        map[x][building.y2].back = color_building
    for y in range(building.y1, building.y2+1):
        map[building.x1][y].blocked = True
        map[building.x1][y].block_sight = True
        map[building.x1][y].fore = color_building
        map[building.x1][y].back = color_building
        map[building.x2][y].blocked = True
        map[building.x2][y].block_sight = True
        map[building.x2][y].fore = color_building
        map[building.x2][y].back = color_building

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

def make_surface_map():
    """
    Creates a map which is open by default, and then filled with boulders, mesas and buildings.
    Uses a 2D noise generator. The map has an impenetrable border.
    """
    global map, objects, stairs
    objects = [player]

    noise2d = libtcod.noise_new(2) #create a 2D noise generator
    libtcod.noise_set_type(noise2d, libtcod.NOISE_SIMPLEX) #tell it to use simplex noise for higher contrast

    map = [[ Tile(blocked=False, block_sight=False, char=' ', fore=color_ground, back=color_ground) 
        for y in range(MAP_HEIGHT)] 
            for x in range(MAP_WIDTH) ]
    #Put a border around the map so the characters can't go off the edge of the world
    for x in range(0, MAP_WIDTH):
        map[x][0].blocked = True
        map[x][0].block_sight = True
        map[x][0].mapedge = True
        map[x][0].fore = color_wall
        map[x][0].back = color_wall
        map[x][MAP_HEIGHT-1].blocked = True
        map[x][MAP_HEIGHT-1].block_sight = True
        map[x][MAP_HEIGHT-1].mapedge = True
        map[x][MAP_HEIGHT-1].fore = color_wall
        map[x][MAP_HEIGHT-1].back = color_wall
    for y in range(0, MAP_HEIGHT):
        map[0][y].blocked = True
        map[0][y].block_sight = True
        map[0][y].mapedge = True
        map[0][y].fore = color_wall
        map[0][y].back = color_wall
        map[MAP_WIDTH-1][y].blocked = True
        map[MAP_WIDTH-1][y].block_sight = True
        map[MAP_WIDTH-1][y].mapedge = True
        map[MAP_WIDTH-1][y].fore = color_wall
        map[MAP_WIDTH-1][y].back = color_wall

    # Create natural looking landscape
    for x in range(1, MAP_WIDTH-1):
        for y in range(1, MAP_HEIGHT-1):
            if libtcod.noise_get_turbulence(noise2d, [x, y], 128.0, libtcod.NOISE_SIMPLEX) < 0.4:
                #Turbulent simplex noise returns values between 0.0 and 1.0, with many values greater than 0.9.
                map[x][y].blocked = True
                map[x][y].block_sight = True
                map[x][y].fore = color_wall
                map[x][y].back = color_wall

    buildings = []
    num_buildings = 0
    for r in range(MAX_BUILDINGS):
        w = libtcod.random_get_int(0, BUILDING_MIN_SIZE, BUILDING_MAX_SIZE)
        h = libtcod.random_get_int(0, BUILDING_MIN_SIZE, BUILDING_MAX_SIZE)
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        new_building = Rect(x, y, w, h)
        create_building(new_building)
        buildings.append(new_building)
        num_buildings += 1

        #Create stairs in the last building
        if num_buildings == MAX_BUILDINGS:
            new_x, new_y = new_building.center()
            stairs = GamePiece(new_x, new_y, '>', 'stairs',  libtcod.white, always_visible=True)
            objects.append(stairs)
            stairs.send_to_back() #so that it gets drawn below monsters

    # #Put doors in buildings. Have to do this AFTER they are built or later ones will overwrite earlier ones
    # door_chances = { 'left': 25, 'right': 25, 'top': 25, 'bottom': 25 }
    for place in buildings:
    #     num_doors = libtcod.random_get_int(0, 2, 4)
    #         for case in switch(num_doors):
    #             if case(2): 
    #                 choice = random_choice(door_chances)
        doorx, doory = place.middle_of_wall('left')
        if map[doorx][doory].blocked and not map[doorx][doory].mapedge: # don't bother putting a door in the middle of an empty room
            map[doorx][doory].char = 206
            map[doorx][doory].blocked = False 
            map[doorx][doory].fore = libtcod.white
            map[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('top')
        if map[doorx][doory].blocked and not map[doorx][doory].mapedge: # don't bother putting a door in the middle of an empty room
            map[doorx][doory].char = 23
            map[doorx][doory].blocked = False 
            map[doorx][doory].fore = libtcod.white
            map[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('right')
        if map[doorx][doory].blocked and not map[doorx][doory].mapedge: # don't bother putting a door in the middle of an empty room
            map[doorx][doory].char = 29
            map[doorx][doory].blocked = False 
            map[doorx][doory].fore = libtcod.white
            map[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('bottom')
        if map[doorx][doory].blocked and not map[doorx][doory].mapedge: # don't bother putting a door in the middle of an empty room
            map[doorx][doory].char = 18
            map[doorx][doory].blocked = False 
            map[doorx][doory].fore = libtcod.white
            map[doorx][doory].back = libtcod.grey

        place_objects(place) #add some contents to this room

    # Choose a spot for the player to start
    player.x, player.y = choose_random_unblocked_spot()


def make_underground_map():
    """Creates rectangular rooms and connects them with straight hallways. The default map is filled."""
    global map, objects, stairs
    
    objects = [player]    
    
    # fill map with blocked=True or blocked=False tiles
    # By using Python's range function this creates the list of tiles, even though its
    # just two for statements.
    map = [[ Tile(blocked=True, block_sight=True)
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

    #create stairs at the center of the last room
    stairs = GamePiece(new_x, new_y, '>', 'stairs',  libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back() #so that it gets drawn below monsters

def next_level():
    global dungeon_level

    message('You rest for a moment and recover your strength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)

    message('You descend deeper into the dungeon...', libtcod.red)
    dungeon_level += 1
    make_surface_map() # a fresh level!
    initialize_fov()
    
def random_choice_index(chances):
    """
    When given a list of chances, such as [80, 10, 10], it will randomly choose one according to
    its relative probability from that list. Accepts different formats, not just percentages, because
    it chooses from 1 to the sum of the chances. Example: [1, 1, 1, 2] means that the last item has a 
    40 percent chance (2/5) and the first three items each have a 20 percent chance (1/5) of having 
    their index returned. 
    """
    dice = libtcod.random_get_int(0, 1, sum(chances))

    running_sum = 0
    choice = 0
    
    for w in chances:
        running_sum += w
        if dice <= running_sum:
            return choice
        choice += 1

def random_choice(chances_dict):
    """Choose an option from a dictionary of {'thing': chance} pairs, and return the corresponding key."""
    chances = chances_dict.values() 
    strings = chances_dict.keys()

    return strings[random_choice_index(chances)] # returns the key which corresponds to the chosen chance

def from_dungeon_level(table):
    """
    Returns a value that depends on level. The table must be a list of [value, level] pairs. For example, 
    a square progression of [x**2, x] would be:
    [1, 1]
    [4, 2]
    [9, 3]
    which is represented as [[1, 1], [4, 2], [9, 3]]
    TODO: Use sorting to enforce the assumption that the table is in ascending order.
    """
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0  #default is zero

def place_objects(room):
    """Puts stuff all over the map AFTER the map has been created."""
    # max number of monsters per room:
    max_monsters = from_dungeon_level( [ [2, 1], [3, 4], [5, 6] ] )

    #chance of each monster
    monster_chances = {} # so that we can build the dict below
    monster_chances['robot'] = 80 #this means that orcs always show up, even if other monsters have 0 chance
    monster_chances['security bot'] = from_dungeon_level( [ [10, 1], [15, 3], [30, 5], [60, 7] ] )
    monster_chances['explorer'] = 80

    #maximum number of items per room
    max_items = from_dungeon_level( [ [1, 1], [2, 4] ] )

    #chance of each item. By default they have a chance of 0 at level 1, which then increases.
    item_chances = {}
    item_chances['heal'] = 35 #heal pots always show up
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] =  from_dungeon_level([[25, 6]])
    item_chances['confuse'] =   from_dungeon_level([[10, 2]])
    item_chances['sword'] = 25
    item_chances['shield'] = 15
 
    #choose a random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)

    for i in range(num_monsters):
        #choose a spot for the monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        
        #Create the monster
        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'robot': 
                #Create an minor enemy
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = GamePiece(x, y, 'r', 'robot', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
                monster.scifi_name = namegenerator()
            elif choice == 'security bot':
                #Create a major enemy
                fighter_component = Fighter(hp=16, defense=1, power=4, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = GamePiece(x, y, 'S', 'security bot', libtcod.darker_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
                monster.scifi_name = namegenerator()

            else:
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=monster_death)
                ai_component = BasicExplorer()
                monster = GamePiece(x, y, '@', 'explorer', libtcod.green, blocks=True,
                    fighter=fighter_component, ai=ai_component)
                monster.ai.create_path()

            
            objects.append(monster)
            
    #Create and place items
    num_items = libtcod.random_get_int(0, 0, max_items)
    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #creating a healing potion:
                item_component = Item(use_function=cast_heal)
                item = GamePiece(x, y, '!', 'healing potion', libtcod.violet, always_visible=True, item=item_component)
            elif choice == 'lightning': 
                # chance of lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = GamePiece(x, y, '?', 'lightning scroll', libtcod.light_azure, always_visible=True, item=item_component)
            elif choice == 'fireball':
                item_component = Item(use_function=cast_fireball)
                item = GamePiece(x, y, '*', 'fireball scroll', libtcod.orange, always_visible=True, item=item_component)
            elif choice == 'sword':
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = GamePiece(x, y, '/', 'sword', libtcod.sky, equipment=equipment_component)
            elif choice == 'shield':
                equipment_component = Equipment(slot='left hand', defense_bonus=1, max_hp_bonus=10)
                item = GamePiece(x, y, '0', 'shield', libtcod.brass, equipment=equipment_component)
            else: 
                item_component = Item(use_function=cast_confuse)
                item = GamePiece(x, y, '#', 'scroll of confusion', libtcod.light_yellow, always_visible=True, item=item_component)
                
            objects.append(item)
            item.send_to_back() #make items appear below other objects

#==============================================================================
# Graphics       
#==============================================================================

def message(new_msg, color=libtcod.white):     
    """
    Fills the game_msgs list with nicely word-wrapped tuples of (line, color). game_msgs is later displayed
    in the render_all method.
    """ 
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        game_msgs.append( (line, color) )
            
def menu(header, options, width):
    """
    Creates a menu with a header as the title at the top of the window, options is the list of strings
    to display, and height is formed from the header + the length of the word-wrapped options. 
    """
    #global end_credits
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
    
    #Display the libtcod credits. 
    # TODO: Put this in a separate console so that it can just run on its own without blocking
    # access to the menu. Make sure to kill that console if the user chooses an option so that
    # it doesnt keep running on top of whatever is next.
    # while not end_credits: 
    #     end_credits = libtcod.console_credits_render(5, 5, False)
    #     libtcod.console_flush()
    #     key = libtcod.console_check_for_keypress()
    #     if key.vk is not libtcod.KEY_NONE: break

    #present the root console to the player and wait for a key-press
    libtcod.console_flush()
    sleep(0.4) # Need to debounce otherwise the menus are super irritating
    key = libtcod.console_wait_for_keypress(True)
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    #convert the ASCII code to an index. If it corresponds to an option, return the index.
    index = key.c - ord('a') # key.c is the ASCII code of the character that was pressed
    if index >= 0 and index < len(options): return index
    return None
    
def inventory_menu(header):
    """Show a menu with each item of the inventory as an option."""
    if len(inventory) == 0:
        options = ['Inventory is empty']
    else:
        # Create a list of items which will be passed to the menu() method for displaying
        options = []
        for item in inventory:
            text = item.name
            #show additional information if it is equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
    
    index = menu(header, options, INVENTORY_WIDTH)
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None 
    return inventory[index].item
            
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    """Render a bar, such as a health or exp bar, with text in the middle."""

    #First calculate the width of the bar:
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
    """Draw everything on to the screen. This is where all the consoles get blit'd."""
    global fov_map, fov_recompute
    global dungeon_level

    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    # go through all tiles and set character, foreground and background according to FOV
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            wall = map[x][y].block_sight
            if not visible:
                if map[x][y].explored:
                    # Draw things outside of vision which are remembered
                    if wall:
                        libtcod.console_put_char_ex(con, x, y, map[x][y].char, 
                            libtcod.light_gray * map[x][y].fore, libtcod.light_gray * map[x][y].back)
                    else:
                        libtcod.console_put_char_ex(con, x, y, map[x][y].char, 
                            libtcod.dark_grey * map[x][y].fore, libtcod.dark_grey * map[x][y].back)
            else:
            # Currently visible things
                libtcod.console_put_char_ex(con, x, y, map[x][y].char, map[x][y].fore, map[x][y].back)
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
    #display dungeon level
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' +
         str(dungeon_level))
    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
    
#==============================================================================
# Keyboard and Mouse management        
#==============================================================================
def player_move_or_attack(dx, dy):
    """
    This function determines whether the player moves into an empty space or interacts 
    with a creature or thing in that space (which means no movement).
    """
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
    """Handles all keyboard input."""
    global fov_recompute
    global key
    global map

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  #exit game

    #movement keys
    if game_state == 'playing':

        if player.wait > 0: # don't take a turn yet if still waiting
            player.wait -= 1
            return

        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  #do nothing ie wait for the monster to come to you
            
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

            if key_char == '>':
                #go down stairs
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            if key_char == 'c':
                #show character sheeet
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

            if key_char == 'h':
                #show help screen
                msgbox('The available keys are:\nKeypad: movement\ng: get an item\ni: show the inventory\n' +
                    'd: drop an item\n>: Take down stairs\nc: Show character information\n\nDebugging:\n' +
                    'm: reveal map\np: print player coordinates', CHARACTER_SCREEN_WIDTH)

            if key_char == 'm':
                #Debugging - display whole map
                for y in range(MAP_HEIGHT):
                    for x in range(MAP_WIDTH):
                        map[x][y].explored = True

            if key_char == 'p':
                #Debugging - give us the player's coordinates
                print 'Player position is: (' + str(player.x) + ', ' + str(player.y) + ')'
                    
            return 'didnt_take_turn'
         
#############################################
# Initialization & Main Loop
#############################################
 
def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level
    
    #Creating the object representing the player:
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death) #creating the fighter aspect of the player
    player = GamePiece(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component, speed=PLAYER_SPEED)
    player.level = 1
    dungeon_level = 1

    #generate map, but at this point its not drawn to the screen    
    make_surface_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []    
    
    #create the list of game messages and their colors.
    game_msgs = []    

    message('Welcome to Mars! This is a test of a roguelike game engine in Python and Libtcod. Push h for help.', libtcod.red)

def initialize_fov():
    """This is needed to allow field of view stuff."""
    global fov_recompute, fov_map
    fov_recompute = True
    
    #create the FOV map according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
            
    libtcod.console_clear(con)

def initialize_pathmap():
    """Allocate a path using the FOV map."""
    global path, fov_map
    path = libtcod.path_new_using_map(fov_map)

def play_game():
    """This function contains the while loop."""
    #====================
    # THE MAIN LOOP
    #====================
    global key, mouse
    
    player_action = None
    
    mouse = libtcod.Mouse()
    key = libtcod.Key()
    while not libtcod.console_is_window_closed():
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
        render_all() #render the screen
       
        libtcod.console_flush()

        check_level_up()
        
        #erase all objects at their old locations, before they move
        for object in objects:
            object.clear()
    
        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break
        
        #let monsters take their turn
        if game_state == 'playing': #and player_action != 'didnt_take_turn': #let monsters take their turn
            for object in objects:
                if object.ai:
                    if object.wait > 0: # don't take a turn yet if still waiting
                        object.wait -= 1
                    else:
                        object.ai.take_turn()
                    
def msgbox(text, width=50):
    """
    Use our menu() function as a sort of message box. Everything counts as the header, with no body,
    even though it can be multi line.
    """
    menu(text, [], width) 

def main_menu():
    """Displays splash screen and initial options such as new game, continue, save/load."""
    global end_credits
    img = libtcod.image_load('menu_background1.png')
    end_credits = False
    while not libtcod.console_is_window_closed():
        #show the background image at 2x the normal resolution using special font characters to do sub-cell shading:
        libtcod.image_blit_2x(img, 0, 0, 0)
        
        #show the game's title and opening credits
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 
                                 'MANY MARTIANS!')
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
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()
    
def load_game():
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level
    
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']] #all we stored previously was the player index. The player itself was stored in objects[].
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()
    
    # Now that the core variables of the game have been restored, we can initialize the FOV map based on the loaded tiles:
    initialize_fov()
    
def check_level_up():
    # does the player have enough xp to level up?
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        # time to level up!
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('You become more skillful and stronger! Welcome to level ' + str(player.level) + '!', libtcod.yellow)

        # How does the player want to improve?
        choice = None
        while choice == None:
            choice = menu('Level up! Choose a stat to raise:\n',
                ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)
        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1

#==============================================================================
# Start the game!
#==============================================================================
libtcod.console_set_custom_font('libtcod-1.5.1/data/fonts/terminal16x16_gs_ro.png', 
    libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Many Martians', False)

# off screen console "con"
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
# GUI panel console "panel"
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS)

main_menu()

                
                
#############################################
# To Do list:
# * If game_state == 'dead' upon saving, then give the save file a post-mortem file type.
# * Break out modules into their own files- objects, graphics, main program loop and globals
# * Set it outside on Martian soil- red colors, day/night cycle. Enlarge the play area. Buildings should
#   be placed by the map after terrain is created, as white squares which are free to interrupt the terrain.
# * Choose a really neat main menu image- something like Gagarin Deep Space.
# * Try to use a hardware renderer, like OpenGL, rather than the software one. Do a simple system check to see
#   if the hardware renderers are supported. Libtcod has stuff to do that check.
# * Make sure that name generation is not continuosly opening the name.cfg file, but rather just opening it once
#   on startup and keeping it in memory after that. 
# * Rename "monster" to "NPC"
# * Scientists, laborers, engineers, with specializations:
#   Botanist (farmer), Engineer (builder), Laborer (?? operators?). Use the object component method described in 
#   tutorial 6.
# * Test out AI by having characters randomly walk from one building to another to simulate
#   a schedule. Have them say where they are going if the player bumps in to them or clicks on them.
# * Add a computer, and if the player uses the computer it brings up an interactive command prompt, possibly
#   in a separate window until they exit it. Make it gameplay relevant.
#############################################

# Alternatively, just remake Scarab of Ra. Have the font start out really big on the early, smaller levels.