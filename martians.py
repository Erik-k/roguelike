#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#============================================================= 
# To use special characters from ASCII Code Page 437 (the terminal 16x16 tileset) pass the decimal value 
# for each of these characters to libtcod.console_put_char_ex as char.
# https://en.wikipedia.org/wiki/Code_page_437
#============================================================= 

# import general python and libtcod stuff:
import libtcodpy as libtcod
import math
import textwrap
import shelve
from time import sleep
from constants import *

# Now import stuff from the game's other files:
from classes import switch, GamePiece, Fighter, Item, Equipment
from utility_methods import is_blocked, choose_random_unblocked_spot, random_choice_index, random_choice, \
                             target_NPC
from mapcreation import MAP_WIDTH, MAP_HEIGHT, GameMap, Tile, Rect, create_room, create_building, create_h_tunnel, \
                            create_v_tunnel, make_surface_map, place_objects, place_junk
from ai import BasicNPC, BasicExplorer, player_death, NPC_death


def target_tile(mymap, max_range=None):
    """Return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked."""
    global key, mouse
    while True:
        # render the screen, which erases the inventory screen and shows the names of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all(mymap)
        
        (x, y) = (mouse.cx, mouse.cy)
        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and 
            (max_range is None or player.distance(x, y) <= max_range) ):
            return (x, y)
        # Give the player ways to cancel, if they right click or press escape:
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) # have to return a tuple with 2 output args


def next_level(list_of_maps, map_number):

    message('You rest for a moment and recover your strength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)

    message('You move onward to the next area...', libtcod.red)
    map_number += 1
    nextmap, objects_for_this_map = make_surface_map() # a fresh level!

    # Append this new level to the list_of_maps, and then append all the objects to that GameMap's
    # object list.
    list_of_maps.append(GameMap(map_number, nextmap, 'surface'))
    for item in objects_for_this_map:
                list_of_maps[map_number].objects.append(item)

    print 'Inside next level, map number is: ' + str(map_number)
    initialize_fov(nextmap)


def draw_things(list_of_maps, map_number):
    """
    This lets the player place things using the mouse by clicking on a tile and drawing over multiple
    tiles. Unforunately it looks like libtcod 1.5.1 has a bug where getting the (dcx, dcy) values from
    a mouse drag doesn't work. Or at least I cannot figure out how to get a good list of (dcx, dcy) 
    coordinates from a mouse drag event.
    """
    
    global key, mouse

    while True:
        # Rendering the screen first closes the menu and returns to the map, ready to place something
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)        
        render_all(list_of_maps, map_number)

        xlist = []
        ylist = []

        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None)  #cancel if the player right-clicked or pressed Escape

        if mouse.lbutton:
            while not mouse.lbutton_pressed:
                (xlength, ylength) = (mouse.dcx, mouse.dcy)
                xlist.append(xlength)
                ylist.append(ylength)
                print 'xlist and ylist are: ' + str(xlist) + ' ' + str(ylist)
            # If the mouse button was pressed and dragged, return affected coordinates
            return (xlist, ylist)

