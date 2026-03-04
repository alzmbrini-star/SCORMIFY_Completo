#!/usr/bin/env python3
"""
Minimal startup script that responds to health checks immediately.
The full server.py is imported, but health endpoints respond instantly.
"""
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 50, file=sys.stderr, flush=True)
print("SCORMIFY MINIMAL STARTUP", file=sys.stderr, flush=True)
print("=" * 50, file=sys.stderr, flush=True)

# Import the full app from server.py
# This will execute all the diagnostic prints we added
from server import app

print("=" * 50, file=sys.stderr, flush=True)
print("APP LOADED SUCCESSFULLY", file=sys.stderr, flush=True)
print("=" * 50, file=sys.stderr, flush=True)
