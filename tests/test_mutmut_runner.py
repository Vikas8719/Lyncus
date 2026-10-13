"""Tests for the mutmut subprocess adapter."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from Lyncus.core import mutmut_runner


def test_main_exports_mutmut_stats_as_json(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        if command[-1] == "export-cicd-stats":
            stats_path = Path("mutants/mutmut-cicd-stats.json")
            stats_path.parent.mkdir()
            stats_path.write_text(json.dumps({"killed": 2}), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    stdout = StringIO()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mutmut_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(mutmut_runner.sys, "stdout", stdout)

    assert mutmut_runner.main() == 0
    assert [call[-1] for call in calls] == ["run", "export-cicd-stats"]
    assert json.loads(stdout.getvalue()) == {"killed": 2}


def test_main_returns_when_mutmut_run_fails(monkeypatch):
    monkeypatch.setattr(
        mutmut_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )

    assert mutmut_runner.main() == 1


def test_main_returns_when_stats_export_fails(monkeypatch):
    results = iter((0, 1))
    monkeypatch.setattr(
        mutmut_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=next(results)),
    )

    assert mutmut_runner.main() == 1


def test_main_reports_invalid_export_file(monkeypatch, tmp_path):
    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[-1] == "export-cicd-stats":
            stats_path = Path("mutants/mutmut-cicd-stats.json")
            stats_path.parent.mkdir()
            stats_path.write_text("invalid", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    stderr = StringIO()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mutmut_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(mutmut_runner.sys, "stderr", stderr)

    assert mutmut_runner.main() == 2
    assert "Could not read mutmut CI stats" in stderr.getvalue()