def build_menu(mymap, header):
    """
    Show a menu of things which can be built using the mouse.

    TODO: Add a fish which can be placed in water, and has an appropriate AI module. If placed on land it
    will turn to a skeleton (either the yen symbol or % like other corpses.)

    Current bugs:
    1) GamePiece objects don't get shaded properly when out of view
    2) Stuff can be placed inside walls
    3) Menu debouncing issues - the damn thing is hard to keep open. And if I click through really
        fast it can hang a bit.
    """

    options = [
                'Plant a gene modified dwarf tree', 
                'Place water',
                'Place a beacon',
                'Lay a horizontal pipe',
                'Lay a vertical pipe',
                'Build a pipe junction'
    ]
    
    choice = menu(header, options, INVENTORY_WIDTH)
    print 'Exited the build menu with choice ' + str(choice)
    if choice is None: 
        return None
    if choice == 0:
        (x, y) = target_tile(mymap)
        # draw_things() returns the mouse.dcx, mouse.dcy values for the console cells that were dragged over
        if x is not None and y is not None:
            thing = GamePiece(x, y, 6, 'tree', libtcod.darker_green, blocks=False, always_visible=True)
    elif choice == 1:
        (x, y) = target_tile(mymap)
        if x is not None and y is not None:
            thing = GamePiece(x, y, 247, 'liquid water', libtcod.blue, blocks=True, always_visible=True)
            mymap[x][y].back = libtcod.darker_blue
    elif choice == 2:
        (x, y) = target_tile(mymap)
        if x is not None and y is not None:
            thing = GamePiece(x, y, 143, 'a beacon', libtcod.brass * libtcod.dark_grey, blocks=False, always_visible=True)
    elif choice == 3:
        # horizontal pipe
        (x, y) = target_tile(mymap)
        if x is not None and y is not None:
            thing = GamePiece(x, y, 205, 'a pipe', libtcod.brass * libtcod.dark_grey, blocks=False, always_visible=True)
    elif choice == 4:
        # vertical pipe
        (x, y) = target_tile(mymap)
        if x is not None and y is not None:
            thing = GamePiece(x, y, 186, 'a pipe', libtcod.brass * libtcod.dark_grey, blocks=False, always_visible=True)
    elif choice == 5:
        # pipe junction
        (x, y) = target_tile(mymap)
        if x is not None and y is not None:
            thing = GamePiece(x, y, 206, 'a pipe', libtcod.brass * libtcod.dark_grey, blocks=False, always_visible=True)
            #check_for_junction(mymap, x, y)

    mymap.objects.append(thing)
    thing.send_to_back(mymap.objects)

    libtcod.console_flush()
    render_all(mymap)    

def check_for_junction(mymap, pipex, pipey):
    """This checks for a pipe junction and replaces the character with the relevant bent pipe character."""


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
    
def inventory_menu(header, creature):
    """Show a menu with each item of the inventory as an option."""
    if len(creature.inventory) == 0:
        options = ['Inventory is empty']
    else:
        # Create a list of items which will be passed to the menu() method for displaying
        options = []
        for item in creature.inventory:
            text = item.name
            #show additional information if it is equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
    
    index = menu(header, options, INVENTORY_WIDTH)
    #if an item was chosen, return it
    if index is None or len(creature.inventory) == 0: return None 
    return creature.inventory[index].item

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
        
def render_all(map_to_be_rendered, fov_map):
    """Draw everything on to the screen. This is where all the consoles get blit'd."""

    # Find the player in this map's list of objects:
    player_index = 0
    for obj in map_to_be_rendered.objects:
        if obj.name == 'player':
            break
        else:
            player_index += 1

    player = map_to_be_rendered.objects[player_index]

    #if fov_recompute:
    libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
        #fov_recompute = False

    # go through all tiles and set character, foreground and background according to FOV
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            wall = map_to_be_rendered[x][y].block_sight
            if not visible:
                if map_to_be_rendered[x][y].explored:
                    # Draw things outside of vision which are remembered
                    if wall:
                        libtcod.console_put_char_ex(con, x, y, map_to_be_rendered[x][y].char, 
                            libtcod.light_gray * map_to_be_rendered[x][y].fore, libtcod.light_gray * map_to_be_rendered[x][y].back)
                    else:
                        libtcod.console_put_char_ex(con, x, y, map_to_be_rendered[x][y].char, 
                            libtcod.dark_grey * map_to_be_rendered[x][y].fore, libtcod.dark_grey * map_to_be_rendered[x][y].back)
                        # TODO: Draw non-map things which are always visible, such as some objects.
                        # Currently objects with always_visible=True do not get shaded darker when
                        # outside of view. :-(

            else:
            # Currently visible things
                libtcod.console_put_char_ex(con, x, y, map_to_be_rendered[x][y].char, map_to_be_rendered[x][y].fore, map_to_be_rendered[x][y].back)
                map_to_be_rendered[x][y].explored = True

    for object in map_to_be_rendered.objects:
        if object != 'player':
            object.draw(map_to_be_rendered, fov_map, con)

    #if we didn't draw this separately, corpses and items sometimes get drawn over the player:        
    player.draw(map_to_be_rendered, fov_map, con) 
    
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
    #display location
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Location: ' +
         str(map_to_be_rendered.location))
    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse(map_to_be_rendered, fov_map))
    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
    
