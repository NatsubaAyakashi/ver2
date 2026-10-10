@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Discord Bot Launcher
echo Starting Discord Bot...
python discord_bot.py
pause