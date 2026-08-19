import pytest
from pydantic import ValidationError

from app.schemas.intent import CompilerIntent, RoomCategory, RoomIntent
from app.services.ai.parser import parse_requirements


@pytest.mark.parametrize("room_type", ["bedroom", "living", "bathroom"])
def test_room_category_accepts_gemini_values(room_type: str):
    assert RoomCategory(room_type).value == room_type


@pytest.mark.parametrize("room_type", ["bedroom", "living", "bathroom"])
def test_room_intent_coerces_gemini_values_to_room_category(room_type: str):
    room = RoomIntent(room_type=room_type)

    assert isinstance(room.room_type, RoomCategory)
    assert room.room_type.value == room_type


def test_room_intent_rejects_unsupported_room_category():
    with pytest.raises(ValidationError):
        RoomIntent(room_type="garage")


def test_compiler_intent_parses_representative_gemini_payload():
    payload = {
        "floors": 3,
        "front_road_setback": 3,
        "plot_depth": 42,
        "plot_width": 44,
        "rooms": [
            {"room_type": "bedroom"},
            {"room_type": "living"},
            {"room_type": "bathroom"},
        ],
    }

    intent = CompilerIntent.model_validate(payload)

    assert all(isinstance(room.room_type, RoomCategory) for room in intent.rooms)
    assert [room.room_type for room in intent.rooms] == [
        RoomCategory.BEDROOM,
        RoomCategory.LIVING,
        RoomCategory.BATHROOM,
    ]


def test_parser_requests_non_strict_structured_validation():
    class StructuredClient:
        def create(self, **kwargs):
            assert kwargs["strict"] is False
            payload = {
                "plot_width": 44,
                "plot_depth": 42,
                "rooms": [
                    {"room_type": "bedroom"},
                    {"room_type": "living"},
                    {"room_type": "bathroom"},
                ],
            }
            return kwargs["response_model"].model_validate(
                payload,
                strict=kwargs["strict"],
            )

    intent = parse_requirements("44x42 plot", client=StructuredClient())

    assert all(isinstance(room.room_type, RoomCategory) for room in intent.rooms)