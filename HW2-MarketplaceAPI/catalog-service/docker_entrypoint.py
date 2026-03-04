#!/usr/bin/env python3
"""Entrypoint: загрузка приложения и запуск uvicorn."""
import os
import sys

os.environ.setdefault("PYTHONPATH", "/app:/app/src")
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/src")

try:
    from src.main import app
    print("Import OK")
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)

import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
