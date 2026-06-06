"""Pre-send validation and audit logging for LLM-generated letters.

Every generated letter goes through `validate_letter` before being sent to BOSS.
Failures are logged but not sent, preventing garbage / error strings from
reaching recruiters. Every attempt (sent or not) is appended to a JSONL file
for later review and prompt iteration.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(os.getenv("LETTER_LOG_PATH", "./logs/letters.jsonl"))

MIN_LEN = int(os.getenv("LETTER_MIN_LEN", "30"))
MAX_LEN = int(os.getenv("LETTER_MAX_LEN", "800"))

# Substrings that indicate an LLM error or a refusal — never safe to send.
BLACKLIST: tuple[str, ...] = (
    "Error",
    "Traceback",
    "抱歉，作为",
    "抱歉，我是",
    "I cannot",
    "I apologize",
    "I'm an AI",
    "I'm sorry",
    "As an AI",
    "```",
)

_CJK_RE = re.compile(r"[一-鿿]")


@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_letter(letter: str) -> ValidationResult:
    """Return ok=False with reasons if the letter is unsafe to send."""
    reasons: list[str] = []
    n = len(letter)
    if n < MIN_LEN:
        reasons.append(f"too_short ({n} < {MIN_LEN})")
    if n > MAX_LEN:
        reasons.append(f"too_long ({n} > {MAX_LEN})")
    if not _CJK_RE.search(letter):
        reasons.append("no_chinese_characters")
    for needle in BLACKLIST:
        if needle in letter:
            reasons.append(f"blacklist:{needle!r}")
            break
    return ValidationResult(ok=not reasons, reasons=reasons)


def log_attempt(
    *,
    provider: str,
    model: str,
    job_description: str,
    letter: str,
    validation: ValidationResult,
    dry_run: bool,
    sent: bool,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "dry_run": dry_run,
        "validation_ok": validation.ok,
        "validation_reasons": validation.reasons,
        "sent": sent,
        "letter_len": len(letter),
        "job_description": job_description,
        "letter": letter,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
