import re
from typing import Tuple

SECRET_NOTICE = "\n\n*(I removed something that looked like a secret. Do not share credentials here.)*"


class RedactionService:
    """
    Scans for and redacts credentials, API keys, TOTP secrets, tokens, and PINs.
    Enforces that sensitive data is never logged, stored in chat history, or passed into LLM context.
    """

    # Patterns to detect secrets
    API_KEY_PATTERN = re.compile(
        r"(?:api[_-]?key|secret|token|auth[_-]?token|bearer|access[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?",
        re.IGNORECASE,
    )
    JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")
    PIN_PATTERN = re.compile(r"(?:pin|passcode|code)\s*[:=]?\s*(\b\d{4,6}\b)", re.IGNORECASE)
    TOTP_KEY_PATTERN = re.compile(r"(?:totp|otp[_-]?secret)\s*[:=]\s*([a-zA-Z2-7]{16,32})", re.IGNORECASE)
    UPSTOX_SECRET_PATTERN = re.compile(r"[a-z0-9]{32,64}", re.IGNORECASE)  # generic hash/hex tokens when labelled

    @classmethod
    def redact_text(cls, text: str) -> Tuple[str, bool]:
        """
        Redacts any detected secrets in text.
        Returns (redacted_text, was_redacted).
        """
        if not text:
            return text, False

        redacted = False
        result = text

        # 1. API Keys & tokens
        def redact_key_match(m):
            nonlocal redacted
            redacted = True
            val = m.group(1)
            return m.group(0).replace(val, "[REDACTED_SECRET]")

        if cls.API_KEY_PATTERN.search(result):
            result = cls.API_KEY_PATTERN.sub(redact_key_match, result)

        # 2. JWT Tokens
        if cls.JWT_PATTERN.search(result):
            redacted = True
            result = cls.JWT_PATTERN.sub("[REDACTED_JWT_TOKEN]", result)

        # 3. TOTP secrets
        def redact_totp(m):
            nonlocal redacted
            redacted = True
            val = m.group(1)
            return m.group(0).replace(val, "[REDACTED_TOTP_KEY]")

        if cls.TOTP_KEY_PATTERN.search(result):
            result = cls.TOTP_KEY_PATTERN.sub(redact_totp, result)

        # 4. PINs (4-6 digits next to PIN or passcode)
        def redact_pin(m):
            nonlocal redacted
            redacted = True
            val = m.group(1)
            return m.group(0).replace(val, "[REDACTED_PIN]")

        if cls.PIN_PATTERN.search(result):
            result = cls.PIN_PATTERN.sub(redact_pin, result)

        return result, redacted

    @classmethod
    def redact_dict(cls, data: dict) -> Tuple[dict, bool]:
        """Deeply traverses and redacts dict values."""
        if not isinstance(data, dict):
            return data, False

        was_redacted = False
        new_data = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ["secret", "password", "pin", "token", "apikey", "api_key", "totp"]):
                new_data[k] = "[REDACTED]"
                was_redacted = True
            elif isinstance(v, str):
                red_v, did_red = cls.redact_text(v)
                new_data[k] = red_v
                if did_red:
                    was_redacted = True
            elif isinstance(v, dict):
                red_d, did_red = cls.redact_dict(v)
                new_data[k] = red_d
                if did_red:
                    was_redacted = True
            elif isinstance(v, list):
                new_list = []
                for item in v:
                    if isinstance(item, str):
                        red_i, did_red = cls.redact_text(item)
                        new_list.append(red_i)
                        if did_red:
                            was_redacted = True
                    elif isinstance(item, dict):
                        red_i, did_red = cls.redact_dict(item)
                        new_list.append(red_i)
                        if did_red:
                            was_redacted = True
                    else:
                        new_list.append(item)
                new_data[k] = new_list
            else:
                new_data[k] = v

        return new_data, was_redacted
