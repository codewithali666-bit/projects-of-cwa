"""
Launch CWA - Autonomous JARVIS AI Agent (inside cwa_agent folder)
"""
import sys
import os
from pathlib import Path

# Add parent directory to path so imports work from anywhere
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    from cwa_agent.main import run
    run()
