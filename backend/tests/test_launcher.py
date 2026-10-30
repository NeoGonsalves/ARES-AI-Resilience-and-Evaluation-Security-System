"""Unit tests for the ARES Unified Launching Terminal Engine (launch.py)."""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add repository root to sys.path so launch can be imported
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import launch
from launch import (
    Colors,
    EnvironmentInfo,
    ServiceTask,
    build_child_env,
    build_service_tasks,
    clean_ports,
    colorize,
    detect_environment,
    get_pids_for_port,
    is_port_in_use,
    kill_process_tree,
    parse_args,
    probe_backend_health,
    set_colors_enabled,
)


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.target is None
    assert args.backend_port == 8000
    assert args.frontend_port == 5149
    assert args.lora_port == 11435
    assert args.host == "127.0.0.1"
    assert args.no_reload is False
    assert args.skip_health_check is False
    assert args.no_color is False
    assert args.no_clean is False
    assert args.timeout == 45.0


@pytest.mark.parametrize(
    "target_name",
    ["backend", "frontend", "both", "all", "lora", "status", "clean", "kill"],
)
def test_parse_args_valid_targets(target_name: str) -> None:
    args = parse_args([target_name])
    assert args.target == target_name


def test_parse_args_custom_ports_and_flags() -> None:
    args = parse_args([
        "both",
        "--backend-port", "9000",
        "--frontend-port", "6000",
        "--lora-port", "12000",
        "--host", "0.0.0.0",
        "--no-reload",
        "--skip-health-check",
        "--no-color",
        "--no-clean",
        "--timeout", "60",
    ])
    assert args.target == "both"
    assert args.backend_port == 9000
    assert args.frontend_port == 6000
    assert args.lora_port == 12000
    assert args.host == "0.0.0.0"
    assert args.no_reload is True
    assert args.skip_health_check is True
    assert args.no_color is True
    assert args.no_clean is True
    assert args.timeout == 60.0


def test_parse_args_short_port_flags() -> None:
    args = parse_args(["all", "-bp", "8080", "-fp", "5000", "-lp", "11000"])
    assert args.backend_port == 8080
    assert args.frontend_port == 5000
    assert args.lora_port == 11000


def test_colorize_toggle() -> None:
    set_colors_enabled(True)
    colored = colorize("ARES", Colors.RED)
    assert Colors.RED in colored
    assert Colors.RESET in colored

    set_colors_enabled(False)
    plain = colorize("ARES", Colors.RED)
    assert plain == "ARES"
    set_colors_enabled(True)


def test_detect_environment(tmp_path: Path) -> None:
    env_info = detect_environment(repo_root=repo_root)
    assert env_info.repo_root == repo_root
    assert env_info.backend_dir == repo_root / "backend"
    assert env_info.frontend_dir == repo_root / "src" / "Ares.Web"
    assert env_info.python_path.exists()
    assert env_info.python_version is not None


def test_build_child_env() -> None:
    env_info = detect_environment(repo_root=repo_root)
    child_env = build_child_env(env_info)

    assert child_env["PYTHONUNBUFFERED"] == "1"
    assert "PYTHONPATH" in child_env
    assert str(env_info.backend_dir) in child_env["PYTHONPATH"]
    if env_info.venv_path:
        assert child_env["VIRTUAL_ENV"] == str(env_info.venv_path)


def test_build_service_tasks_backend_only() -> None:
    env_info = detect_environment(repo_root=repo_root)
    tasks = build_service_tasks("backend", env_info, backend_port=8000, host="127.0.0.1", reload=True)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.tag == "BACKEND"
    assert task.port == 8000
    assert task.cwd == env_info.backend_dir
    assert "-m" in task.command
    assert "uvicorn" in task.command
    assert "app.main:app" in task.command
    assert "--reload" in task.command
    assert "8000" in task.command


def test_build_service_tasks_both() -> None:
    env_info = detect_environment(repo_root=repo_root)
    # Ensure dotnet_path is mocked if not installed on machine
    if not env_info.dotnet_path:
        env_info.dotnet_path = Path("/mock/dotnet")

    tasks = build_service_tasks("both", env_info, backend_port=8000, frontend_port=5149, reload=False)

    assert len(tasks) == 2
    tags = [t.tag for t in tasks]
    assert "BACKEND" in tags
    assert "FRONTEND" in tags

    backend_task = next(t for t in tasks if t.tag == "BACKEND")
    assert "--reload" not in backend_task.command

    frontend_task = next(t for t in tasks if t.tag == "FRONTEND")
    assert frontend_task.port == 5149
    assert "run" in frontend_task.command
    assert "--project" in frontend_task.command
    assert "http://localhost:5149" in frontend_task.command[frontend_task.command.index("--urls") + 1]


def test_build_service_tasks_all() -> None:
    env_info = detect_environment(repo_root=repo_root)
    if not env_info.dotnet_path:
        env_info.dotnet_path = Path("/mock/dotnet")

    tasks = build_service_tasks("all", env_info, backend_port=8000, frontend_port=5149, lora_port=11435)

    assert len(tasks) == 3
    tags = [t.tag for t in tasks]
    assert "BACKEND" in tags
    assert "FRONTEND" in tags
    assert "LORA" in tags

    lora_task = next(t for t in tasks if t.tag == "LORA")
    assert lora_task.port == 11435
    assert "ares.training.serve_lora" in lora_task.command
    assert "11435" in lora_task.command


def test_build_service_tasks_frontend_missing_dotnet_raises() -> None:
    env_info = EnvironmentInfo(
        repo_root=repo_root,
        backend_dir=repo_root / "backend",
        frontend_dir=repo_root / "src" / "Ares.Web",
        python_path=Path(sys.executable),
        dotnet_path=None,
        venv_path=None,
        is_windows=sys.platform == "win32",
    )

    with pytest.raises(RuntimeError, match=r"\.NET SDK CLI \('dotnet'\) was not found"):
        build_service_tasks("frontend", env_info)


def test_is_port_in_use() -> None:
    # Bind an ephemeral port to test detection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    try:
        assert is_port_in_use(port) is True
    finally:
        sock.close()

    # Free port should not be in use
    assert is_port_in_use(port) is False


def test_clean_ports_empty() -> None:
    # Non-existent or free port should return 0 killed
    killed = clean_ports([49151], verbose=False)
    assert killed == 0


def test_kill_process_tree_invalid_pid() -> None:
    assert kill_process_tree(-1) is False
    assert kill_process_tree(0) is False


def test_probe_backend_health_success() -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        ready = probe_backend_health(
            health_url="http://127.0.0.1:8000/health",
            backend_port=8000,
            timeout=1.0,
            interval=0.1,
        )
        assert ready is True


def test_probe_backend_health_timeout() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        ready = probe_backend_health(
            health_url="http://127.0.0.1:8000/health",
            backend_port=8000,
            timeout=0.3,
            interval=0.1,
        )
        assert ready is False
