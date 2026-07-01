import pytest

from server.entities.map_group import MapGroup
from server.entities.map_service import MapService
from server.entities.map_user import MapUser

from tests.helpers import load_json_data


@pytest.fixture
def map_service():
    json_data = load_json_data("data/map_service.json")
    map_service = MapService.model_validate(json_data)
    raw_json = map_service.model_dump_json(ensure_ascii=False, by_alias=True)

    return json_data, map_service, raw_json


@pytest.fixture
def map_group():
    json_data = load_json_data("data/map_group.json")
    map_group = MapGroup.model_validate(json_data)
    raw_json = map_group.model_dump_json(ensure_ascii=False, by_alias=True)

    return json_data, map_group, raw_json


@pytest.fixture
def map_user():
    json_data = load_json_data("data/map_user.json")
    map_user = MapUser.model_validate(json_data)
    raw_json = map_user.model_dump_json(ensure_ascii=False, by_alias=True)

    return json_data, map_user, raw_json
