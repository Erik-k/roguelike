#==============================================================================
# Level and map creation  
#==============================================================================

import libtcodpy as libtcod
from constants import *

from utility_methods import MAP_WIDTH, MAP_HEIGHT, switch, is_blocked, choose_random_unblocked_spot, \
                            random_choice_index, random_choice, cast_heal
from classes import GamePiece, Fighter, Item, Equipment
from ai import BasicNPC, BasicExplorer, player_death, NPC_death, namegenerator



class GameMap(object):
    """
    This class holds all the information needed for processing a map, as well as the map itself.
    GameMaps have qualities which apply to an entire play area. 
    GameMaps have a unique id which is a sequential integer starting from 0, a location specifying 
    whether the map is predominately on the surface or inside the planet. 
    GameMaps contain a list of all objects within them. If an object moves between maps, such as the player
    going to a different area, the origin map needs to hand the player object to the destination map.
    """
    def __init__(self, id_number, level, fov_map, location='surface', objects=None):
        self.id_number = id_number
        self.level = level # this is the actual map.
        self.fov_map = fov_map
        self.location = location
        
        if objects is None:
            self.objects = []
        else:
            self.objects = objects

    def __getitem__(self, index):
        return self.level[index]

class Tile(object):
    """
    A tile in the map and its properties. These are the properties that an individual square has, 
    not to be confused with the properties that an entire game level might have.
    A map is a 2D array of Tiles.
    """
    def __init__(self, blocked, block_sight=True, char=' ', fore=libtcod.white, back=libtcod.black, outdoors=True):
        self.blocked = blocked #is it passable?
        self.block_sight = block_sight
        self.char = char 
        self.fore = fore #foreground color
        self.back = back #background color
        self.outdoors = outdoors
        self.mapedge = False
        self.explored = False

        # A tile can be designated for construction of some sort. If it is designated, it will blink.
        # designation_type determines more details like how it blinks or what it needs to be made into.
        self.designated = False
        self.designation_type = None
        self.designation_char = None

class Rect(object):
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

def create_room(room):
    """Makes the tiles in a rectangle passable."""
    global map

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_building(mymap, building):
    """Very similar to create_room but puts a border around it.
    Currently it makes a double pass over some of the tiles, first assigning them to be
    cleared and then putting a wall there (un-clearing them). That could probably be cleaned up.
    """

    # Clear the whole footprint
    for x in range(building.x1, building.x2+1):
        for y in range(building.y1, building.y2+1):
            mymap[x][y].blocked = False
            mymap[x][y].block_sight = False
            mymap[x][y].fore = color_ground
            mymap[x][y].back = color_ground
            mymap[x][y].outdoors = False

    #Create walls of building 
    for x in range(building.x1, building.x2+1):
        mymap[x][building.y1].blocked = True
        mymap[x][building.y1].block_sight = True
        mymap[x][building.y1].fore = color_building
        mymap[x][building.y1].back = color_building
        mymap[x][building.y2].blocked = True
        mymap[x][building.y2].block_sight = True
        mymap[x][building.y2].fore = color_building
        mymap[x][building.y2].back = color_building
    for y in range(building.y1, building.y2+1):
        mymap[building.x1][y].blocked = True
        mymap[building.x1][y].block_sight = True
        mymap[building.x1][y].fore = color_building
        mymap[building.x1][y].back = color_building
        mymap[building.x2][y].blocked = True
        mymap[building.x2][y].block_sight = True
        mymap[building.x2][y].fore = color_building
        mymap[building.x2][y].back = color_building

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

