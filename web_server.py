"""Compatibility shim for legacy `web_server` imports.

Routes and globals are defined in `src.web.server`. This module aliases the
package module so legacy imports interact with the same objects (including
monkeypatch of module-level globals like USERS_FILE).
"""

import importlib
import sys

_server = importlib.import_module("src.web.server")

# Expose all server attributes through this module name
sys.modules[__name__] = _server
