from datetime import datetime

import pytest

from pydantic_core import ValidationError

from server.entities.map_user import EPPN, Email, Group, MapUser, Meta
from tests.helpers import load_json_data


def test_validate():
    json_data = load_json_data("data/map_user.json")

    user = MapUser(
        id=json_data["id"],
        external_id=json_data["externalId"],
        user_name=json_data["userName"],
        preferred_language=json_data["preferredLanguage"],
        meta=Meta(
            created=json_data["meta"]["created"],
            last_modified=json_data["meta"]["lastModified"],
            created_by=json_data["meta"]["createdBy"],
        ),
        edu_person_principal_names=[
            EPPN(
                value=json_data["eduPersonPrincipalNames"][0]["value"],
                idp_entity_id=json_data["eduPersonPrincipalNames"][0]["idpEntityId"],
            ),
        ],
        emails=[Email(value=json_data["emails"][0]["value"])],
        groups=[
            Group(
                value=json_data["groups"][0]["value"],
                ref=json_data["groups"][0]["$ref"],
            ),
            Group(
                value=json_data["groups"][1]["value"],
                ref=json_data["groups"][1]["$ref"],
            ),
        ],
    )
    assert user.schemas
    assert user.id == json_data["id"]
    assert user.external_id == json_data["externalId"]
    assert user.user_name == json_data["userName"]
    assert user.preferred_language == json_data["preferredLanguage"]
    assert user.meta
    assert user.meta.resource_type == "User"
    assert user.meta.created == datetime.fromisoformat(json_data["meta"]["created"])
    assert user.meta.last_modified == datetime.fromisoformat(json_data["meta"]["lastModified"])
    assert user.meta.created_by == json_data["meta"]["createdBy"]
    assert user.edu_person_principal_names
    assert len(user.edu_person_principal_names) == len(json_data["eduPersonPrincipalNames"])
    assert user.edu_person_principal_names[0].value == json_data["eduPersonPrincipalNames"][0]["value"]
    assert user.edu_person_principal_names[0].idp_entity_id == json_data["eduPersonPrincipalNames"][0].pop(
        "idpEntityId"
    )
    assert user.emails
    assert len(user.emails) == len(json_data["emails"])
    assert user.emails[0].value == json_data["emails"][0]["value"]
    assert user.groups
    assert len(user.groups) == len(json_data["groups"])
    assert user.groups[0].value == json_data["groups"][0]["value"]
    assert user.groups[1].value == json_data["groups"][1]["value"]

    json_user = user.model_dump(mode="json", by_alias=True, exclude={"schemas"})
    json_data.pop("schemas")
    assert json_user == json_data


def test_validate_json_data():
    json_data = load_json_data("data/map_user.json")
    user = MapUser.model_validate(json_data)

    assert user.schemas
    assert user.id == json_data["id"]
    assert user.external_id == json_data["externalId"]
    assert user.user_name == json_data["userName"]
    assert user.preferred_language == json_data["preferredLanguage"]
    assert user.meta
    assert user.meta.resource_type == "User"
    assert user.meta.created == datetime.fromisoformat(json_data["meta"]["created"])
    assert user.meta.last_modified == datetime.fromisoformat(json_data["meta"]["lastModified"])
    assert user.meta.created_by == json_data["meta"]["createdBy"]
    assert user.edu_person_principal_names
    assert len(user.edu_person_principal_names) == len(json_data["eduPersonPrincipalNames"])
    assert user.edu_person_principal_names[0].value == json_data["eduPersonPrincipalNames"][0]["value"]
    assert user.edu_person_principal_names[0].idp_entity_id == json_data["eduPersonPrincipalNames"][0].pop(
        "idpEntityId"
    )
    assert user.emails
    assert len(user.emails) == len(json_data["emails"])
    assert user.emails[0].value == json_data["emails"][0]["value"]
    assert user.groups
    assert len(user.groups) == len(json_data["groups"])
    assert user.groups[0].value == json_data["groups"][0]["value"]
    assert user.groups[1].value == json_data["groups"][1]["value"]

    json_user = user.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert json_user == json_data


def test_validate_json_data_invalid_type():
    json_data = load_json_data("data/map_user.json")
    json_data["meta"]["resourceType"] = "InvalidType"

    with pytest.raises(ValidationError, match="Input should be 'User'"):
        MapUser.model_validate(json_data)


def test_validate_reassign_resource_type():
    json_data = load_json_data("data/map_user.json")
    user = MapUser.model_validate(json_data)

    assert user.meta
    with pytest.raises(ValidationError, match="Instance is frozen"):
        user.meta.resource_type = "User"
