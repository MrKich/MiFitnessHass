"""
Mi Fitness cloud API client.

Endpoint: POST https://{region}.hlth.io.mi.com/app/v1/data/get_fitness_data_by_time
          (cn region serves the same API from the bare host hlth.io.mi.com,
          see _api_host below)

The legacy incremental endpoint ``get_fitness_data_by_watermark`` is no longer
used: Xiaomi stopped appending to that stream for some accounts (it freezes on
a fixed date), while ``get_fitness_data_by_time`` keeps returning current data.
Requests are therefore windowed by time and paginated with ``next_key``.

Auth: RC4 + SHA1 MAC signing scheme (signed body, see _post)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import time

import requests
from Crypto.Cipher import ARC4

from .const import LIVE_DATA_KEYS

_LOGGER = logging.getLogger(__name__)


def _rand_hex(n: int = 32) -> str:
    """Random lowercase hex string of length n."""
    return "".join(random.choices("0123456789abcdef", k=n))


# Per-install device fingerprint baked into the UA. Xiaomi only uses these two
# hashes to identify the client instance, so a random value generated once at
# import is fine — never hardcode a real device id here.
USER_AGENT = f"Android-14-3.55.0i-samsung-SM-F721B-{_rand_hex()}-{_rand_hex()}"


class MiFitnessApiError(Exception):
    """Base API error."""


class MiFitnessAuthError(MiFitnessApiError):
    """Authentication / token expired error."""


# ── Crypto ──────────────────────────────────────────────────────────────────

def _gen_nonce() -> str:
    """8 random bytes (signed int64) + 4 bytes floor(millis/60000) → base64."""
    b = (random.getrandbits(64) - 2**63).to_bytes(8, "big", signed=True)
    b += int(time.time() * 1000 / 60000).to_bytes(4, "big")
    return base64.b64encode(b).decode()


def _signed_nonce(ssecurity: str, nonce: str) -> str:
    """SHA256(b64decode(ssecurity) + b64decode(nonce)) → base64."""
    h = hashlib.sha256()
    h.update(base64.b64decode(ssecurity))
    h.update(base64.b64decode(nonce))
    return base64.b64encode(h.digest()).decode()


def _fc4_sign(method: str, path: str, params: dict, security: str) -> str:
    """
    Request signing:
      SHA1(METHOD & /path & k=v & ... & security) → base64
    Params sorted lexicographically.
    """
    parts = [method.upper(), path]
    for k, v in sorted(params.items()):
        parts.append(f"{k}={v}")
    parts.append(security)
    return base64.b64encode(
        hashlib.sha1("&".join(parts).encode("utf-8")).digest()
    ).decode()


def _encrypt_rc4(key_b64: str, text: str) -> str:
    r = ARC4.new(base64.b64decode(key_b64))
    r.encrypt(bytes(1024))  # skip first 1024 bytes
    return base64.b64encode(r.encrypt(text.encode("utf-8"))).decode()


def _decrypt_rc4(key_b64: str, payload_b64: str) -> bytes:
    r = ARC4.new(base64.b64decode(key_b64))
    r.encrypt(bytes(1024))
    return r.encrypt(base64.b64decode(payload_b64))


# ── Client ───────────────────────────────────────────────────────────────────

class MiFitnessClient:
    """Xiaomi health data client for hlth.io.mi.com (sync, run in executor)."""

    PATH_BY_TIME = "/app/v1/data/get_fitness_data_by_time"
    MAX_PAGES_PER_KEY = 60

    def __init__(
        self,
        user_id: str,
        c_user_id: str,
        ssecurity: str,
        service_token: str,
        region: str = "us",
        phone_id: str = "",
    ) -> None:
        self.user_id       = user_id
        self.c_user_id     = c_user_id
        self.ssecurity     = ssecurity
        self.service_token = service_token
        self.region        = region
        self.phone_id      = phone_id   # kept for config compatibility, unused

        # cn region: cn.hlth.io.mi.com does not resolve; the bare host serves CN data
        self._api_host = "hlth.io.mi.com" if region == "cn" else f"{region}.hlth.io.mi.com"
        self._base = f"https://{self._api_host}"
        self._session = self._make_session()

    def update_service_token(self, new_token: str) -> None:
        """Hot-swap serviceToken without rebuilding the full client."""
        self.service_token = new_token
        domain = self._api_host
        self._session.cookies.set("serviceToken", new_token, domain=domain)

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent":   USER_AGENT,
            "HandleParams": "true",
            "region_tag":   self.region,
        })
        domain = self._api_host
        s.cookies.set("userId",       self.user_id,       domain=domain)
        s.cookies.set("cUserId",      self.c_user_id,     domain=domain)
        s.cookies.set("serviceToken", self.service_token, domain=domain)
        s.cookies.set("locale",       "de_de",            domain=domain)
        _LOGGER.debug(
            "API session: region=%s user_id=%s c_user_id=%s ssec_len=%d tok_len=%d",
            self.region, self.user_id, self.c_user_id,
            len(self.ssecurity), len(self.service_token),
        )
        return s

    def _post(self, path: str, payload: dict) -> dict:
        """Signed POST, decrypt RC4 response, return the ``result`` object."""
        nonce  = _gen_nonce()
        snonce = _signed_nonce(self.ssecurity, nonce)

        form = {"data": json.dumps(payload, separators=(",", ":"))}
        form["rc4_hash__"] = _fc4_sign("POST", path, form, snonce)
        encrypted = {k: _encrypt_rc4(snonce, v) for k, v in form.items()}
        encrypted["signature"] = _fc4_sign("POST", path, encrypted, snonce)
        encrypted["_nonce"] = nonce

        try:
            r = self._session.post(self._base + path, data=encrypted, timeout=25)
        except requests.RequestException as exc:
            raise MiFitnessApiError(f"Network error: {exc}") from exc

        if r.status_code == 401:
            _LOGGER.error("HTTP 401 path=%s body=%s", path, r.text[:300])
            raise MiFitnessAuthError("serviceToken expired (HTTP 401)")
        if r.status_code != 200:
            raise MiFitnessApiError(f"HTTP {r.status_code}: {r.text[:200]}")

        try:
            body = json.loads(_decrypt_rc4(snonce, r.text.strip()))
        except Exception as exc:
            raise MiFitnessApiError(
                f"Decrypt/parse failed: {exc} raw={r.text[:100]}"
            ) from exc

        code = body.get("code", -1)
        if code != 0:
            raise MiFitnessApiError(f"API error code {code} on {path}: {body}")
        return body.get("result") or {}

    # ── Public methods ───────────────────────────────────────────────────────

    def get_data_by_time(
        self,
        key: str,
        start_ts: int,
        end_ts: int,
        next_key: str | None = None,
    ) -> dict:
        """One page of records for ``key`` in [start_ts, end_ts]."""
        payload: dict = {
            "start_time": int(start_ts),
            "end_time":   int(end_ts),
            "key":        key,
        }
        if next_key:
            payload["next_key"] = next_key
        return self._post(self.PATH_BY_TIME, payload)

    def fetch_key_window(self, key: str, start_ts: int, end_ts: int) -> list[dict]:
        """All records for one key in the window, following ``next_key``."""
        items: list[dict] = []
        next_key: str | None = None
        for _ in range(self.MAX_PAGES_PER_KEY):
            result = self.get_data_by_time(key, start_ts, end_ts, next_key)
            page = result.get("data_list") or []
            items.extend(page)
            cursor = result.get("next_key")
            if not result.get("has_more") or not cursor:
                break
            next_key = str(cursor)
            time.sleep(0.15)   # be gentle: avoid hammering / rate-limit
        return items

    def fetch_window(
        self,
        start_ts: int,
        end_ts: int,
        keys: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[list[dict], bool]:
        """
        Fetch every configured metric for [start_ts, end_ts].

        Returns (items, errored). ``errored`` is True when at least one key
        failed, so the caller does not mistake a partial result for a complete
        one. Items keep the shape produced by the cloud:
        {sid, key, time, value (JSON string), zone_offset, zone_name, update_time}.
        """
        keys = tuple(keys or LIVE_DATA_KEYS)
        items: list[dict] = []
        errored = False
        for key in keys:
            try:
                items.extend(self.fetch_key_window(key, start_ts, end_ts))
            except MiFitnessAuthError:
                raise   # let the coordinator handle 401 → silent refresh
            except MiFitnessApiError as exc:
                errored = True
                _LOGGER.warning("fetch window key=%s failed: %s", key, exc)
        return items, errored
