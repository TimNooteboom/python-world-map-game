"""World Map Game: a geography quiz in pygame.

Modules:
    config      sizes, colors, map views, time limits, file paths, the list of modes
    data        countries and US states (loading, names, point-in-shape tests)
    geo         turning lon/lat into screen pixels, drawing the map
    storage     scoreboards and flag/capital progress
    scope       one map you play on (the world or the USA) and its game in progress
    ui          buttons, cards, the answer box, the timer, flags
    labels      name tags on the map
    scoreboard  the "enter your name" and Top 10 screens
    menu        the Modes menu
    app         the window, main loop and switching between modes
    modes/      one class per kind of mode (naming game, guess games, quizzes, learn)
"""
