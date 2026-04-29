#!/usr/bin/env python
from app import create_app
from app.services.monitor_service import run_uptime_check

app = create_app()
ctx = app.app_context()
ctx.push()

try:
    print("Running uptime check for site 1...")
    run_uptime_check(1)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
