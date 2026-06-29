from __future__ import annotations

from types import SimpleNamespace

from aiogram.enums import MessageEntityType
from aiogram.types import MessageEntity

from marco_bot.handlers.admin import extract_custom_emoji_ids


def test_extract_custom_emoji_ids_from_message_and_reply() -> None:
    message = SimpleNamespace(
        entities=[
            MessageEntity(type=MessageEntityType.CUSTOM_EMOJI, offset=0, length=1, custom_emoji_id="id-1"),
            MessageEntity(type="bold", offset=1, length=4),
        ],
        caption_entities=None,
        reply_to_message=SimpleNamespace(
            entities=[MessageEntity(type=MessageEntityType.CUSTOM_EMOJI, offset=0, length=1, custom_emoji_id="id-2")],
            caption_entities=[MessageEntity(type=MessageEntityType.CUSTOM_EMOJI, offset=0, length=1, custom_emoji_id="id-1")],
        ),
    )

    assert extract_custom_emoji_ids(message) == ["id-1", "id-2"]