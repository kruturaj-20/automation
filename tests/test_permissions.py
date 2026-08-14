"""
Unit tests for PermissionGuard and ExecutionLimiter.
"""

from pathlib import Path

import pytest
from src.core.config import LimitsConfig, SecurityConfig
from src.security.limits import ExecutionLimiter
from src.security.permissions import PermissionGuard


def test_permission_guard_allows_paths_within_boundary():
    cfg = SecurityConfig(allowed_dirs=["e:/Work", "e:\\Work"])
    guard = PermissionGuard(cfg)

    assert guard.is_path_allowed("e:/Work/automation") is True
    assert guard.is_path_allowed("e:/Work/Projects/new-app") is True


def test_permission_guard_blocks_paths_outside_boundary():
    cfg = SecurityConfig(allowed_dirs=["e:/Work"])
    guard = PermissionGuard(cfg)

    assert guard.is_path_allowed("c:/Windows/System32") is False
    assert guard.is_path_allowed("c:/Users/hp/Desktop") is False


def test_execution_limiter_stops_at_max_iterations():
    cfg = LimitsConfig(max_iterations=3, task_timeout_minutes=10)
    limiter = ExecutionLimiter(cfg)
    limiter.start()

    ok, _ = limiter.step()
    assert ok is True
    ok, _ = limiter.step()
    assert ok is True
    ok, _ = limiter.step()
    assert ok is True

    # 4th iteration exceeds limit of 3
    ok, reason = limiter.step()
    assert ok is False
    assert "limit exceeded" in reason


def test_execution_limiter_emergency_stop():
    cfg = LimitsConfig(max_iterations=10)
    limiter = ExecutionLimiter(cfg)
    limiter.start()

    limiter.emergency_stop()
    ok, reason = limiter.step()
    assert ok is False
    assert "Emergency stop" in reason
