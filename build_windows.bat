@echo off
rem Builds "Map Game.exe" from the files in this folder. Double-click to run.
cd /d "%~dp0"

rem A broken setup folder from an earlier version of this script can freeze the PC: remove it first.
if exist .venv rmdir /s /q .venv
set VIRTUAL_ENV=

rem Find a Python that works: the "py" launcher (python.org installs) first, then "python".
set PY=
py -c "import sys" >nul 2>nul && set PY=py
if not defined PY (python -c "import sys" >nul 2>nul && set PY=python)
if not defined PY (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" in the installer, then run this again.
    pause
    exit /b 1
)
%PY% --version

echo Setting up (the first time takes a minute)...
%PY% -m pip install --user --quiet --upgrade pygame-ce pyinstaller
if errorlevel 1 (
    echo Installing pygame-ce / pyinstaller failed. Check the internet connection and try again.
    pause
    exit /b 1
)

echo Building the game...
rem Bundle starting scoreboards only if the folder is here (it isn't in the GitHub download).
set "SCORES="
if exist starting_scores\ set "SCORES=--add-data=starting_scores;starting_scores"

%PY% -m PyInstaller --noconfirm --windowed --onefile --name "Map Game" ^
  --add-data "countries.geojson;." --add-data "capitals.json;." --add-data "us_states.geojson;." ^
  --add-data "flags;flags" %SCORES% world_map.py
if errorlevel 1 (
    echo The build failed - see the messages above.
    pause
    exit /b 1
)

echo.
echo Done! The game is:  %cd%\dist\Map Game.exe
echo That one file is all your friends need.
explorer dist
pause
