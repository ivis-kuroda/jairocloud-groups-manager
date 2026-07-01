import re
import typing as t

import server.clients.utils

from server.clients.utils import compute_signature, get_time_stamp


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_time_stamp(mocker: MockerFixture):
    mocker.patch.object(server.clients.utils.time, "time", return_value=1767667634.6385803)

    time_stamp = get_time_stamp()
    assert isinstance(time_stamp, str)
    assert re.match(r"^\d+$", time_stamp)
    assert time_stamp == "1767667634"


def test_compute_signature():
    time_stamp = "1767667634"
    client_secret, access_token = "bdaf22fc9d8a4b25b6f97f6a2a38f6ea", "bd06475264864f56"

    signature = compute_signature(client_secret, access_token, time_stamp)

    assert isinstance(signature, str)
    assert re.match(r"^[a-f0-9]{64}$", signature)
    assert signature == "24f9dd449705838fafc185bc8a6cd40b733f5653ae2b2bc8eeaf65d2dfaeb5d6"
