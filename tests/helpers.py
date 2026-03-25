import json

from pathlib import Path
from typing import Any


def load_json_data(file_path: str) -> dict[str, Any]:
    with (Path(__file__).parent / file_path).open() as file:
        return json.load(file)


class UnexpectedError(Exception):
    """Custom exception for unexpected errors in tests."""