#==============================================================================
# Keyboard and Mouse management        
#==============================================================================
def player_move_or_attack(mymap, dx, dy):
    """
    This function determines whether the player moves into an empty space or interacts 
    with a creature or thing in that space (which means no movement).
    """
    
    # Find the player in this map's list of objects:
    player_index = 0
    for obj in mymap.objects:
        if obj.name == 'player':
            break
        else:
            player_index += 1

    player = mymap.objects[player_index]


    #the coordinates the player is moving to or attacking into
    x = player.x + dx
    y = player.y + dy
    
    #Is there an attackable object there?
    target = None
    for object in mymap.objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break #prevents attacking multiple overlapping things
            
    #attack if target found, otherwise move
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(mymap, dx, dy)
        #fov_recompute = True
        #return fov_recompute

def get_names_under_mouse(mymap, fov_map):
    global mouse
    
    #return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)    
    #print 'Getting names under mouse at: (' + str(x) + ', ' + str(y) + ').'

    # check for valid mouse region to prevent buffer overflow if the mouse goes into the GUI
    if y >= MAP_HEIGHT-1:
        return

    #create a list with the names of all objects under the mouse AND in FOV 
    names = [obj.name for obj in mymap.objects if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    
    # If there is junk placed, explain what it is
    if mymap[x][y].char is not ' ':
        for case in switch(mymap[x][y].char):
            if case('.'): 
                names.append('a stone')
                break
            if case(7): 
                names.append('a boulder')
                break
            if case(176): 
                names.append('gravel')
                break
            if case(): break

    names = ', '.join(names) #concatenates the names into a big string, separated by a comma
    return names.capitalize() 
    
def handle_keys(list_of_maps, map_number):
    """Handles all keyboard input."""
    global key

    mymap = list_of_maps[map_number] # mymap here IS a GameMap object

    # Find the player in this map's list of objects:
    player_index = 0
    for obj in mymap.objects:
        if obj.name == 'player':
            break
        else:
            player_index += 1

    player = mymap.objects[player_index]

    # Find the stairs in this map's list of objects:
    stair_index = 0
    for obj in mymap.objects:
        if obj.name == 'stairs':
            break
        else:
            stair_index += 1

    stairs = mymap.objects[stair_index]

    # -----------------------------------------------------
    # Now check for all the key presses that we care about:
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
            player_move_or_attack(mymap, 0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(mymap, 0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(mymap, -1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(mymap, 1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(mymap, -1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(mymap, 1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(mymap, -1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(mymap, 1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  #do nothing ie wait for the NPC to come to you
            
        else:
            #test for other keys
            key_char = chr(key.c)
            if key_char == 'g':
                #pick up an item
                for object in mymap.objects: #Is there an item in the player's tile?
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            
            if key_char == 'i':
                #show the inventory. If an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other key to cancel.\n', player)
                if chosen_item is not None:
                    chosen_item.use()
                    
            if key_char == 'd':
                #show the inventory and drop the selected item
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other key to cancel.\n', player)
                if chosen_item is not None:
                    chosen_item.drop()

            if key_char == '>':
                #go to next map
                if stairs.x == player.x and stairs.y == player.y:
                    print 'Going down stairs. Map number is: ' + str(map_number)
                    next_level(list_of_maps, map_number)
                    map_number += 1
                    return 'next_map'

            if key_char == '<':
                #go to previous map
                if upstairs.x == player.x and stairs.y == player.y:
                    print 'Going up stairs. Map number is: ' + str(map_number)
                    map_number -= 1
                    return 'previous_map'


            if key_char == 'c':
                #show character sheeet
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox(
                    'Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), 
                    CHARACTER_SCREEN_WIDTH)

            if key_char == 'h':
                #show help screen
                msgbox(
                    'The available keys are:\n' +
                    'keypad: Movement\n' +
                    'g: Get an item\n' +
                    'i: Show the inventory\n' +
                    'd: Drop an item\n' +
                    '>: Take down stairs\n' + 
                    'c: Show character information\n' + 
                    'q: Build something in a tile\n' +
                    '\nDebugging:\n' +
                    'm: Reveal map\n' +
                    'p: Print player coordinates', 
                    CHARACTER_SCREEN_WIDTH)

            if key_char == 'm':
                #Debugging - display whole map
                for y in range(MAP_HEIGHT):
                    for x in range(MAP_WIDTH):
                        mymap[x][y].explored = True

            if key_char == 'p':
                #Debugging - give us the player's coordinates
                print 'Player position is: (' + str(player.x) + ', ' + str(player.y) + ')'

            if key_char == 'q':
                # Display a menu from which the player can choose something to place on the map using the mouse.
                build_menu(mymap, 'Choose something to place with the mouse:\n')
                    
            return 'didnt_take_turn'
         
#############################################
# Initialization & Main Loop
#############################################
 
def new_game():
    global game_msgs, game_state
    
    map_number = 0
    list_of_maps = []

    #generate map, but at this point it's not drawn to the screen    
    newmap, objects_for_this_map = make_surface_map() # a fresh level!

    # Append this new level to the list_of_maps, and then append all the objects to that GameMap's
    # object list.
    list_of_maps.append( GameMap(map_number, newmap, 'surface') )
    for item in objects_for_this_map:
                list_of_maps[map_number].objects.append(item)

    fov_map = initialize_fov(newmap)

    game_state = 'playing'
    # Inventory assignment used to be here ("inventory = []") but now the list gets created on the line above where we create
    # the player gamepiece. 
    
    #create the list of game messages and their colors.
    game_msgs = []    

    message('Welcome to Mars! This is a test of a roguelike game engine in Python and Libtcod. Push h for help.', libtcod.red)

    return list_of_maps, map_number, fov_map

def initialize_fov(mymap):
    """This is needed to allow field of view stuff."""
    
    #create the FOV map according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not mymap[x][y].block_sight, not mymap[x][y].blocked)
            
    libtcod.console_clear(con)
    return fov_map

def initialize_pathmap():
    """Allocate a path using the FOV map."""
    global path, fov_map
    path = libtcod.path_new_using_map(fov_map)

def play_game(list_of_maps, map_number, fov_map):
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
        mymap = list_of_maps[map_number]
        render_all(mymap, fov_map) #render the screen
        libtcod.console_flush()

        #check_level_up()
        
        #erase all objects at their old locations, before they move
        for object in mymap.objects:
            object.clear(con)
    
        #handle keys and exit game if needed
        player_action = handle_keys(list_of_maps, map_number)
        if player_action == 'exit':
            save_game()
            break
        
        if player_action == 'next_map':
            map_number += 1

        if player_action == 'previous_map':
            map_number -= 1

        #let NPCs take their turn
        if game_state == 'playing': #and player_action != 'didnt_take_turn': #let NPCs take their turn
            for object in mymap.objects:
                if object.ai:
                    if object.wait > 0: # don't take a turn yet if still waiting
                        object.wait -= 1
                    else:
                        object.ai.take_turn(fov_map)
                    
def msgbox(text, width=50):
    """
    Use our menu() function as a sort of message box. Everything counts as the header, with no body,
    even though it can be multi line.
    """
    menu(text, [], width) 

def main_menu():
    """Displays splash screen and initial options such as new game, continue, save/load."""
    global end_credits
    img = libtcod.image_load('2001_station_and_shuttle.png')
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
            list_of_maps, map_number, fov_map = new_game()
            play_game(list_of_maps, map_number, fov_map)
        elif choice == 1: #load game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game(list_of_maps, map_number)
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
    file['map_number'] = map_number
    file.close()
    
def load_game():
    global map, objects, player, inventory, game_msgs, game_state, stairs, map_number
    
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']] #all we stored previously was the player index. The player itself was stored in objects[].
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    map_number = file['map_number']
    file.close()
    
    # Now that the core variables of the game have been restored, we can initialize the FOV map based on the loaded tiles:
    initialize_fov()
    

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

# Alternatively, just remake Scarab of Ra. Have the font start out really big on the early, smaller levels.