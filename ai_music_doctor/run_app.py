#!/usr/bin/env python3
"""
Quick launcher for AI Music Doctor (Development)
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui import run_app

if __name__ == '__main__':
    run_app()
