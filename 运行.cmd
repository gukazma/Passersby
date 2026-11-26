@echo off
rem Run the game (arrow keys to move). Add -- --autoplay to watch the auto tour.
set GODOT=D:\tools\godot\4.6.3\Godot_v4.6.3-stable_win64.exe
start "" "%GODOT%" --path "%~dp0game" %*
