#!/usr/bin/env python3
"""Test screening results with Sydney time conversion"""
import sys
sys.path.insert(0, '.')

from src.web.server import _load_screening_results

print('Testing screening results loading with Sydney time conversion...')
results = _load_screening_results()

if 'sydney_timestamp' in results:
    print(f'✅ Sydney timestamp: {results["sydney_timestamp"]}')
    print(f'   Original UTC: {results.get("timestamp", "N/A")}')
    print()
    print('Available coins in screening:')
    for symbol in results.get('coins', {}).keys():
        coin_data = results['coins'][symbol]
        print(f'  - {symbol}: {coin_data["status"]} at ${coin_data.get("current_price", 0):.6f}')
else:
    print(f'⚠️  Result: {results}')
