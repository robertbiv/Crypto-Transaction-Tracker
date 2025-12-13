
import json
import os

CONFIG_FILE = 'config.json'

try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    print(f"Config loaded: {config}")
    response_data = json.dumps(config)
    print(f"Response data string: {response_data}")
    
    # Simulate JS parsing
    parsed = json.loads(response_data)
    print(f"Parsed in JS: {parsed}")
    
except Exception as e:
    print(f"Error: {e}")
