"""World Map Game: a geography quiz. Run with:  python world_map.py

Click a continent to zoom in, then type the names of its countries; each one you get turns green.
The "Modes" menu (top left) switches between:

  World   Countries, Flags and Capitals, each with Learn (hover to see) and Game (timed naming game,
          or multiple choice where getting a whole continent right turns it green)
  USA     the same for the 50 states, plus Guess the State and Guess the Capital (one highlighted
          state at a time, timed)

The timed games each have a Top 10 scoreboard. The code is in the worldmap/ package (see its __init__.py).
"""

from worldmap import config
from worldmap.app import App

__all__ = ["App", "config"]  # config is handy for tools and tests: world_map.config

if __name__ == "__main__":
    App().run()
