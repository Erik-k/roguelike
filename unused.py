# This is a file for the functions I'm currently not using

#====================
# IN PROGRESS
#====================


def blink_all_designations(gamemap_instance):
    """This blinks the designated construction zones (and other zones) periodically."""
    for y in range(MAP_HEIGHT): 
        for x in range(MAP_WIDTH):
            if gamemap_instance.level[x][y].designated:
                
# -----------------------------------------------------------------------------

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
    stairs.send_to_back() #so that it gets drawn below NPCs


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
