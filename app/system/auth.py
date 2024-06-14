import uuid
from typing import TypedDict
from urllib.parse import unquote

import jwt
import sqlalchemy as sa

from app.system.config import Config
from app.system.db.base import SessionTable
from app.system.db.db import DBConnector


NOT_A_UUID = ""


def parse_token(config: Config, token: str) -> dict[str, str] | None:
    try:
        return jwt.decode(
            token,
            config["appsecret"],
            algorithms=["HS256"],
            audience="user:known")
    except jwt.exceptions.InvalidTokenError:
        return None


def parse_user(obj: dict[str, str]) -> uuid.UUID | None:
    try:
        return uuid.UUID(obj.get("uuid", NOT_A_UUID))
    except ValueError:
        return None


def is_valid_token(config: Config, token: str) -> uuid.UUID | None:
    obj = parse_token(config, token)
    if obj is None:
        return None
    return parse_user(obj)


SessionInfo = TypedDict('SessionInfo', {
    "uuid": uuid.UUID,
    "name": str,
})


def get_session(
        platform_db: DBConnector, session_str: str) -> SessionInfo | None:
    session_str = unquote(session_str).removeprefix("s:")
    eos = session_str.find(".")
    if eos >= 0:
        session_str = session_str[:eos]
    with platform_db.get_session() as session:
        stmt = sa.select(SessionTable.sess)
        stmt = stmt.where(SessionTable.sid == session_str)
        obj = session.execute(stmt).scalar_one_or_none()
        if obj is None:
            return None
        rights = obj.get("rights")
        if rights is None:
            return None
        if int(rights) < 2:
            return None
        name = obj.get("username")
        user = parse_user(obj)
        if name is None or user is None:
            return None
    return {
        "name": name,
        "uuid": user,
    }
