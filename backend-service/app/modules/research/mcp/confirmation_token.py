import hashlib
import hmac
import json
import time
from typing import Any, Dict, Set, Tuple
from app.core.config.settings import settings


class ConfirmationTokenValidator:
    """
    Validates single-use HMAC-SHA256 confirmation tokens for OPERATE MCP tools.
    """

    def __init__(self, secret: str = ""):
        self.secret = secret or getattr(settings, "MCP_CONFIRM_SECRET", "mcp_confirm_secret_key_32b_hex!")
        self._used_nonces: Set[str] = set()

    @staticmethod
    def compute_args_hash(args: Dict[str, Any]) -> str:
        """Stable sha256 hash of tool argument dictionary."""
        serialized = json.dumps(args, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def mint_token(self, tool_name: str, args: Dict[str, Any], nonce: str, ttl_seconds: int = 600) -> str:
        """Mints a token (used by Master backend). Format: {tool}:{argsHash}:{nonce}:{expiresAt}:{signature}"""
        args_hash = self.compute_args_hash(args)
        expires_at = int(time.time()) + ttl_seconds
        payload = f"{tool_name}:{args_hash}:{nonce}:{expires_at}"
        sig = hmac.new(self.secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload}:{sig}"

    def validate_token(self, token: str, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates signature, expiry, tool match, argument hash match, and nonce uniqueness.
        Returns: (is_valid, error_reason)
        """
        if not token:
            return False, "CONFIRMATION_REQUIRED: Confirmation token is required for OPERATE tools"

        parts = token.split(":")
        if len(parts) != 5:
            return False, "INVALID_TOKEN: Token format invalid"

        t_name, args_hash, nonce, exp_str, sig = parts

        # 1. Check tool name
        if t_name != tool_name:
            return False, f"TOKEN_MISMATCH: Token was minted for {t_name}, not {tool_name}"

        # 2. Check expiry
        try:
            expires_at = int(exp_str)
            if time.time() > expires_at:
                return False, "TOKEN_EXPIRED: Confirmation token has expired"
        except ValueError:
            return False, "INVALID_TOKEN: Invalid expiration timestamp"

        # 3. Check nonce uniqueness
        if nonce in self._used_nonces:
            return False, "TOKEN_ALREADY_USED: Confirmation token is single-use and has already been redeemed"

        # 4. Check args hash match
        expected_args_hash = self.compute_args_hash(args)
        if args_hash != expected_args_hash:
            return False, "ARGS_MISMATCH: Arguments do not match confirmed proposal payload"

        # 5. Check HMAC signature
        expected_payload = f"{tool_name}:{args_hash}:{nonce}:{exp_str}"
        expected_sig = hmac.new(
            self.secret.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            return False, "INVALID_SIGNATURE: HMAC signature verification failed"

        # Mark nonce as redeemed
        self._used_nonces.add(nonce)
        return True, "OK"


confirmation_validator = ConfirmationTokenValidator()
