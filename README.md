Roguelike Game-in-progress
==========================
The goal: [Dwarf Fortress](http://www.bay12games.com/dwarves) on mars.

and requires [libtcod-1.5.1](http://roguecentral.org/doryen/libtcod/).

Put the libtcod library's folder into the folder which contains the files in this repository. Then find "libtcod_py.py" 
and put that in the main folder with these files here.

Title Screen Image
------------------
Put the appropriately named .png file in the same folder as everything else. It's a 160x100 pixel image that gets
scaled up by libtcod's sub-cell font magic. I haven't settled on a final window size so the title image is not perfect.

To-Do list:
-----------
* If game_state == 'dead' upon saving, then give the save file a post-mortem file type. Create a method to
go through the post-mortems and present gameplay statistics.
* Break out modules into their own files- objects, graphics, main program loop and globals
* Set it outside on Martian soil- red colors, day/night cycle. Enlarge the play area. Buildings should
  be placed by the map after terrain is created, as white squares which are free to interrupt the terrain.
* Choose a really neat main menu image- something like Gagarin Deep Space.
* Try to use a hardware renderer, like OpenGL, rather than the software one. Do a simple system check to see
  if the hardware renderers are supported. Libtcod has stuff to do that check.
* Make sure that name generation is not continuosly opening the name.cfg file, but rather just opening it once
  on startup and keeping it in memory after that. 
* Scientists, laborers, engineers, with specializations:
  Botanist (farmer), Engineer (builder), Laborer (?? operators?). Use the object component method described in 
  tutorial 6.
* Add a computer, and if the player uses the computer it brings up an interactive command prompt, possibly
  in a separate window until they exit it. Make it gameplay relevant- locking doors, loading bot programs,
  reading emails and documents that provide backstory...

This was based off the [libtcod tutorial](http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod).
