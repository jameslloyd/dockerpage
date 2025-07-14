#!/usr/bin/env python3
import os

print("Testing DISABLE_STATS environment variable...")
print(f"Raw value: {repr(os.getenv('DISABLE_STATS'))}")
print(f"Lower case: {repr(os.getenv('DISABLE_STATS', '').lower())}")
print(f"Comparison result: {os.getenv('DISABLE_STATS', '').lower() == 'true'}")
print(f"Stats should be disabled: {os.getenv('DISABLE_STATS', '').lower() == 'true'}")

# Test with different values
test_values = ['true', 'True', 'TRUE', 'false', 'False', '', None]
for val in test_values:
    os.environ['DISABLE_STATS'] = str(val) if val is not None else ''
    result = os.getenv('DISABLE_STATS', '').lower() == 'true'
    print(f"Value '{val}' -> disabled: {result}")
