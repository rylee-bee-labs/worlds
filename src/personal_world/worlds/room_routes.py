"""Owner-only routes for room/0 providers: what the rooms are, which of their actions to adopt, and
answering a need through the same C3 authority as any other write."""

from __future__ import annotations

from typing import Callable

from fastapi import Body, Depends, FastAPI, HTTPException

from .authn import Principal
from .config_store import ConfigInvalid, EtagMismatch
from .dispatcher import BadRequest, NotConsumable, NotPermitted
from .room0 import RoomService


def register_room_routes(app: FastAPI, rooms: RoomService, *, owner: Callable[..., Principal]) -> None:
    @app.get("/api/rooms")
    def list_rooms(p: Principal = Depends(owner)) -> list[dict]:
        return rooms.rooms()

    @app.post("/api/rooms/{provider_id}/changed")
    def room_changed(provider_id: str, p: Principal = Depends(owner)) -> dict:
        """The room signalled a change (its ``/changed`` ping): invalidate its cached snapshot.

        Sends nothing to the room and dispatches nothing — the next read refetches. A provider that is
        not a room0 room is a 404.
        """
        if not rooms.invalidate(provider_id):
            raise HTTPException(status_code=404, detail="no such room")
        return {"id": provider_id, "invalidated": True}

    @app.get("/api/rooms/{provider_id}/actions")
    def action_candidates(provider_id: str, p: Principal = Depends(owner)) -> list[dict]:
        found = rooms.candidates(provider_id)
        if found is None:
            raise HTTPException(status_code=404, detail="no such room")
        return found

    @app.post("/api/rooms/{provider_id}/actions/{room_action_id}/adopt")
    def adopt(provider_id: str, room_action_id: str, p: Principal = Depends(owner)) -> dict:
        """Make a room's action callable (never exposed to agents, approval always). Sends nothing."""
        try:
            action = rooms.adopt(provider_id, room_action_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except (ConfigInvalid, EtagMismatch) as exc:
            raise HTTPException(status_code=409, detail=f"cannot adopt: {exc}") from None
        if action is None:
            raise HTTPException(status_code=404, detail="no such room action")
        return {"action_id": action.id, "exposed": action.exposed, "approval": action.approval, "access": action.access}

    @app.post("/api/rooms/{provider_id}/actions/{room_action_id}/answer")
    def answer_need(provider_id: str, room_action_id: str, body: dict = Body(default_factory=dict),
                    p: Principal = Depends(owner)) -> dict:
        """Answer a room need by running its ALREADY-ADOPTED action through the C3 dispatcher (owner, CSRF).

        request_authorization -> approve -> consume -> dispatch: the same lifecycle as any write, at most
        one network attempt. An unadopted action (or one the room no longer offers) is refused; nothing is
        ever sent without a consumed authorization, and there is no dispatcher-free path to the room.
        """
        params = body.get("params")
        if params is not None and not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="params must be an object")
        idempotency_key = body.get("idempotency_key")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise HTTPException(status_code=400, detail="idempotency_key must be a string")
        dispatcher = getattr(app.state, "dispatcher", None)
        if dispatcher is None:
            raise HTTPException(status_code=503, detail="the action authority is not available")
        try:
            receipt = rooms.answer(provider_id, room_action_id, params, p, dispatcher, idempotency_key=idempotency_key,
                                   project_home_approval_id=body.get("project_home_approval_id"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except NotPermitted as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except NotConsumable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except BadRequest as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        if receipt is None:
            raise HTTPException(status_code=404, detail="no such adopted room action")
        return receipt