def make_surface_map(player=None):
    """
    Creates a map which is open by default, and then filled with boulders, mesas and buildings.
    Uses a 2D noise generator. The map has an impenetrable border.
    """
    objects_for_this_map = []
    new_objects = []
    more_objects = []

    if player is None:
        #Creating the object representing the player:
        fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death) #creating the fighter aspect of the player
        player = GamePiece(0, 0, 219, 'player', libtcod.white, blocks=False, fighter=fighter_component, speed=PLAYER_SPEED)
        player.level = 1

        objects_for_this_map.append(player)

    else:
        # This must not be a new game. We need to put the pre-existing player into the list and later give them an
        # appropriate spot in the map to have spatial translation continuity.
        objects_for_this_map.append(player)


    noise2d = libtcod.noise_new(2) #create a 2D noise generator
    libtcod.noise_set_type(noise2d, libtcod.NOISE_SIMPLEX) #tell it to use simplex noise for higher contrast

    # Create the map with a default tile choice of empty unblocked squares.
    newmap = [[ Tile(blocked=False, block_sight=False, char=' ', fore=color_ground, back=color_ground) 
        for y in range(MAP_HEIGHT)] 
            for x in range(MAP_WIDTH) ]

    #Put a border around the map so the characters can't go off the edge of the world
    for x in range(0, MAP_WIDTH):
        newmap[x][0].blocked = True
        newmap[x][0].block_sight = True
        newmap[x][0].mapedge = True
        newmap[x][0].fore = color_wall
        newmap[x][0].back = color_wall
        newmap[x][MAP_HEIGHT-1].blocked = True
        newmap[x][MAP_HEIGHT-1].block_sight = True
        newmap[x][MAP_HEIGHT-1].mapedge = True
        newmap[x][MAP_HEIGHT-1].fore = color_wall
        newmap[x][MAP_HEIGHT-1].back = color_wall
    for y in range(0, MAP_HEIGHT):
        newmap[0][y].blocked = True
        newmap[0][y].block_sight = True
        newmap[0][y].mapedge = True
        newmap[0][y].fore = color_wall
        newmap[0][y].back = color_wall
        newmap[MAP_WIDTH-1][y].blocked = True
        newmap[MAP_WIDTH-1][y].block_sight = True
        newmap[MAP_WIDTH-1][y].mapedge = True
        newmap[MAP_WIDTH-1][y].fore = color_wall
        newmap[MAP_WIDTH-1][y].back = color_wall

    # Create natural looking landscape
    for x in range(1, MAP_WIDTH-1):
        for y in range(1, MAP_HEIGHT-1):
            if libtcod.noise_get_turbulence(noise2d, [x, y], 128.0, libtcod.NOISE_SIMPLEX) < 0.4:
                #Turbulent simplex noise returns values between 0.0 and 1.0, with many values greater than 0.9.
                newmap[x][y].blocked = True
                newmap[x][y].block_sight = True
                newmap[x][y].fore = color_wall
                newmap[x][y].back = color_wall

    # Place buildings
    buildings = []
    num_buildings = 0
    for r in range(MAX_BUILDINGS):
        w = libtcod.random_get_int(0, BUILDING_MIN_SIZE, BUILDING_MAX_SIZE)
        h = libtcod.random_get_int(0, BUILDING_MIN_SIZE, BUILDING_MAX_SIZE)
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        new_building = Rect(x, y, w, h)
        create_building(newmap, new_building)
        buildings.append(new_building)
        num_buildings += 1

        #Create stairs in the last building
        if num_buildings == MAX_BUILDINGS:
            new_x, new_y = new_building.center()
            stairs = GamePiece(new_x, new_y, '>', 'stairs', libtcod.white, always_visible=True)
            objects_for_this_map.append(stairs)
            #stairs.send_to_back(newmap.objects) #so that it gets drawn below NPCs. I commented this out because
            # it should be at the end anyway, since its being appended.

    #Put doors in buildings. Have to do this AFTER they are built or later ones will overwrite earlier ones
    # door_chances = { 'left': 25, 'right': 25, 'top': 25, 'bottom': 25 }
    for place in buildings:
    #     num_doors = libtcod.random_get_int(0, 2, 4)
    #         for case in switch(num_doors):
    #             if case(2): 
    #                 choice = random_choice(door_chances)
        doorx, doory = place.middle_of_wall('left')
        if newmap[doorx][doory].blocked and not newmap[doorx][doory].mapedge: 
            newmap[doorx][doory].char = 29
            newmap[doorx][doory].blocked = False 
            newmap[doorx][doory].fore = libtcod.white
            newmap[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('top')
        if newmap[doorx][doory].blocked and not newmap[doorx][doory].mapedge:
            newmap[doorx][doory].char = 18
            newmap[doorx][doory].blocked = False 
            newmap[doorx][doory].fore = libtcod.white
            newmap[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('right')
        if newmap[doorx][doory].blocked and not newmap[doorx][doory].mapedge: 
            newmap[doorx][doory].char = 29
            newmap[doorx][doory].blocked = False 
            newmap[doorx][doory].fore = libtcod.white
            newmap[doorx][doory].back = libtcod.grey
        doorx, doory = place.middle_of_wall('bottom')
        if newmap[doorx][doory].blocked and not newmap[doorx][doory].mapedge: 
            newmap[doorx][doory].char = 18
            newmap[doorx][doory].blocked = False 
            newmap[doorx][doory].fore = libtcod.white
            newmap[doorx][doory].back = libtcod.grey

        #more_objects = place_objects(newmap, place) #add some contents to this room
        #if more_objects is not None:
            #for item in more_objects:
                #new_objects.append(item)

    # Scatter debris around the map to add flavor:
    place_junk(newmap)

    # Choose a spot for the player to start
    player.x, player.y = choose_random_unblocked_spot(newmap)

    for item in new_objects:
        objects_for_this_map.append(item)

    return newmap, objects_for_this_map


def place_objects(mymap, room):
    """Puts stuff all over the map AFTER the map has been created."""

    objects = []

    # max number of NPCs per room:
    #max_NPCs = from_difficulty_level( [ [2, 1], [3, 4], [5, 6] ] )
    max_NPCs = 2

    #chance of each NPC
    NPC_chances = {} # so that we can build the dict below
    NPC_chances['robot'] = 80 #this means that orcs always show up, even if other NPCs have 0 chance
    #NPC_chances['security bot'] = from_difficulty_level( [ [10, 1], [15, 3], [30, 5], [60, 7] ] )
    NPC_chances['security bot'] = 10
    NPC_chances['explorer'] = 80

    #maximum number of items per room
    #max_items = from_difficulty_level( [ [1, 1], [2, 4] ] )
    max_items = 1

    #chance of each item. By default they have a chance of 0 at level 1, which then increases.
    item_chances = {}
    item_chances['heal'] = 35 #heal pots always show up
    #item_chances['lightning'] = from_difficulty_level([[25, 4]])
    #item_chances['fireball'] =  from_difficulty_level([[25, 6]])
    #item_chances['confuse'] =   from_difficulty_level([[10, 2]])
    item_chances['sword'] = 25
    item_chances['shield'] = 15
 
    #choose a random number of NPCs
    num_NPCs = libtcod.random_get_int(0, 0, max_NPCs)

    for i in range(num_NPCs):
        #choose a spot for the NPC
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        
        #Create the NPC
        if not is_blocked(mymap, objects, x, y):
            choice = random_choice(NPC_chances)
            if choice == 'robot': 
                #Create an minor enemy
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=NPC_death)
                ai_component = BasicNPC(mymap)
                NPC = GamePiece(x, y, 'r', 'robot', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
                NPC.scifi_name = namegenerator()
                print 'Created robot named ' + str(NPC.scifi_name)
            elif choice == 'security bot':
                #Create a major enemy
                fighter_component = Fighter(hp=16, defense=1, power=4, xp=100, death_function=NPC_death)
                ai_component = BasicNPC(mymap)
                NPC = GamePiece(x, y, 'S', 'security bot', libtcod.darker_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
                NPC.scifi_name = namegenerator()
                print 'Created security bot named ' + str(NPC.scifi_name)
            else:
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=NPC_death)
                ai_component = BasicExplorer(mymap)
                NPC = GamePiece(x, y, '@', 'explorer', libtcod.green, blocks=True,
                    fighter=fighter_component, ai=ai_component)
                NPC.ai.create_path()
                print 'Created Explorer'
            
            objects.append(NPC)
            
    #Create and place items
    num_items = libtcod.random_get_int(0, 0, max_items)
    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        if not is_blocked(mymap, objects, x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #creating a healing potion:
                item_component = Item(use_function=cast_heal)
                item = GamePiece(x, y, '!', 'healing potion', libtcod.violet, always_visible=True, item=item_component)
            # elif choice == 'lightning': 
            #     # chance of lightning scroll
            #     item_component = Item(use_function=cast_lightning)
            #     item = GamePiece(x, y, '?', 'lightning scroll', libtcod.light_azure, always_visible=True, item=item_component)
            # elif choice == 'fireball':
            #     item_component = Item(use_function=cast_fireball)
            #     item = GamePiece(x, y, '*', 'fireball scroll', libtcod.orange, always_visible=True, item=item_component)
            elif choice == 'sword':
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = GamePiece(x, y, '/', 'sword', libtcod.sky, equipment=equipment_component, always_visible=True,)
            elif choice == 'shield':
                equipment_component = Equipment(slot='left hand', defense_bonus=1, max_hp_bonus=10)
                item = GamePiece(x, y, '0', 'shield', libtcod.brass, equipment=equipment_component, always_visible=True,)
            else: 
                item_component = Item(use_function=cast_confuse)
                item = GamePiece(x, y, '#', 'scroll of confusion', libtcod.light_yellow, always_visible=True, item=item_component)
                
            objects.append(item)

            #item.send_to_back(objects) #make items appear below other objects
            print 'objects is ' + str(len(objects)) + ' long.'
            for item in objects:
                print 'Returning objects in place_objects: ' + str(item)
            return objects


def place_junk(mymap):
    """
    Puts boulders, rocks, junk and/or plants around the map. Eventually I want it to accept a map as an 
    argument and depending on the type of map, (outdoors vs indoors, surface vs cavern, etc) place
    different debris. For example, indoors would have equipment and trash rather than rocks and plants.
    """
    # Ideally I can eventually get rid of this global statement and just accept a map object when we 
    # get to the point where there are many different maps stored (to allow returning to previous areas).

    debris = {}
    debris['nothing'] = 100
    debris['stone'] = 10
    debris['boulder'] = 10
    debris['gravel'] = 10

    for y in range(MAP_HEIGHT): 
            for x in range(MAP_WIDTH):
                if mymap[x][y].outdoors and not mymap[x][y].blocked:
                    choice = random_choice(debris)
                    if choice == 'nothing':
                        pass
                    elif choice == 'stone':
                        mymap[x][y].char = '.'
                        mymap[x][y].fore = libtcod.dark_sepia
                    elif choice == 'boulder':
                        mymap[x][y].char = 7 # bullet point
                        mymap[x][y].fore = libtcod.dark_sepia
                    else: # gravel
                        mymap[x][y].char = 176
                        mymap[x][y].fore = libtcod.dark_red
