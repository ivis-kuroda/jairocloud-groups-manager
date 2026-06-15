import inspect
import json
import re
import typing as t

from logging import LogRecord
from pathlib import Path

from server.messages.base import LogMessage


if t.TYPE_CHECKING:
    from collections.abc import Callable


def load_json_data(file_path: str) -> dict[str, t.Any]:
    with (Path(__file__).parent / file_path).open() as file:
        return json.load(file)


def unwrap[T: Callable](f: T) -> T:
    return inspect.unwrap(f)


if t.TYPE_CHECKING:

    def assert_message(actual: str, expected: str, args: dict | None = None) -> None: ...
    def regex(log_message: str) -> str: ...
    def extract(log_message: str, actual: str) -> dict[str, str]: ...

else:

    def assert_message(actual: str | LogMessage | LogRecord, expected: LogMessage, args: dict | None = None) -> None:
        __tracebackhide__ = True
        if isinstance(actual, LogRecord):
            message = actual.msg
            if isinstance(message, LogMessage):
                assert expected == message, f"Expected {expected.code}, got {message.code}"
                if args:
                    assert actual.args == args
                return
            actual_text = message

        elif isinstance(actual, LogMessage):
            assert expected == actual, f"Expected {expected.code}, got {actual.code}"

            if args:
                assert extract(expected, actual) == args

            return
        else:
            actual_text = actual

        pattern = regex(expected)

        assert re.search(pattern, actual_text), f"\nExpected: {pattern}\nActual:   {actual_text}"

    def regex(log_message: LogMessage) -> str:
        marker = "PLACEHOLDER"
        prepared = re.sub(r"%\(.*?\)s", marker, log_message.data)
        return re.escape(prepared).replace(r"\ ", " ").replace(marker, ".*?")

    def extract(log_message: LogMessage, actual: str | LogMessage) -> dict[str, str]:
        keys = re.findall(r"%\((.*?)\)s", log_message.data)
        marker_fmt = "PH{}MARKER"
        prepared = log_message.data
        for i in range(len(keys)):
            prepared = prepared.replace(f"%({keys[i]})s", marker_fmt.format(i))

        pattern = re.escape(prepared)

        for i, key in enumerate(keys):
            pattern = pattern.replace(marker_fmt.format(i), f"(?P<{key}>.*?)")

        if isinstance(actual, LogMessage):
            actual = actual.data

        match = re.search(pattern, actual)
        return match.groupdict() if match else {}


class UnexpectedError(Exception):
    """Custom exception for unexpected errors in tests."""
