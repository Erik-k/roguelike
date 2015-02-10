Roguelike Game-in-progress
==========================
The goal: [Dwarf Fortress](http://www.bay12games.com/dwarves) on mars.

This game requires [libtcod-1.5.1](http://roguecentral.org/doryen/libtcod/).

Put the libtcod library's folder into the folder which contains the files in this repository. Then find "libtcod_py.py" 
and put that in the main folder with these files here.

Title Screen Image
------------------
Put the appropriately named .png file in the same folder as everything else. It's a 160x100 pixel image that gets
scaled up by libtcod's sub-cell font magic. I haven't settled on a final window size so the title image is not perfect.

To-Do list:
-----------
* Builders just stand there after getting stuck once or twice. Make them more aggressive in recomputing and choosing
new paths.
* Its still possible to remove stuff by designating it and the builders just magically make it disappear from across 
the map. 
* Move the building designation logic into its own function. I wasn't able to get that to work for now.
* in move(), should the object.wait = object.speed be moved inside the if-else loop? This would prevent having to wait
so long after a failed attempt to move.

Future Goals:
-------------
* If game_state == 'dead' upon saving, then give the save file a post-mortem file type. Create a method to
go through the post-mortems and present gameplay statistics.
* Try to use a hardware renderer, like OpenGL, rather than the software one. Do a simple system check to see
  if the hardware renderers are supported. Libtcod has stuff to do that check.
* Make sure that name generation is not continuosly opening the name.cfg file, but rather just opening it once
  on startup and keeping it in memory after that. 
* Astronaut name generator - use a dictionary of real-world names combined with libtcod's namegen algorithm?
* Scientists, laborers, engineers, with specializations:
  Botanist (farmer), Engineer (builder), Laborer (?? operators?). Use the object component method described in 
  tutorial 6.
* Add a computer, and if the player uses the computer it brings up an interactive command prompt, possibly
  in a separate window until they exit it. Make it gameplay relevant- locking doors, loading bot programs,
  reading emails and documents that provide backstory...
* Adventure mode rather than construction mode - explore a world of randomly generated levels. This will use all
the single-player utilities that I cut out for the construction mode.

This was based off the [libtcod tutorial](http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod).
