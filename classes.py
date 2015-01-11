#============================================================= 
# This file holds the main class definitions for the game.
#============================================================= 

import libtcodpy as libtcod
from math import sqrt
from time import sleep
from random import choice
from constants import *

from utility_methods import switch, is_blocked

PLAYER_SPEED = 1
DEFAULT_SPEED = 8
DEFAULT_ATTACK_SPEED = 20

#============================================================= 
# Drawable objects
#============================================================= 

class GamePiece(object):
    """Anything which can be drawn. Players, NPCs, items, stairs, etc."""
    def __init__(
        self, 
        x, 
        y, 
        char, 
        name, 
        color, 
        blocks=False, 
        always_visible=False, 
        fighter=None, 
        ai=None, 
        item=None, 
        equipment=None, 
        speed=DEFAULT_SPEED,
        inventory=None
        ):

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

        # The possessions of this NPC or player:
        if inventory is None:
            self.inventory = []
        else:
            self.inventory = inventory

        # For creatures with names
        self.scifi_name = None
        self.spoken = False

    def move(self, mymap, dx, dy):
        """Move to a coordinate if it isn't blocked."""
        if not is_blocked(mymap, mymap.objects, self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

        # Whenever the thing moves, it has to wait:
        self.wait = self.speed
            
    def move_towards(self, mymap, target_x, target_y):
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
        self.move(mymap, dx, dy)
        
    def distance_to(self, other):
        """Return the distance to another object from this object."""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)        
        
    def distance(self, x, y):
        """Returns the distance between an object and a tile."""
        return math.sqrt( (x - self.x)**2 + (y - self.y)**2 )
        
    def draw(self, mymap, fov_map, con):
        """Set the color and then draw the object at its position."""
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and mymap[self.x][self.y].explored)):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
        
    def clear(self, con):
        """Erase the character that represents this object."""
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
        
    def send_to_back(self, objectlist):
        """
        Make this thing get drawn first, so that everything else appears above it if on the same tile
        otherwise NPC corpses get drawn on top of NPCs sometimes.
        """
        
        objectlist.remove(self)
        objectlist.insert(0, self)
        return objectlist
        
class Fighter(object):
    """Combat related properties and methods (NPC, player, NPC)."""
    def __init__(
        self, 
        hp, 
        defense, 
        power, 
        xp, 
        death_function=None, 
        attack_speed=DEFAULT_ATTACK_SPEED
        ):

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

class Item(object):
    """Item class defines usage, picking up, and dropping of GamePieces."""
    def __init__(self, use_function=None):
        self.use_function = use_function
    
    def use(self, creature):
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
                creature.inventory.remove(self.owner) #destroy after use unless the use was aborted
                
    def pick_up(self, creature):
        #it needs to be added to the player's inventory and removed from the map
        if len(creature.inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            creature.inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)

        #Special case: automatically equip an eligible piece of equipment if the slot is unused
        equipment = self.owner.equipment
        if equipment and get_equipped_in_slot(equipment.slot) is None:
            equipment.equip()
            
    def drop(self, creature):
        #Special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip()

        #add to the map and remove from the player's inventory. Place it at the player's coordinates
        objects.append(self.owner)
        creature.inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
            
class Equipment(object):
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

def get_equipped_in_slot(slot, creature): 
    """Returns the equipment in a slot, or None if its empty."""
    for obj in creature.inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(creature):
    """Returns a list of equipped items."""
    if creature.name is 'player':
        equipped_list = []
        for item in creature.inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        #other objects such as NPCs do not currently have equipment. If they do, change this.
        # Also I'm pretty sure it should be "return None" rather than "return []"
        return []
