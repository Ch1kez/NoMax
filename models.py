from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from passlib.hash import pbkdf2_sha256


@dataclass
class User:
    id: int
    username: str
    hashed_password: str
    full_name: Optional[str] = None


@dataclass
class Relationship:
    id: int
    owner_id: int
    contact_id: int
    alias: Optional[str] = None


@dataclass
class CallParticipant:
    user_id: int
    joined: bool = False
    muted: bool = False


@dataclass
class CallRoom:
    id: int
    type: str  # "one_to_one" | "group"
    status: str  # "pending" | "active" | "ended"
    owner_id: int
    participants: List[CallParticipant] = field(default_factory=list)
    media_room_id: Optional[str] = None


_users: List[User] = []
_relationships: List[Relationship] = []
_calls: List[CallRoom] = []
_user_id_seq = 1
_rel_id_seq = 1
_call_id_seq = 1


def get_password_hash(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_user_password(plain_password: str, hashed_password: str) -> bool:
    return pbkdf2_sha256.verify(plain_password, hashed_password)


async def create_user(username: str, password: str, full_name: Optional[str] = None) -> User:
    global _user_id_seq
    user = User(
        id=_user_id_seq,
        username=username,
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    _user_id_seq += 1
    _users.append(user)
    return user


async def get_user_by_username(username: str) -> Optional[User]:
    for user in _users:
        if user.username == username:
            return user
    return None


async def get_user_by_id(user_id: int) -> Optional[User]:
    for user in _users:
        if user.id == user_id:
            return user
    return None


async def create_relationship(owner_id: int, contact_id: int, alias: Optional[str] = None) -> Relationship:
    global _rel_id_seq
    rel = Relationship(
        id=_rel_id_seq,
        owner_id=owner_id,
        contact_id=contact_id,
        alias=alias,
    )
    _rel_id_seq += 1
    _relationships.append(rel)
    return rel


async def list_relationships_for_user(owner_id: int) -> List[Relationship]:
    return [rel for rel in _relationships if rel.owner_id == owner_id]


async def create_call_room(
    owner_id: int,
    participant_ids: List[int],
    call_type: str = "one_to_one",
    media_room_id: Optional[str] = None,
) -> CallRoom:
    global _call_id_seq
    room = CallRoom(
        id=_call_id_seq,
        type=call_type,
        status="pending",
        owner_id=owner_id,
        participants=[CallParticipant(user_id=pid) for pid in participant_ids],
        media_room_id=media_room_id,
    )
    _call_id_seq += 1
    _calls.append(room)
    return room


async def get_call_room(call_id: int) -> Optional[CallRoom]:
    for room in _calls:
        if room.id == call_id:
            return room
    return None


async def update_call_status(call_id: int, status: str) -> Optional[CallRoom]:
    room = await get_call_room(call_id)
    if room:
        room.status = status
    return room


async def join_call_room(call_id: int, user_id: int) -> Optional[CallRoom]:
    room = await get_call_room(call_id)
    if not room:
        return None
    for p in room.participants:
        if p.user_id == user_id:
            p.joined = True
            break
    else:
        room.participants.append(CallParticipant(user_id=user_id, joined=True))
    room.status = "active"
    return room


