"""Launcher for headless bot execution"""
import sys
import os

# Ensure the project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from study_bot.main import main
main()
