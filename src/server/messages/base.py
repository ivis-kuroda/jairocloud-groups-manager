#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides base classes for log messages used in the server application."""

# ruff: noqa: D105

import typing as t

from collections import UserString


class LogMessage(UserString):
    """Log message with a code and content."""

    __slots__ = ("code",)

    def __init__(self, code: t.LiteralString, message: t.LiteralString) -> None:
        """Initialize a LogMessage instance.

        Args:
            code (LiteralString): The log message code.
            message (LiteralString): The log message content.
        """
        super().__init__(message)
        self.code = code

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LogMessage):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        return hash((self.code, self.data))

    def __format__(self, format_spec: str) -> t.NoReturn:
        raise NotImplementedError

    def __add__(self, other: object) -> t.NoReturn:
        raise NotImplementedError

    def __radd__(self, other: object) -> t.NoReturn:
        raise NotImplementedError

    def __str__(self) -> str:
        return f"{self.code} | {self.data}"

    def __repr__(self) -> str:
        return f"LogMessage(code={self.code!r}, content={self.data!r})"

    def __mod__(self, mapping: dict[str, t.Any]) -> t.Self:
        return self.__class__(self.code, self.data % mapping)  # pyright: ignore[reportArgumentType]
