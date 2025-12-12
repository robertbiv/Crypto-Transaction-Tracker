import sys
from flask import Flask
from web_server import app

print("Inspecting Flask App Rules:")
with app.app_context():
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, Rule: {rule}")

    print("\nChecking for setup_wizard endpoint:")
    try:
        from flask import url_for
        url = url_for('setup_wizard')
        print(f"SUCCESS: url_for('setup_wizard') -> {url}")
    except Exception as e:
        print(f"FAILURE: {e}")
