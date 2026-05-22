from __future__ import annotations

import json
import time
from itertools import count
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


class CdpError(RuntimeError):
    pass


class CdpLocator:
    def __init__(self, page: CdpPage, selector: str) -> None:
        self._page = page
        self._selector = selector

    def inner_text(self, timeout: int = 3000) -> str:
        deadline = time.time() + timeout / 1000
        while True:
            text = self._page.evaluate(
                "(selector) => document.querySelector(selector)?.innerText || ''",
                self._selector,
            )
            if text or time.time() >= deadline:
                return text
            time.sleep(0.1)


class CdpPage:
    def __init__(self, cdp_url: str) -> None:
        import websocket  # noqa: PLC0415

        self._base_url = cdp_url.rstrip("/")
        target = self._create_target("about:blank")
        self._target_id = target["id"]
        self._ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        self._ids = count(1)
        self._send("Page.enable")
        self._send("Runtime.enable")

    def _create_target(self, url: str) -> dict:
        endpoint = urljoin(f"{self._base_url}/", f"json/new?{quote(url, safe='')}")
        request = Request(endpoint, method="PUT")
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _send(self, method: str, params: dict | None = None) -> dict:
        msg_id = next(self._ids)
        self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") != msg_id:
                continue
            if "error" in message:
                raise CdpError(f"{method}: {message['error']}")
            return message.get("result", {})

    def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000) -> None:
        self._send("Page.navigate", {"url": url})
        self._wait_for_ready_state(timeout, interactive_ok=wait_until == "domcontentloaded")

    def _wait_for_ready_state(self, timeout: int, interactive_ok: bool) -> None:
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            state = self.evaluate("() => document.readyState")
            if state == "complete" or (interactive_ok and state == "interactive"):
                return
            time.sleep(0.1)
        raise CdpError("Timed out waiting for document ready state")

    def wait_for_timeout(self, ms: int) -> None:
        time.sleep(ms / 1000)

    def evaluate(self, expression: str, arg=None):
        if arg is None:
            call_expression = f"({expression})()"
        else:
            call_expression = f"({expression})({json.dumps(arg)})"
        result = self._send(
            "Runtime.evaluate",
            {
                "expression": call_expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        remote = result.get("result", {})
        if "value" in remote:
            return remote["value"]
        if remote.get("subtype") == "null":
            return None
        return None

    @property
    def url(self) -> str:
        return self.evaluate("() => window.location.href") or ""

    def locator(self, selector: str) -> CdpLocator:
        return CdpLocator(self, selector)

    def close(self) -> None:
        try:
            self._ws.close()
        finally:
            with urlopen(f"{self._base_url}/json/close/{self._target_id}", timeout=10):
                pass
