#!/usr/bin/env python3
"""
View confidence calibration report

Shows how Claude's confidence correlates with actual trade outcomes
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.confidence_calibration import confidence_calibration

if __name__ == "__main__":
    confidence_calibration.print_report()
