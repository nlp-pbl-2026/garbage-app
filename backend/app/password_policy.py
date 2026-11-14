"""Shared UTF-8 byte limit; bcrypt must never silently truncate passwords."""


def validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("パスワードはUTF-8で72バイト以内にしてください。")
    return value
