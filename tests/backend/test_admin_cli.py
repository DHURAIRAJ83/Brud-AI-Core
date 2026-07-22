from pathlib import Path
from types import SimpleNamespace

from backend import admin_cli
from backend.database.migrations import initialize_database


def test_admin_cli_lifecycle(monkeypatch, capsys, tmp_path: Path) -> None:
    database = tmp_path / "cli.db"
    initialize_database(database)
    monkeypatch.setattr(
        admin_cli, "get_settings", lambda: SimpleNamespace(resolved_database_path=database)
    )

    answers = iter(["Admin", "Administrator"])
    passwords = iter(["Strong-CLI-Password-42", "Strong-CLI-Password-42"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(admin_cli.getpass, "getpass", lambda _: next(passwords))
    assert admin_cli.run("create-admin") == 0

    assert admin_cli.run("list-admins") == 0
    output = capsys.readouterr().out
    assert "admin\tAdministrator\tactive" in output
    assert "password" not in output.lower()

    answers = iter(["admin", "disable"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert admin_cli.run("disable-admin") == 0
    answers = iter(["admin", "enable"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert admin_cli.run("enable-admin") == 0

    answers = iter(["admin", "reset"])
    passwords = iter(["Reset-CLI-Password-84", "Reset-CLI-Password-84"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(admin_cli.getpass, "getpass", lambda _: next(passwords))
    assert admin_cli.run("reset-password") == 0

    answers = iter(["admin", "Administrator"])
    passwords = iter(["Strong-CLI-Password-42", "Strong-CLI-Password-42"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(admin_cli.getpass, "getpass", lambda _: next(passwords))
    assert admin_cli.run("create-admin") == 1
