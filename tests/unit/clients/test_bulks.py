import json
import typing as t

from datetime import UTC, datetime

from pydantic import HttpUrl

from server.clients import bulks
from server.entities.bulk_request import BulkOperation, BulkResponse
from server.entities.map_error import MapError
from server.entities.map_group import Administrator, MapGroup, MemberUser, Meta, Service
from tests.helpers import load_json_data


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_post(app, mocker: MockerFixture):
    operations = []
    access_token = "test_access_token"
    client_secret = "test_client"
    mocker.patch("server.clients.bulks.get_time_stamp", return_value="1772175516")
    mocker.patch(
        "server.clients.bulks.compute_signature",
        return_value="9f09ff6b8e31dec7c51662c2da90a5f95dc878a86f781ccb0205ed1649f2f22c",
    )

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = json.dumps(load_json_data("data/map_bulk.json"))
    mocker.patch("server.clients.bulks.requests.post", return_value=mock_response)
    put_group = MapGroup(
        schemas=["urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Group"],
        id="c8fdd6b4-35b6-41b8-959b-0e24b9a9700d",
        display_name="JAIRO test group UPDATED",
        public=False,
        description="Created by John Doe",
        member_list_visibility="Private",
        meta=Meta(
            created=datetime(2025, 8, 28, 2, 3, 40, tzinfo=UTC),
            last_modified=datetime(2025, 8, 28, 2, 3, 40, tzinfo=UTC),
        ),
        members=[
            MemberUser(
                value="00404105-6f3e-47bb-b839-ad093153b34c",
                display="John Doe",
                ref=HttpUrl("https://sptest.cg.example.jp/api/v2/Users/00404105-6f3e-47bb-b839-ad093153b34c"),
            )
        ],
        administrators=[
            Administrator(
                value="00404105-6f3e-47bb-b839-ad093153b34c",
                display="John Doe",
                ref=HttpUrl("https://sptest.cg.example.jp/api/v2/Users/00404105-6f3e-47bb-b839-ad093153b34c"),
            )
        ],
        services=[
            Service(
                value="jairocloud-groups-manager",
                display="JAIRO Cloud Groups Manager",
                administrator_of_group=0,
                ref=HttpUrl("https://sptest.cg.example.jp/api/v2/Services/jairocloud-groups-manager"),
            )
        ],
    )
    expected = BulkResponse(
        operations=[
            BulkOperation(
                method="PUT",
                path="Groups/c8fdd6b4-35b6-41b8-959b-0e24b9a9700d",
                data=put_group,
                response=put_group,
                status="200",
            ),
            BulkOperation(method="DELETE", path="Users/00404105-6f3e-47bb-b839-ad093153b34c", status="204"),
        ]
    )
    result = bulks.post(operations, access_token, client_secret)
    assert isinstance(result, BulkResponse)
    assert result == expected


def test_post_return_map_error(app, mocker: MockerFixture):
    operations = []
    access_token = "test_access_token"
    client_secret = "test_client"
    mocker.patch("server.clients.bulks.get_time_stamp", return_value="1772175516")
    mocker.patch(
        "server.clients.bulks.compute_signature",
        return_value="9f09ff6b8e31dec7c51662c2da90a5f95dc878a86f781ccb0205ed1649f2f22c",
    )

    mock_response = mocker.MagicMock()
    mock_response.status_code = 500
    mock_response.text = json.dumps(load_json_data("data/map_error.json"))
    mocker.patch("server.clients.bulks.requests.post", return_value=mock_response)
    expected = MapError.model_validate(load_json_data("data/map_error.json"))
    result = bulks.post(operations, access_token, client_secret)
    assert isinstance(result, MapError)
    assert result == expected
