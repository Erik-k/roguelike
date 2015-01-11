#============================================================= 
# This file holds the stand-alone methods for the game. This way it 
# can be imported into all of the other files, since these methods 
# are used by a variety of functions, some of which are class functions.
#============================================================= 

import libtcodpy as libtcod
from constants import *




#============================================================= 
# Implement a switch-case construction, from this website: http://code.activestate.com/recipes/410692/
# because Python doesn't have switch-case statements but I want to use it.
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

#------------------------------------------------------------

def is_blocked(mymap, objects, x,y):
    """Is this square blocked by a map tile, or an object?"""
    #first see if the map tile itself is blocking
    if mymap[x][y].blocked:
        return True
    #now check for any objects that are blocking
    for item in objects:
        if item.blocks and item.x == x and item.y == y:
            return True
    
    return False

def choose_random_unblocked_spot(mymap):
    """
    This function picks a random point on the map which is not blocked. It returns the x, y coordinates for
    that location.
    """
    candidates = []
    for x in range(1, MAP_WIDTH):
            for y in range(1, MAP_HEIGHT):
                if not mymap[x][y].blocked:
                    candidates.append((x, y))
    rand_index = libtcod.random_get_int(0, 0, len(candidates)-1)
    return candidates[rand_index]

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

def from_difficulty_level(table):
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
        if difficulty_level >= level:
            return value
    return 0  #default is zero


#============================================================= 
# Spell functions
#============================================================= 
            
def target_NPC(mymap, max_range=None):
    """Returns a clicked NPC inside FOV up to a range, or None if right-click to cancel."""
    while True:
        (x, y) = target_tile(mymap, max_range)
        if x is None: #player canceled
            return None
            
        #return the first clicked NPC, otherwise continue looping
        for obj in mymap.objects:
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
    NPC = closest_NPC(LIGHTNING_RANGE)
    if NPC is None:
        message('No enemy is close enough to strike.', libtcod.azure)
        return 'cancelled'
        
    message('A lightning bolt strikes the ' + NPC.name + ' with a loud thunderclap! The damage is '
        + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    NPC.fighter.take_damage(LIGHTNING_DAMAGE)

def closest_NPC(max_range):
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
    NPC = target_NPC(CONFUSE_RANGE)
    if NPC is None: return 'cancelled'
    
    #replace the NPC's AI with the confused AI
    old_ai = NPC.ai
    NPC.ai = ConfusedNPC(old_ai)
    NPC.ai.owner = NPC #you need to tell the new component who owns it every time you replace a component during runtime
    message('The ' + NPC.name + ' starts to stumble around!', libtcod.light_green)
    
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


