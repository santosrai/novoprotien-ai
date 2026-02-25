import json
import os
import hashlib
import re
from typing import Any, Dict, List, Optional


LOG_AI = os.getenv("LOG_AI", "1") != "0"

_REDACT_KEY_PATTERNS = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "cookie",
    "proxy",
)

_SUMMARIZE_KEY_PATTERNS = (
    "usertext",
    "user_text",
    "input",
    "prompt",
    "content",
    "sequence",
    "pdb",
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"(^|[^A-Za-z0-9])sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(^|[^A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$"),  # JWT-like
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),  # credentialed URLs
)


def _hash_preview(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ")):
        return True
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _redact_payload(payload: Any, key_hint: str = "") -> Any:
    """Redact sensitive values while preserving useful debugging shape."""
    key = (key_hint or "").lower()

    if isinstance(payload, dict):
        return {k: _redact_payload(v, str(k)) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_redact_payload(v, key_hint) for v in payload]
    if isinstance(payload, tuple):
        return tuple(_redact_payload(v, key_hint) for v in payload)
    if isinstance(payload, set):
        return sorted(_redact_payload(v, key_hint) for v in payload)

    if isinstance(payload, bytes):
        return f"<redacted bytes len={len(payload)}>"

    if isinstance(payload, str):
        if any(pattern in key for pattern in _REDACT_KEY_PATTERNS):
            return "<redacted>"
        if any(pattern in key for pattern in _SUMMARIZE_KEY_PATTERNS):
            return f"<redacted len={len(payload)} sha256={_hash_preview(payload)}>"
        if _looks_like_secret(payload):
            return "<redacted secret>"
        return payload

    return payload


def _truncate(value: Any, max_len: int = 8000) -> str:
    try:
        if isinstance(value, str):
            s = value
        else:
            s = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "... [truncated]"
    return s


def _safe_for_console(s: str) -> str:
    """Ensure string can be printed on consoles with limited encoding (e.g. Windows cp1252)."""
    return s.encode("ascii", errors="replace").decode("ascii")


def log_line(section: str, message: Any) -> None:
    if not LOG_AI:
        return
    from datetime import datetime

    ts = datetime.utcnow().isoformat()
    sanitized_message = _redact_payload(message)
    output = f"[{section}] {ts} {_truncate(sanitized_message)}"
    try:
        print(output)
    except UnicodeEncodeError:
        print(_safe_for_console(output))


def get_text_from_completion(completion: Any) -> str:
    """OpenRouter API returns message.content as a list of blocks.
    Join all text blocks into a single string.
    """
    try:
          # Check for OpenAI response format
        if hasattr(completion, 'choices') and completion.choices:
            return completion.choices[0].message.content or ""

        # OpenRouter API response format (for Anthropic models)
        content = completion.content or []
        parts = []
        for block in content:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    except Exception:
        return str(getattr(completion, "content", ""))


def strip_code_fences(text: str) -> str:
    import re

    t = text.strip()
    t = re.sub(r"^```[a-zA-Z0-9]*\n?", "", t)
    t = re.sub(r"```\s*$", "", t)
    return t.strip()


def extract_code_and_text(content: str) -> tuple:
    """Extract code and text from content that may contain code fences.
    
    Returns:
        tuple: (code, text) where code is the content inside code fences,
               and text is everything outside code fences.
    """
    import re
    
    if not content or not content.strip():
        return "", ""
    
    # Pattern to match code blocks: ```language\n...code...\n``` or ```language...code...```
    # More flexible: matches with or without newline after opening fence
    code_block_pattern = r"```(?:[a-zA-Z0-9]+)?\n?(.*?)```"
    
    # Extract all code blocks
    code_blocks = re.findall(code_block_pattern, content, re.DOTALL)
    code = "\n\n".join([block.strip() for block in code_blocks if block.strip()]).strip()
    
    # Remove code blocks from content to get text
    # Use a more comprehensive pattern that includes the fences themselves
    text = re.sub(r"```[a-zA-Z0-9]*\n?.*?```", "", content, flags=re.DOTALL).strip()
    
    # Clean up extra whitespace
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    
    return code, text


def spell_fix(input_text: str) -> str:
    replacements = {
        "strucutre": "structure",
        "visulize": "visualize",
        "colour": "color",
        "protien": "protein",
    }
    fixed = input_text
    for k, v in replacements.items():
        fixed = fixed.replace(k, v)
    return fixed


def trim_history(history: Optional[List[Dict[str, Any]]], max_turns: int = 6, max_chars: int = 8000) -> List[Dict[str, Any]]:
    if not history:
        return []
    trimmed = history[-max_turns:]
    # Cap serialized size
    s = _truncate(trimmed, max_len=max_chars)
    try:
        # Reparse to ensure valid JSON shape after truncation attempt
        json.loads(s)
        return trimmed
    except Exception:
        return trimmed

