#============================================================= 
# AI modules and death states
#============================================================= 

import libtcodpy as libtcod
from random import choice
from math import sqrt
from constants import *

from utility_methods import MAP_WIDTH, MAP_HEIGHT, choose_random_unblocked_spot, find_player_in_list, \
                            message, move, move_towards, send_to_back, switch




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
    """
    def __init__(self):
        pass

    def take_turn(self, gamemap_instance):
        """The NPC takes its turn. If you can see it it can see you. It tries to move toward the
        player and attack the player."""

        NPC = self.owner
        object_list = gamemap_instance.objects
        player = find_player_in_list(object_list)
        fov_map = gamemap_instance.fov_map

        if libtcod.map_is_in_fov(fov_map, NPC.x, NPC.y):
            # move towards player if far away
            if NPC.distance_to(player) >= 2:
                move_towards(gamemap_instance, NPC, player.x, player.y)
            # if close enough, attack!
            elif player.fighter.hp > 0:
                NPC.fighter.attack(player)
                if not self.owner.spoken: 
                    message('My name is ' + self.owner.scifi_name +' and I am programmed to destroy!', libtcod.magenta)
                    self.owner.spoken = True


class BasicExplorer(object):
    """
    AI which chooses a random point on the map and travels there. This AI tries to explore the whole map, 
    seeking out unexplored areas.
    Current bugs: if I cast confuse on an explorer, after they finish being confused they then stumble around
    inside the room where I confused them and constantly create new paths to points on the map and immediately
    complete them, without moving. Occaisionally it would walk a few steps in the room before generating and
    erroneously finishing hundreds of paths. I think this might be because it generates an FOV map that only
    can see inside that room and considers that the whole world.
    Also, fov_map has to be passed in to take_turn even though its not currently used because the BasicNPC.take_turn
    needs it, and the call to the ai.take_turn() doesn't distinguish which AI its calling. Just a minor issue.
    """      
    def __init__(self):

        self.is_pathmap_created = False

    def create_path(self, gamemap_instance):
        """Creates the initial path_map, and then on subsequent calls uses that path_map to play."""

        mymap = gamemap_instance.level

        if not self.is_pathmap_created:
            #Create the path map
            self.path_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
            for x in range(1, MAP_WIDTH):
                for y in range(1, MAP_HEIGHT):
                    libtcod.map_set_properties(self.path_map, x, y, not mymap[x][y].block_sight, not mymap[x][y].blocked)
            self.is_pathmap_created = True

        # now use the path map to create the path from the explorer's current position to another spot:
        self.path = libtcod.path_new_using_map(self.path_map)
        random_destination_x, random_destination_y = choose_random_unblocked_spot(mymap)
        libtcod.path_compute(self.path, self.owner.x, self.owner.y, random_destination_x, random_destination_y)

        originx, originy = libtcod.path_get_origin(self.path)
        destx, desty = libtcod.path_get_destination(self.path)
        #print 'Created a new path with origin (' + str(originx)+', '+str(originy)+') and dest ('+str(destx)+
            # ', '+str(desty)+').'

    def take_turn(self, gamemap_instance):

        mymap = gamemap_instance.level
        object_list = gamemap_instance.objects

        if not self.is_pathmap_created:
            self.create_path(gamemap_instance)

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
            move(gamemap_instance, self.owner, dx, dy)        
        else:
            #print 'The Explorer ' + self.owner.name + ' has finished their path. Choosing a new one...'
            self.create_path(gamemap_instance)

class BasicBuilder(object):
    """This AI goes to Tiles where designated=True, and clears blocking tiles and then builds a building."""

    def __init__(self):

        self.is_pathmap_created = False

    def initalize_pathmap(self, gamemap_instance):
        """Allocate a pathfinding algorithm using the map this object is in."""

        self.mymap = gamemap_instance.level

        self.work_target = (None, None)

        #Create the path map
        self.path_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
        for x in range(1, MAP_WIDTH):
            for y in range(1, MAP_HEIGHT):
                libtcod.map_set_properties(self.path_map, x, y, not mymap[x][y].block_sight, not mymap[x][y].blocked)
    
    def pick_spot_to_work(self, gamemap_instance):
        """Choose a Tile that needs work done."""
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if gamemap_instance.level[x][y].designated:
                    return (x, y)

        return (None, None)

    def create_path(self, gamemap_instance):

        mymap = gamemap_instance.level

        if not self.is_pathmap_created:
            #Create the path map
            self.path_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
            for x in range(1, MAP_WIDTH):
                for y in range(1, MAP_HEIGHT):
                    libtcod.map_set_properties(self.path_map, x, y, not mymap[x][y].block_sight, not mymap[x][y].blocked)
            self.is_pathmap_created = True

        # now use the path map to create the path from the explorer's current position to another spot:
        self.path = libtcod.path_new_using_map(self.path_map)
        destinationx, destinationy = self.pick_spot_to_work(gamemap_instance)
        self.work_target = (destinationx, destinationy)

        if destinationx is not None:
            libtcod.path_compute(self.path, self.owner.x, self.owner.y, destinationx, destinationy)

            originx, originy = libtcod.path_get_origin(self.path)
            destx, desty = libtcod.path_get_destination(self.path)

    def take_turn(self, gamemap_instance):

        fov_map = gamemap_instance.fov_map
        object_list = gamemap_instance.objects
        mymap = gamemap_instance.level

        if not self.is_pathmap_created:
            self.create_path(gamemap_instance)

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
            move(gamemap_instance, self.owner, dx, dy)        
        elif self.work_target[0] is not None:
            # We have arrived at a Tile that needs work done. Now begin work:
            (x, y) = self.work_target
            for case in switch(mymap[x][y].designation_type):
                if case('clearing'): 
                    mymap[x][y].blocked = False
                    mymap[x][y].block_sight = False
                    mymap[x][y].char = GRAVEL

                    # Then reset the tile:
                    mymap[x][y].designated = False
                    mymap[x][y].designation_type = None
                    mymap[x][y].designation_char = None

                    break
                if case(): break # default
        else:
            pass



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
