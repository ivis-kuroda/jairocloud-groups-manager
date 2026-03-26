#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Utilities to contribute for log messages."""

import hashlib
import importlib
import pathlib
import pkgutil

from datetime import UTC, datetime


try:
    from src.server import messages
    from src.server.messages.base import LogMessage
except ImportError:
    from server import messages
    from server.messages.base import LogMessage


def generate_type_stub() -> None:
    """Generate type stubs for log messages."""
    base_dir = pathlib.Path(messages.__file__).parent
    package_name = messages.__package__

    for _, module_name, _ in pkgutil.iter_modules([str(base_dir)]):
        if module_name == "base":
            continue

        src_path = base_dir / f"{module_name}.py"
        stub_path = base_dir / f"{module_name}.pyi"

        current_hash = _get_file_hash(src_path)
        if current_hash == _read_last_hash(stub_path):
            continue

        try:
            module = importlib.import_module(f"{package_name}.{module_name}")
        except ImportError:
            continue

        header = [
            f"# Stubs for {module.__name__}",
            f"# source hash: {current_hash}",
            f"# last generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
            "",
            "from typing import Final",
            "",
        ]

        body = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if not isinstance(attr, LogMessage):
                continue

            body.extend([
                f"{attr_name}: Final[str]",
                f'"""Message Code: {attr.code}',
                f'>>> "{attr.data.encode("unicode_escape").decode("utf-8")}"',
                '"""',
                "",
            ])

        stub_path.write_text("\n".join(header + body), encoding="utf-8")


def _get_file_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def _read_last_hash(stub_path: pathlib.Path) -> str:
    if not stub_path.exists():
        return ""
    with stub_path.open("r", encoding="utf-8") as f:
        first_line = f.readline()
        if first_line.startswith("# source hash:"):
            return first_line.split(":")[-1].strip()
        second_line = f.readline()
        if second_line.startswith("# source hash:"):
            return second_line.split(":")[-1].strip()
    return ""


if __name__ == "__main__":
    generate_type_stub()
