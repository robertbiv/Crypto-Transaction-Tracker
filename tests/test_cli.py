import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli


def _fake_run_factory(calls):
    def _fake_run(args, check=True):
        calls.append(args)
        return SimpleNamespace(returncode=0)
    return _fake_run


def test_cmd_run_adds_cascade_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(calls))
    args = SimpleNamespace(cascade=True)

    ok = cli.cmd_run(args)

    assert ok is True
    assert calls, "subprocess.run was not called"
    run_args = calls[0]
    assert '--cascade' in run_args
    assert Path(run_args[1]).name == 'Auto_Runner.py'


def test_cmd_run_defaults_to_current_year(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(calls))
    args = SimpleNamespace(cascade=False)

    ok = cli.cmd_run(args)

    assert ok is True
    assert calls, "subprocess.run was not called"
    run_args = calls[0]
    assert '--cascade' not in run_args
    assert Path(run_args[1]).name == 'Auto_Runner.py'


def test_cmd_test_specific_file_missing_returns_false():
    args = SimpleNamespace(file='missing_test_file.py')

    ok = cli.cmd_test(args)

    assert ok is False


def test_cmd_test_specific_file_invokes_pytest(monkeypatch):
    calls = []

    def fake_run(args, check=True):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    args = SimpleNamespace(file='test_setup_workflow.py')
    ok = cli.cmd_test(args)

    assert ok is True
    assert calls, "subprocess.run was not called"
    assert any('pytest' in str(arg) for arg in calls[0])
    assert any('test_setup_workflow.py' in str(arg) for arg in calls[0])


def test_run_python_script_missing_file_returns_false(tmp_path, monkeypatch):
    # Point CLI to a temp directory so the script path is guaranteed missing
    fake_cli_path = tmp_path / 'cli.py'
    fake_cli_path.write_text("# stub cli file")
    monkeypatch.setattr(cli, "__file__", str(fake_cli_path))

    ok = cli.run_python_script('not_real.py')

    assert ok is False


def test_main_no_command_shows_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['cli.py'])

    exit_code = cli.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "usage" in output.lower()
