"""HTTP routes for actions, approvals, receipts and agent tokens (C3), over the Dispatcher.

Who may call what: any authenticated caller may list the actions it can see and ask for an
authorization; only the OWNER session may approve/deny others' requests or manage tokens;
a caller may execute or cancel its own authorization (the owner may act on any). Approval itself
(step-up, authority) is enforced in :class:`Dispatcher`, not here.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Body, Depends, FastAPI, HTTPException

from .authn import Auth, Principal
from .dispatcher import BadRequest, Dispatcher, DispatchError, NotConsumable, NotPermitted


def _public_authorization(row: dict, *, owner: bool) -> dict:
    keep = ["id", "action_id", "state", "created_at", "expires_at", "authority", "approved_at", "idempotency_key",
            "retry_of", "previous_may_have_run", "caller"]
    out = {k: row[k] for k in keep if k in row}
    if owner:
        out["action_version"] = row["action_version"]
        out["destination"] = row["destination"]
    return out


def _public_receipt(row: dict, *, owner: bool) -> dict:
    keep = ["execution_id", "authorization_id", "action_id", "state", "status_code", "intent_at", "finished_at", "caller",
            "authority", "retry_of", "previous_may_have_run"]
    out = {k: row[k] for k in keep if k in row}
    out["evidence"] = row["evidence"] if owner else {k: v for k, v in row["evidence"].items() if k in ("error_class", "status_code")}
    if owner:
        out.update({k: row[k] for k in ("action_version", "destination", "approved_at", "approved_by", "dispatch_started_at") if k in row})
    return out


def register_action_routes(app: FastAPI, auth: Auth, dispatcher: Dispatcher, *, anyone: Callable[..., Principal],
                           owner: Callable[..., Principal]) -> None:
    def guard(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except NotPermitted as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except NotConsumable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except BadRequest as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except DispatchError as exc:  # pragma: no cover - future subclasses
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.get("/api/actions")
    def list_actions(p: Principal = Depends(anyone)) -> list[dict]:
        return [{"id": a.id, "name": a.name, "access": a.access, "approval": a.approval,
                 **({"scope": a.scope, "exposed": a.exposed} if p.is_owner else {})}
                for a in dispatcher.list_actions(p)]

    @app.post("/api/actions/{action_id}/authorizations")
    def request_authorization(action_id: str, body: dict = Body(default_factory=dict), p: Principal = Depends(anyone)) -> dict:
        row = guard(lambda: dispatcher.request_authorization(p, action_id, body.get("params"), body.get("idempotency_key")))
        return _public_authorization(row, owner=p.is_owner)

    @app.get("/api/authorizations/{authorization_id}")
    def get_authorization(authorization_id: str, p: Principal = Depends(anyone)) -> dict:
        row = guard(lambda: dispatcher.get_authorization(authorization_id))
        if not (p.is_owner or p.id == row["caller"]):
            raise HTTPException(status_code=404, detail="no such authorization")  # not 403: do not confirm it exists
        return _public_authorization(row, owner=p.is_owner)

    @app.post("/api/authorizations/{authorization_id}/approve")
    def approve(authorization_id: str, p: Principal = Depends(owner)) -> dict:
        return _public_authorization(guard(lambda: dispatcher.approve(p, authorization_id)), owner=True)

    @app.post("/api/authorizations/{authorization_id}/deny")
    def deny(authorization_id: str, p: Principal = Depends(anyone)) -> dict:
        return _public_authorization(guard(lambda: dispatcher.deny(p, authorization_id)), owner=p.is_owner)

    @app.post("/api/authorizations/{authorization_id}/execute")
    def execute(authorization_id: str, p: Principal = Depends(anyone)) -> dict:
        return _public_receipt(guard(lambda: dispatcher.execute(p, authorization_id)), owner=p.is_owner)

    @app.post("/api/executions/{execution_id}/retry")
    def retry(execution_id: str, p: Principal = Depends(anyone)) -> dict:
        return _public_authorization(guard(lambda: dispatcher.request_retry(p, execution_id)), owner=p.is_owner)

    @app.get("/api/receipts")
    def receipts(limit: int = 50, p: Principal = Depends(owner)) -> list[dict]:
        return [_public_receipt(r, owner=True) for r in dispatcher.list_receipts(max(1, min(limit, 200)))]

    @app.get("/api/receipts/{execution_id}")
    def receipt(execution_id: str, p: Principal = Depends(anyone)) -> dict:
        row = guard(lambda: dispatcher.receipt(execution_id))
        if not (p.is_owner or p.id == row["caller"]):
            raise HTTPException(status_code=404, detail="no such receipt")
        return _public_receipt(row, owner=p.is_owner)

    # ------------------------------------------------------------ agent tokens (owner only)

    @app.post("/api/agent-tokens")
    def create_token(body: dict = Body(...), p: Principal = Depends(owner)) -> dict:
        name, scopes = body.get("name"), body.get("scopes")
        if not isinstance(name, str) or not 1 <= len(name) <= 80 or not isinstance(scopes, list) or not scopes \
                or not all(isinstance(s, str) and 1 <= len(s) <= 120 for s in scopes):
            raise HTTPException(status_code=400, detail="name and a non-empty list of scope strings are required")
        ttl = body.get("ttl_s")
        if ttl is not None and (not isinstance(ttl, int) or isinstance(ttl, bool) or not 60 <= ttl <= 365 * 86400):
            raise HTTPException(status_code=400, detail="ttl_s must be between 60 seconds and one year")
        token_id, token = auth.tokens.create(name, scopes, ttl_s=ttl)
        return {"id": token_id, "token": token, "note": "shown once; only a hash is kept"}

    @app.get("/api/agent-tokens")
    def list_tokens(p: Principal = Depends(owner)) -> list[dict]:
        rows = auth.db.conn().execute("SELECT id,name,scopes,created_at,expires_at,revoked_at,last_used_at FROM agent_tokens ORDER BY created_at DESC")
        import json

        return [{**dict(r), "scopes": json.loads(r["scopes"])} for r in rows]

    @app.delete("/api/agent-tokens/{token_id}")
    def revoke_token(token_id: str, p: Principal = Depends(owner)) -> dict:
        if not auth.tokens.revoke(token_id):
            raise HTTPException(status_code=404, detail="no such active token")
        return {"ok": True}
