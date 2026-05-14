
"""
AI Music Doctor - Main Entry Point
Denoise The Future Inc. © 2026
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import run_app

if __name__ == '__main__':
    run_app()

