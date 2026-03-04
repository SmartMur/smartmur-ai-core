"""Home Assistant REST API client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from superpowers.ssh_fabric.base import SSHError


class HomeAssistantClient:
    def __init__(self, url: str, token: str):
        if not url or not token:
            raise SSHError("Home Assistant URL and token are required")
        self._url = url.rstrip("/")
        self._token = token

    def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
    ) -> dict | list:
        url = f"{self._url}/api/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise SSHError(
                f"Home Assistant API error {exc.code}: {exc.read().decode(errors='replace')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise SSHError(f"Home Assistant connection error: {exc.reason}") from exc

    def get_states(self) -> list[dict]:
        result = self._request("GET", "/states")
        if isinstance(result, list):
            return result
        return []

    def get_state(self, entity_id: str) -> dict:
        result = self._request("GET", f"/states/{entity_id}")
        if isinstance(result, dict):
            return result
        return {}

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict | None = None,
    ) -> dict:
        payload = {"entity_id": entity_id}
        if data:
            payload.update(data)
        result = self._request("POST", f"/services/{domain}/{service}", payload)
        if isinstance(result, dict):
            return result
        return {}

    def turn_on(self, entity_id: str) -> dict:
        domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
        return self.call_service(domain, "turn_on", entity_id)

    def turn_off(self, entity_id: str) -> dict:
        domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
        return self.call_service(domain, "turn_off", entity_id)

    def set_temperature(self, entity_id: str, temp: float) -> dict:
        return self.call_service("climate", "set_temperature", entity_id, {"temperature": temp})
