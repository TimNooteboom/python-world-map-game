# Map Game

A geography quiz game in Python and pygame. Name every country in the world against the clock, learn flags and
capitals, or switch to the USA and test yourself on the 50 states.

![Countries Game](screenshots/countries-game.png)

## Modes

The game opens on a start screen: click **World** for the Countries Game or **USA** for Guess the State.
After that, pick any mode from the **Modes** menu in the top-left corner, or click **Home** to return to the
start screen (your game in progress is kept, and its clock pauses).

**World**

| Mode | Learn | Game |
|---|---|---|
| Countries | Hover over a country to see its name and flag | Type the names of all 197 countries in 15 minutes. Click a continent to zoom in. |
| Flags | Hover over a country to see its flag, or take a practice test | Pick the right flag for every country in a continent. Get them all right to turn it green. |
| Capitals | Hover over a country to see its capital, or take a practice test | Pick the right capital for every country in a continent |

**USA**

| Mode | Learn | Game |
|---|---|---|
| States | Hover over a state to see its name and flag | Type all 50 states in 5 minutes |
| State Flags | Hover over a state to see its flag, or take a practice test | Pick the right flag for all 50 states |
| State Capitals | Hover over a state to see its capital, or take a practice test | Pick the right capital for all 50 states |
| Guess the State | | A state is highlighted: type its name. One try per state, 5 minutes. |
| Guess the Capital | | A state is highlighted: type its capital. One try per state, 5 minutes. |

The timed games (Countries, States, Guess the State and Guess the Capital) each have their own top 10 leaderboard.

![Guess the State](screenshots/guess-the-state.png)
![Flags Game](screenshots/flags-game.png)

## Tips

- Names autocomplete after 3 letters. Press **Tab** or **→** to accept a suggestion, and **↑/↓** to see others.
- The timer starts with your first answer.
- Stuck? Click a country or state you haven't named yet to see its first letter. In the Countries game this
  works once you've named your first country; in the States game any time; in Guess the State and Guess the
  Capital, click the blue state any time.
- In Guess the State and Guess the Capital, press **Space** before typing to come back to a state later. Small
  northeastern states get a **Zoom in** button.

## Run it

You need Python 3.10 or newer.

```
pip install -r requirements.txt
python world_map.py
```

## How the code is organized

`world_map.py` starts the game; the code is in the `worldmap` package:

| File | What's in it |
|---|---|
| `config.py` | Window size, colors, map views, time limits, file paths, the list of modes |
| `data.py` | Countries and US states: loading them, accepted names |
| `geo.py` | Turning longitude/latitude into screen pixels, drawing the map |
| `storage.py` | Scoreboards and flag/capital progress |
| `scope.py` | One map you play on (the world or the USA) and its game in progress |
| `ui.py`, `labels.py`, `scoreboard.py`, `menu.py` | Buttons, cards, the timer, name tags, the Top 10 screens, the Modes menu |
| `splash.py` | The start screen with the World and USA tiles, and the Home button that returns to it |
| `app.py` | The window, main loop, zooming and switching modes |
| `modes/` | One class per kind of mode: `naming.py` (Countries/States game), `guess.py` (Guess the State/Capital), `quiz.py` (multiple choice), `learn.py` (Learn modes) |

## Tests

```
python -m unittest discover tests
```

The tests play through every mode without opening a window and check things like scoring, name spelling and
save files. They save to a temporary folder, so your own scores are never touched.

## Build a Windows .exe

**Without a PC:** on GitHub, open the **Actions** tab, pick **Build Windows game** and click **Run workflow**.
After a few minutes `Map Game.exe` appears on the
[Releases page](https://github.com/TimNooteboom/python-world-map-game/releases/latest), ready to share.

**On a Windows PC** with Python installed, double-click `build_windows.bat`. It installs what it needs and builds
`dist\Map Game.exe`, a single file you can share. Windows may show "Windows protected your PC" the first time:
click **More info → Run anyway**.

## Credits

- Country and state shapes, and capitals: [Natural Earth](https://www.naturalearthdata.com/) (public domain)
- Flags: [Flagpedia / flagcdn.com](https://flagpedia.net/)
