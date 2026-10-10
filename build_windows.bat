@echo off
rem Builds "World Map Game.exe" from the files in this folder. Double-click to run.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" in the installer, then run this again.
    pause
    exit /b 1
)

echo Setting up (the first time takes a minute)...
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pygame-ce pyinstaller
if errorlevel 1 (
    echo Installing pygame-ce / pyinstaller failed. Check the internet connection and try again.
    pause
    exit /b 1
)

echo Building the game...
rem Bundle starting scoreboards only if the folder is here (it isn't in the GitHub download).
set "SCORES="
if exist starting_scores\ set "SCORES=--add-data=starting_scores;starting_scores"

pyinstaller --noconfirm --windowed --onefile --name "World Map Game" ^
  --add-data "countries.geojson;." --add-data "capitals.json;." --add-data "us_states.geojson;." ^
  --add-data "flags;flags" %SCORES% world_map.py
if errorlevel 1 (
    echo The build failed - see the messages above.
    pause
    exit /b 1
)

echo.
echo Done! The game is:  %cd%\dist\World Map Game.exe
echo That one file is all your friends need.
explorer dist
pause
