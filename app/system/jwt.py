import uuid

import jwt

from app.system.config import Config


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
        return uuid.UUID(obj.get("uuid", ""))
    except ValueError:
        return None


def is_valid_token(config: Config, token: str) -> bool:
    obj = parse_token(config, token)
    if obj is None:
        return False
    user = parse_user(obj)
    if user is None:
        return False
    return True
