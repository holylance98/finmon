"""Безопасность и защита персональных данных (FR-6, NFR-5).

Реализует: обезличивание ФИО для отчётов (152-ФЗ), хеширование паролей
(PBKDF2), журналирование операций с hash-цепочкой (защита от подмены лога).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

PBKDF2_ROUNDS = 200_000
MIN_PASSWORD_LEN = 10


def mask_name(full_name: str) -> str:
    """Иванов Иван Иванович -> Ив***ов И.И."""
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if not parts:
        return ""
    surname = parts[0]
    masked = surname[:2] + "***" + (surname[-2:] if len(surname) > 4 else "")
    initials = "".join(f"{p[0].upper()}." for p in parts[1:3])
    return f"{masked} {initials}".strip()


def mask_card(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 8:
        return "***"
    return f"{digits[:4]} **** **** {digits[-4:]}"


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if not check_password_strength(password):
        raise ValueError("Пароль не соответствует политике сложности")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), PBKDF2_ROUNDS)
    return hmac.compare_digest(digest.hex(), stored_hash)


def check_password_strength(password: str) -> bool:
    return (len(password) >= MIN_PASSWORD_LEN
            and any(c.isdigit() for c in password)
            and any(c.isupper() for c in password)
            and any(c.islower() for c in password))


@dataclass
class AuditEntry:
    ts: str
    actor: str
    action: str
    details: str
    prev_hash: str
    hash: str = ""

    def compute_hash(self) -> str:
        payload = f"{self.ts}|{self.actor}|{self.action}|{self.details}|{self.prev_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditLog:
    """Append-only журнал с hash-цепочкой: каждая запись связана с предыдущей."""

    entries: List[AuditEntry] = field(default_factory=list)

    def add(self, actor: str, action: str, details: str = "") -> AuditEntry:
        prev = self.entries[-1].hash if self.entries else "GENESIS"
        entry = AuditEntry(
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            actor=actor, action=action, details=details, prev_hash=prev,
        )
        entry.hash = entry.compute_hash()
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = "GENESIS"
        for entry in self.entries:
            if entry.prev_hash != prev or entry.hash != entry.compute_hash():
                return False
            prev = entry.hash
        return True

    def to_json(self) -> str:
        return json.dumps([vars(e) for e in self.entries], ensure_ascii=False, indent=2)
