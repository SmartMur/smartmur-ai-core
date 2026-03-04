"""Typed dataclasses for Telegram Bot API updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    id: int
    is_bot: bool = False
    first_name: str = ""
    last_name: str = ""
    username: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> User | None:
        if not data:
            return None
        return cls(
            id=data.get("id", 0),
            is_bot=data.get("is_bot", False),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            username=data.get("username", ""),
        )


@dataclass
class Chat:
    id: int
    type: str = "private"  # private, group, supergroup, channel
    title: str = ""
    username: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Chat | None:
        if not data:
            return None
        return cls(
            id=data.get("id", 0),
            type=data.get("type", "private"),
            title=data.get("title", ""),
            username=data.get("username", ""),
        )


@dataclass
class Voice:
    file_id: str = ""
    file_unique_id: str = ""
    duration: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Voice | None:
        if not data:
            return None
        return cls(
            file_id=data.get("file_id", ""),
            file_unique_id=data.get("file_unique_id", ""),
            duration=data.get("duration", 0),
        )


@dataclass
class PhotoSize:
    file_id: str = ""
    file_unique_id: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PhotoSize | None:
        if not data:
            return None
        return cls(
            file_id=data.get("file_id", ""),
            file_unique_id=data.get("file_unique_id", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            file_size=data.get("file_size", 0),
        )


@dataclass
class Document:
    file_id: str = ""
    file_unique_id: str = ""
    file_name: str = ""
    mime_type: str = ""
    file_size: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Document | None:
        if not data:
            return None
        return cls(
            file_id=data.get("file_id", ""),
            file_unique_id=data.get("file_unique_id", ""),
            file_name=data.get("file_name", ""),
            mime_type=data.get("mime_type", ""),
            file_size=data.get("file_size", 0),
        )


@dataclass
class Message:
    message_id: int = 0
    chat: Chat | None = None
    from_user: User | None = None
    text: str = ""
    caption: str = ""
    voice: Voice | None = None
    audio: Voice | None = None
    photo: list[PhotoSize] | None = None
    document: Document | None = None
    date: int = 0

    @property
    def chat_id(self) -> str:
        return str(self.chat.id) if self.chat else ""

    @property
    def is_command(self) -> bool:
        return self.text.startswith("/")

    @property
    def has_attachment(self) -> bool:
        return bool(self.photo or self.document)

    @property
    def command(self) -> str:
        """Extract command name without leading slash and bot mention."""
        if not self.is_command:
            return ""
        parts = self.text.split()
        cmd = parts[0][1:]  # Remove leading /
        return cmd.split("@")[0].lower()  # Remove @botname suffix

    @property
    def command_args(self) -> str:
        """Extract text after the command."""
        if not self.is_command:
            return ""
        parts = self.text.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Message | None:
        if not data:
            return None
        # Parse photo array (Telegram sends multiple sizes)
        photo_list = None
        raw_photos = data.get("photo")
        if raw_photos and isinstance(raw_photos, list):
            photo_list = [
                PhotoSize.from_dict(p)
                for p in raw_photos
                if p and PhotoSize.from_dict(p) is not None
            ]
        return cls(
            message_id=data.get("message_id", 0),
            chat=Chat.from_dict(data.get("chat")),
            from_user=User.from_dict(data.get("from")),
            text=data.get("text", ""),
            caption=data.get("caption", ""),
            voice=Voice.from_dict(data.get("voice")),
            audio=Voice.from_dict(data.get("audio")),
            photo=photo_list,
            document=Document.from_dict(data.get("document")),
            date=data.get("date", 0),
        )


@dataclass
class CallbackQuery:
    id: str = ""
    from_user: User | None = None
    message: Message | None = None
    data: str = ""

    @property
    def chat_id(self) -> str:
        if self.message and self.message.chat:
            return str(self.message.chat.id)
        return ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CallbackQuery | None:
        if not data:
            return None
        return cls(
            id=data.get("id", ""),
            from_user=User.from_dict(data.get("from")),
            message=Message.from_dict(data.get("message")),
            data=data.get("data", ""),
        )


@dataclass
class Update:
    update_id: int = 0
    message: Message | None = None
    callback_query: CallbackQuery | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Update:
        return cls(
            update_id=data.get("update_id", 0),
            message=Message.from_dict(data.get("message")),
            callback_query=CallbackQuery.from_dict(data.get("callback_query")),
        )


def parse_updates(data: dict[str, Any]) -> list[Update]:
    """Parse a getUpdates response into typed Update objects."""
    if not data.get("ok"):
        return []
    return [Update.from_dict(u) for u in data.get("result", [])]
