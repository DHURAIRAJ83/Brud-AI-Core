"""Interactive local administrator lifecycle CLI."""

import argparse
import getpass
import sys

from pydantic import ValidationError as PydanticValidationError

from backend.core.config import get_settings
from backend.database.repositories import RepositoryError
from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate


def _password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("password confirmation does not match")
    return password


def run(command: str) -> int:
    repository = AdminRepository(get_settings().resolved_database_path)
    try:
        if command == "create-admin":
            username = input("Username: ")
            display_name = input("Display name: ")
            admin = repository.create_admin(
                AdminCreate(username=username, display_name=display_name, password=_password())
            )
            print(f"Created admin {admin.username} ({admin.public_id})")
        elif command == "list-admins":
            for admin in repository.list_admins():
                print(f"{admin.username}\t{admin.display_name}\t{admin.status}\t{admin.public_id}")
        elif command in {"disable-admin", "enable-admin"}:
            username = input("Username: ")
            action = "disable" if command == "disable-admin" else "enable"
            if input(f"Type {action} to confirm: ").strip().lower() != action:
                raise ValueError("confirmation cancelled")
            repository.set_status(username, "disabled" if action == "disable" else "active")
            print(f"Admin {action}d")
        elif command == "reset-password":
            username = input("Username: ")
            if input("Type reset to confirm: ").strip().lower() != "reset":
                raise ValueError("confirmation cancelled")
            repository.reset_password(username, _password())
            print("Password reset; existing sessions revoked")
    except (RepositoryError, PydanticValidationError, ValueError) as exc:
        print(f"Admin command failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI local admin management")
    parser.add_argument(
        "command",
        choices=("create-admin", "list-admins", "disable-admin", "enable-admin", "reset-password"),
    )
    return run(parser.parse_args(argv).command)


if __name__ == "__main__":
    raise SystemExit(main())
