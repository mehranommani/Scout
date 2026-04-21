"""
Shared pytest fixtures.
Tests run from the backend/ directory so imports work correctly.
"""
import sys
import os
import pytest

# Add backend/ to sys.path so all backend modules are importable
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
