#============================================================= 
# AI modules and death states
#============================================================= 

import libtcodpy as libtcod
from random import choice
from math import sqrt
from constants import *

from utility_methods import MAP_WIDTH, MAP_HEIGHT, choose_random_unblocked_spot




#for most types of AI that have different states, you can simply have a "state" property in the AI component, 
#like this: 
#class MultiStateAI:
#    def __init__(self):
#        self.state = 'chasing'
#    def take_turn(self):
#        if self.state == 'chasing': ...
#        elif self.state == 'running away': ...

class BasicNPC(object):
    """AI module for a basic NPC.
    Errors: I think the mymap parameter should be passed to take_turn, not __init__.
    """
    def __init__(self, mymap):
        self.mymap = mymap

    def take_turn(self, fov_map):
        #the NPC takes its turn. If you can see it it can see you
        NPC = self.owner
        if libtcod.map_is_in_fov(fov_map, NPC.x, NPC.y):
            # move towards player if far away
            if NPC.distance_to(player) >= 2:
                NPC.move_towards(self.mymap, player.x, player.y)
            # if close enough, attack!
            elif player.fighter.hp > 0:
                NPC.fighter.attack(player)
                if not self.owner.spoken: 
                    message('My name is ' + self.owner.scifi_name +' and I am programmed to destroy!', libtcod.magenta)
                    self.owner.spoken = True

            
class ConfusedNPC(object):
    """AI for a confused NPC. Must take previous AI as argument so it can revert to it after a while."""
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self, fov_map):
        if self.num_turns > 0:
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))            
            self.num_turns -= 1
        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)      

class BasicExplorer(object):
    """
    AI which chooses a random point on the map and travels there. This AI tries to explore the whole map, 
    seeking out unexplored areas.
    Current bugs: if I cast confuse on an explorer, after they finish being confused they then stumble around
    inside the room where I confused them and constantly create new paths to points on the map and immediately
    complete them, without moving. Occaisionally it would walk a few steps in the room before generating and
    erroneously finishing hundreds of paths.
    Also, fov_map has to be passed in to take_turn even though its not currently used because the BasicNPC.take_turn
    needs it, and the call to the ai.take_turn() doesn't distinguish which AI its calling. Just a minor issue.
    """      
    def __init__(self, mymap):
        """Allocate a pathfinding algorithm using a new map belonging to this object."""

        self.mymap = mymap

        #Create the path map
        self.path_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
        for x in range(1, MAP_WIDTH):
            for y in range(1, MAP_HEIGHT):
                libtcod.map_set_properties(self.path_map, x, y, not mymap[x][y].block_sight, not mymap[x][y].blocked)

    def create_path(self):
        # now use the path map to create the path from the explorer's current position to another spot:
        self.path = libtcod.path_new_using_map(self.path_map)
        random_destination_x, random_destination_y = choose_random_unblocked_spot(self.mymap)
        libtcod.path_compute(self.path, self.owner.x, self.owner.y, random_destination_x, random_destination_y)

        originx, originy = libtcod.path_get_origin(self.path)
        destx, desty = libtcod.path_get_destination(self.path)
        #print 'Created a new path with origin (' + str(originx)+', '+str(originy)+') and dest ('+str(destx)+
            # ', '+str(desty)+').'

    def take_turn(self, fov_map):
        if not libtcod.path_is_empty(self.path):
            pathx, pathy = libtcod.path_walk(self.path, True)
            #print 'Explorer is trying to move from (' + str(self.owner.x) + ', ' + str(self.owner.y) + 
                #') to (' + str(pathx) + ', ' + str(pathy) +').'
            dx = pathx - self.owner.x
            dy = pathy - self.owner.y
            distance = sqrt(dx ** 2 + dy ** 2)
     
            #normalize it to length 1 (preserving direction), then round it and
            #convert to integer so the movement is restricted to the map grid
            dx = int(round(dx / distance))
            dy = int(round(dy / distance))
            self.owner.move(self.mymap, dx, dy)        
        else:
            #print 'The Explorer ' + self.owner.name + ' has finished their path. Choosing a new one...'
            self.create_path()

def player_death(player, game_state):
    """Turn the player into a corpse and declare game over."""
    message('Game Over!', libtcod.red)

    # transform player into a corpse:
    player.char = '%'
    player.color = libtcod.dark_red
    player.name = 'remains of ' + player.name

    game_state = 'dead'
    return game_state
    
def NPC_death(NPC):
    """Transform into a corpse which doesn't block, can't move, and can't be attacked."""
    message(NPC.name.capitalize() + ' dies! You gain ' + str(NPC.fighter.xp) + ' experience points.', libtcod.orange)
    NPC.char = '%'
    NPC.color = libtcod.dark_red
    NPC.blocks = False
    NPC.fighter = None
    NPC.ai = None # important to make sure they dont keep acting! Unless they're a ghost...
    NPC.name = 'remains of ' + NPC.name
    NPC.send_to_back()
    
def namegenerator():
    """Create a random male or female demon name and return it as a string."""

    alphanumerics = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    choices = []
    new_name = ''
    for i in range(0, libtcod.random_get_int(0, 2, 4)):
        choices.append(choice(alphanumerics))

    try:
        libtcod.namegen_parse('libtcod-1.5.1/data/namegen/mingos_demon.cfg')
        if libtcod.random_get_int(0, 0, 1):
            return new_name.join(choices[i] for i in range(len(choices))) + '-' + libtcod.namegen_generate('demon male')
        else:
            return new_name.join(choices[i] for i in range(len(choices))) + '-' + libtcod.namegen_generate('demon female')
    except:
        print 'Cannot find name generator file. Is it in ./libtcod-1.5.1/data/namegen/mingos_demon.cfg ?'
