import base64
import hashlib
import hmac
import random
import re
import string
import struct
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from urllib.parse import parse_qs, quote, urlparse

import httpx

from app.core.crypto.secret_cipher import cipher
from app.core.logging.logger import logger
from app.modules.users.entity.upstox_config_entity import UpstoxConfig

Tuple_Profile = tuple[bool, dict[str, Any] | None]

BASE32_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
DEVICE_DETAILS = "platform=WEB|osName=Mac OS/10.15.7|osVersion=Chrome/140.0.0.0|appVersion=4.0.0|modelName=Chrome|manufacturer=Apple|uuid=3Z1IVTlV4rUUGbNp8KP0|userAgent=Upstox 3.0 Mozilla/5.0"


class UpstoxService:
    """
    Service handling Upstox automated zero-touch OAuth authentication and TOTP login.
    Mirrors the production-grade multi-step handshake from trading-engine.
    """

    UPSTOX_AUTH_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
    UPSTOX_PROFILE_URL = "https://api.upstox.com/v2/user/profile"

    @staticmethod
    def decode_base32(base32_str: str) -> bytes:
        """
        Tolerant Base32 decoder that ignores invalid characters (spaces, hyphens, etc.)
        matching UpstoxAuthServiceImpl logic.
        """
        clean = base32_str.strip().upper().replace("=", "").replace(" ", "").replace("-", "")
        buffer = 0
        bits_left = 0
        byte_array = bytearray()
        for char in clean:
            val = BASE32_CHARS.find(char)
            if val < 0:
                continue
            buffer = (buffer << 5) | val
            bits_left += 5
            if bits_left >= 8:
                byte_array.append((buffer >> (bits_left - 8)) & 0xFF)
                bits_left -= 8
        return bytes(byte_array)

    @classmethod
    def generate_totp(cls, secret: str, time_step: int | None = None) -> str:
        """
        Generates 6-digit RFC 6238 TOTP using standard Python cryptography.
        Tolerant to whitespace, hyphens, and non-base32 formatting.
        """
        if time_step is None:
            time_step = int(time.time() // 30)

        key = cls.decode_base32(secret)
        if not key:
            raise ValueError("Provided TOTP secret contains no valid Base32 characters.")

        msg = struct.pack(">Q", time_step)
        hmac_digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = hmac_digest[-1] & 0x0F
        code = (struct.unpack(">I", hmac_digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"

    @staticmethod
    def random_alphanumeric(length: int = 10) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    @staticmethod
    def extract_param(url: str, param_name: str) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        val = params.get(param_name)
        return val[0] if val else None

    async def authenticate(self, config: UpstoxConfig) -> dict[str, Any]:
        """
        Executes automated zero-touch authentication against Upstox APIs.
        Decrypts credentials and performs the complete 6-step handshake:
        1. Auth Dialog initialization (session cookie & internal user_id)
        2. OTP generation
        3. TOTP generation & verification
        4. 2FA PIN verification
        5. OAuth approval -> OAuth authorization code
        6. Token exchange -> Daily access token + user profile
        """
        if not config.apiKey:
            config.authStatus = "AUTH_FAILED"
            config.lastError = "Missing Upstox API Key"
            return {"success": False, "message": config.lastError}

        api_secret = cipher.decrypt(config.apiSecretEnc) if config.apiSecretEnc else ""
        pin = cipher.decrypt(config.pinEnc) if config.pinEnc else ""
        totp_secret = cipher.decrypt(config.totpSecretEnc) if config.totpSecretEnc else ""

        if not api_secret or not pin or not totp_secret or not config.mobile:
            config.authStatus = "AUTH_FAILED"
            config.lastError = (
                "Incomplete credentials. Mobile, PIN, TOTP secret, and API secret "
                "are required for automated authentication."
            )
            return {"success": False, "message": config.lastError}

        redirect_uri = config.redirectUri or f"http://localhost:8000/api/v1/upstox/callback/{config.userId}"

        # Check existing token validity first
        existing_token = cipher.decrypt(config.accessTokenEnc) if config.accessTokenEnc else ""
        now = datetime.now(UTC)
        if existing_token and config.tokenExpiresAt and config.tokenExpiresAt > now:
            profile_ok, profile_data = await self.fetch_profile(existing_token)
            if profile_ok and profile_data:
                config.authStatus = "VALID"
                config.lastAuthAt = now
                config.lastError = None
                config.upstoxUserId = profile_data.get("user_id") or config.upstoxUserId
                config.profileName = profile_data.get("user_name") or config.profileName
                config.email = profile_data.get("email") or config.email
                return {"success": True, "message": "Existing token is valid and active."}

        logger.info(f"[UPSTOX_AUTO_AUTH_START] Initiating automated zero-touch OAuth TOTP handshake for user [{config.userId}]...")

        request_id = f"WPRO-{self.random_alphanumeric(10)}"
        common_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Origin": "https://login.upstox.com",
            "Referer": "https://login.upstox.com",
            "x-device-details": DEVICE_DETAILS,
            "x-request-id": request_id,
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                # Step 1: Authorization dialog
                auth_dialog_url = (
                    "https://api.upstox.com/v2/login/authorization/dialog"
                    f"?response_type=code&client_id={quote(config.apiKey.trim() if hasattr(config.apiKey, 'trim') else config.apiKey.strip())}"
                    f"&redirect_uri={quote(redirect_uri.strip())}"
                )

                step1_resp = await client.get(auth_dialog_url, headers=common_headers)
                if step1_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step1_resp.text)
                    raise ValueError(f"Step 1 (Auth Dialog) failed: {err_msg}")

                final_url = str(step1_resp.url)
                user_id = self.extract_param(final_url, "user_id")
                client_id = self.extract_param(final_url, "client_id") or config.apiKey.strip()

                if not user_id:
                    raise ValueError("Step 1 failed: user_id parameter missing. Verify Upstox API Key and Redirect URI.")

                # Step 2: Generate OTP session token
                step2_url = "https://service.upstox.com/login/open/v6/auth/1fa/otp/generate"
                step2_body = {
                    "data": {
                        "mobileNumber": config.mobile.strip(),
                        "userId": user_id,
                    }
                }
                step2_resp = await client.post(step2_url, headers=common_headers, json=step2_body)
                if step2_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step2_resp.text)
                    raise ValueError(f"Step 2 (OTP Generation) failed: {err_msg}")

                step2_json = step2_resp.json()
                validate_otp_token = step2_json.get("data", {}).get("validateOTPToken")
                if not validate_otp_token:
                    raise ValueError(f"Step 2 failed: Missing validateOTPToken in response: {step2_resp.text}")

                # Step 3: Compute TOTP and verify
                current_totp = self.generate_totp(totp_secret)
                step3_url = "https://service.upstox.com/login/open/v4/auth/1fa/otp-totp/verify"
                step3_body = {
                    "data": {
                        "otp": current_totp,
                        "validateOtpToken": validate_otp_token,
                    }
                }
                step3_resp = await client.post(step3_url, headers=common_headers, json=step3_body)
                if step3_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step3_resp.text)
                    raise ValueError(f"Step 3 (TOTP Verification) failed: {err_msg}")

                # Step 4: 2FA PIN Submission
                encoded_pin = base64.b64encode(pin.strip().encode("utf-8")).decode("utf-8")
                step4_url = (
                    "https://service.upstox.com/login/open/v3/auth/2fa"
                    f"?client_id={quote(client_id)}"
                    f"&redirect_uri={quote('https://api-v2.upstox.com/login/authorization/redirect')}"
                )
                step4_body = {
                    "data": {
                        "twoFAMethod": "SECRET_PIN",
                        "inputText": encoded_pin,
                    }
                }
                step4_resp = await client.post(step4_url, headers=common_headers, json=step4_body)
                if step4_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step4_resp.text)
                    raise ValueError(f"Step 4 (PIN Verification) failed: {err_msg}")

                # Step 5: OAuth Authorize -> Obtain OAuth Code
                step5_url = (
                    "https://service.upstox.com/login/v2/oauth/authorize"
                    f"?client_id={quote(client_id)}"
                    f"&redirect_uri={quote('https://api-v2.upstox.com/login/authorization/redirect')}"
                    f"&requestId={quote(request_id)}"
                    "&response_type=code"
                )
                step5_body = {"data": {"userOAuthApproval": True}}
                step5_resp = await client.post(step5_url, headers=common_headers, json=step5_body)
                if step5_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step5_resp.text)
                    raise ValueError(f"Step 5 (OAuth Approval) failed: {err_msg}")

                step5_json = step5_resp.json()
                redirect_result_uri = step5_json.get("data", {}).get("redirectUri", "")
                auth_code = self.extract_param(redirect_result_uri, "code")
                if not auth_code:
                    raise ValueError(f"Step 5 failed: Missing authorization code in redirect response: {redirect_result_uri}")

                # Step 6: Exchange Authorization Code for Daily Access Token
                step6_url = self.UPSTOX_AUTH_TOKEN_URL
                step6_data = {
                    "code": auth_code,
                    "client_id": config.apiKey.strip(),
                    "client_secret": api_secret.strip(),
                    "redirect_uri": redirect_uri.strip(),
                    "grant_type": "authorization_code",
                }
                step6_headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }
                step6_resp = await client.post(step6_url, headers=step6_headers, data=step6_data)
                if step6_resp.status_code >= 400:
                    err_msg = self._extract_upstox_error(step6_resp.text)
                    raise ValueError(f"Step 6 (Token Exchange) failed: {err_msg}")

                token_json = step6_resp.json()
                access_token = token_json.get("access_token")
                upstox_user_id = token_json.get("user_id")
                user_name = token_json.get("user_name")
                email = token_json.get("email")

                if not access_token:
                    raise ValueError(f"Step 6 failed: Access token missing in response: {step6_resp.text}")

                # Success: Persist new encrypted token
                config.accessTokenEnc = cipher.encrypt(access_token)
                config.authStatus = "VALID"
                config.lastAuthAt = now
                config.tokenExpiresAt = now + timedelta(hours=24)
                config.lastError = None
                config.upstoxUserId = upstox_user_id or config.upstoxUserId
                config.profileName = user_name or config.profileName
                config.email = email or config.email

                logger.info(f"[UPSTOX_AUTO_AUTH_SUCCESS] Successfully generated new daily Upstox token for user: {user_name} (ID: {upstox_user_id})")
                return {
                    "success": True,
                    "message": f"Successfully authenticated as {user_name} (ID: {upstox_user_id})",
                    "data": {
                        "userId": upstox_user_id,
                        "userName": user_name,
                        "email": email,
                    },
                }

        except Exception as ex:
            config.authStatus = "AUTH_FAILED"
            config.lastError = str(ex)
            logger.error(f"[UPSTOX_AUTO_AUTH_FAILED] Upstox auth failed for user {config.userId}: {ex}")
            return {"success": False, "message": config.lastError}

    @staticmethod
    def _extract_upstox_error(response_body: str) -> str:
        try:
            import json
            data = json.loads(response_body)
            errors = data.get("errors")
            if isinstance(errors, list) and len(errors) > 0:
                msg = errors[0].get("message", "")
                code = errors[0].get("errorCode", "")
                return f"{msg} ({code})" if code else msg
            return data.get("message") or response_body[:200]
        except Exception:
            return response_body[:200]

    async def fetch_profile(self, access_token: str) -> Tuple_Profile:
        """Fetch profile from Upstox API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                }
                res = await client.get(self.UPSTOX_PROFILE_URL, headers=headers)
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    return True, data
                return False, None
        except Exception as e:
            logger.error(f"Error fetching Upstox profile: {e}")
            return False, None

    async def exchange_code(
        self,
        config: UpstoxConfig,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> dict[str, Any]:
        uri = redirect_uri or config.redirectUri or "http://localhost:8000/api/v1/upstox/callback"
        return await self.exchange_code_for_token(config, code, uri)

    async def exchange_code_for_token(
        self,
        config: UpstoxConfig,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchanges OAuth authorization code for Upstox access token."""
        api_secret = cipher.decrypt(config.apiSecretEnc) if config.apiSecretEnc else ""
        if not api_secret:
            raise ValueError("Upstox API Secret is not configured.")

        data = {
            "code": code,
            "client_id": config.apiKey,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.UPSTOX_AUTH_TOKEN_URL, data=data, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Upstox token exchange failed: {resp.text}")

            result = resp.json()
            access_token = result.get("access_token")
            if not access_token:
                raise ValueError(f"Missing access_token in Upstox response: {resp.text}")

            now = datetime.now(UTC)
            config.accessTokenEnc = cipher.encrypt(access_token)
            config.authStatus = "VALID"
            config.lastAuthAt = now
            config.tokenExpiresAt = now + timedelta(hours=24)
            config.lastError = None
            config.upstoxUserId = result.get("user_id")
            config.profileName = result.get("user_name")
            config.email = result.get("email")

            return result
