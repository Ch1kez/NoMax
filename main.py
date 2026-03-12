from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from auth import Token, get_current_user, login_for_access_token
from models import (
    CallRoom,
    User,
    create_call_room,
    create_relationship,
    create_user,
    get_call_room,
    get_user_by_id,
    get_user_by_username,
    join_call_room,
    list_relationships_for_user,
)


app = FastAPI(title="NoMax Voice Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://45.10.43.191:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str | None = None


class RelationshipOut(BaseModel):
    id: int
    contact: UserOut
    alias: str | None = None


class CallCreate(BaseModel):
    type: Literal["one_to_one", "group"] = "one_to_one"
    participant_ids: List[int]


class CallOut(BaseModel):
    id: int
    type: str
    status: str
    owner_id: int
    participant_ids: List[int]


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate):
    existing = await get_user_by_username(user_in.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    user = await create_user(user_in.username, user_in.password, user_in.full_name)
    return UserOut(id=user.id, username=user.username, full_name=user.full_name)


@app.post("/auth/token", response_model=Token)
async def issue_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return await login_for_access_token(form_data)


@app.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, username=current_user.username, full_name=current_user.full_name)


@app.post("/relationships", response_model=RelationshipOut, status_code=status.HTTP_201_CREATED)
async def add_relationship(
    username: str,
    alias: str | None = None,
    current_user: User = Depends(get_current_user),
):
    contact = await get_user_by_username(username)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    rel = await create_relationship(owner_id=current_user.id, contact_id=contact.id, alias=alias)
    contact_out = UserOut(id=contact.id, username=contact.username, full_name=contact.full_name)
    return RelationshipOut(id=rel.id, contact=contact_out, alias=rel.alias)


@app.get("/relationships", response_model=List[RelationshipOut])
async def list_relationships(current_user: User = Depends(get_current_user)):
    rels = await list_relationships_for_user(current_user.id)
    result: List[RelationshipOut] = []
    for rel in rels:
        contact = await get_user_by_id(rel.contact_id)
        if contact:
            contact_out = UserOut(id=contact.id, username=contact.username, full_name=contact.full_name)
            result.append(RelationshipOut(id=rel.id, contact=contact_out, alias=rel.alias))
    return result


@app.post("/calls", response_model=CallOut, status_code=status.HTTP_201_CREATED)
async def create_call_room_endpoint(
    call_in: CallCreate,
    current_user: User = Depends(get_current_user),
):
    if call_in.type == "one_to_one" and len(call_in.participant_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="one_to_one call must have exactly one participant",
        )
    room = await create_call_room(
        owner_id=current_user.id,
        participant_ids=call_in.participant_ids,
        call_type=call_in.type,
    )
    participant_ids = [p.user_id for p in room.participants]
    return CallOut(
        id=room.id,
        type=room.type,
        status=room.status,
        owner_id=room.owner_id,
        participant_ids=participant_ids,
    )


@app.post("/calls/{call_id}/join", response_model=CallOut)
async def join_call(
    call_id: int,
    current_user: User = Depends(get_current_user),
):
    room = await join_call_room(call_id, current_user.id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    participant_ids = [p.user_id for p in room.participants]
    return CallOut(
        id=room.id,
        type=room.type,
        status=room.status,
        owner_id=room.owner_id,
        participant_ids=participant_ids,
    )


@app.post("/calls/{call_id}/end", response_model=CallOut)
async def end_call(
    call_id: int,
    current_user: User = Depends(get_current_user),
):
    room = await get_call_room(call_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can end the call")
    room.status = "ended"
    participant_ids = [p.user_id for p in room.participants]
    return CallOut(
        id=room.id,
        type=room.type,
        status=room.status,
        owner_id=room.owner_id,
        participant_ids=participant_ids,
    )


class SignalingMessage(BaseModel):
    type: str
    call_id: Optional[int] = None
    from_user_id: Optional[int] = None
    to_user_id: Optional[int] = None
    payload: Optional[dict] = None


active_websockets: dict[int, WebSocket] = {}


@app.websocket("/ws/signaling")
async def signaling_ws(websocket: WebSocket):
    await websocket.accept()
    user_id: Optional[int] = None
    try:
        while True:
            raw = await websocket.receive_json()
            msg = SignalingMessage(**raw)
            if msg.type == "register" and msg.from_user_id is not None:
                user_id = msg.from_user_id
                active_websockets[user_id] = websocket
                continue
            if msg.to_user_id is not None and msg.to_user_id in active_websockets:
                await active_websockets[msg.to_user_id].send_json(raw)
    except WebSocketDisconnect:
        if user_id is not None:
            active_websockets.pop(user_id, None)