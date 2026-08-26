"""Tests for the mock on-call contact lookup.

The on-call text file is read from a tmp path -- no external state.
"""
import pytest

from app.tools.mock import oncall as oncall_module
from app.tools.mock.oncall import OnCallContact, get_current_oncall


def _write(tmp_path, text):
    path = tmp_path / "current_oncall.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_oncall_file(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        "Name: Ayush Sharma\n"
        "Role: Backend On-Call Engineer\n"
        "Email: cocruxexoipra-2710@yopmail.com\n"
        "Team: backend\n"
        "Status: on-call\n",
    )
    monkeypatch.setattr(oncall_module, "ONCALL_FILE_PATH", path)

    contact = get_current_oncall()

    assert isinstance(contact, OnCallContact)
    assert contact.name == "Ayush Sharma"
    assert contact.role == "Backend On-Call Engineer"
    assert contact.email == "cocruxexoipra-2710@yopmail.com"
    assert contact.team == "backend"
    assert contact.status == "on-call"


def test_ignores_lines_without_colon(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        "Name: Ayush Sharma\n"
        "just some text\n"
        "Role: Backend On-Call Engineer\n"
        "Email: cocruxexoipra-2710@yopmail.com\n"
        "\n"
        "Team: backend\n"
        "Status: on-call\n",
    )
    monkeypatch.setattr(oncall_module, "ONCALL_FILE_PATH", path)

    contact = get_current_oncall()

    assert contact.name == "Ayush Sharma"
    assert contact.email == "cocruxexoipra-2710@yopmail.com"
    assert contact.team == "backend"


def test_trims_surrounding_whitespace(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        "  Name:   Ayush Sharma  \n"
        "Role:  Backend On-Call Engineer  \n"
        "Email: cocruxexoipra-2710@yopmail.com\n"
        "Team: backend\n"
        "Status: on-call\n",
    )
    monkeypatch.setattr(oncall_module, "ONCALL_FILE_PATH", path)

    contact = get_current_oncall()

    assert contact.name == "Ayush Sharma"
    assert contact.role == "Backend On-Call Engineer"


def test_missing_file_raises(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist.txt"
    monkeypatch.setattr(oncall_module, "ONCALL_FILE_PATH", missing)

    with pytest.raises(FileNotFoundError, match="On-call mock data file not found"):
        get_current_oncall()