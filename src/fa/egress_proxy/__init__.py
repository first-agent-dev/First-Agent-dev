"""Egress-injection proxy for First-Agent secret isolation (ADR-12, Option C).

The proxy is the **architectural boundary** for LLM provider keys: those keys
live ONLY inside this component's process (in a *separate* container from the
agent). The agent (``first-agent`` container) targets the proxy instead of the
real provider and carries no provider key — only a fa→proxy bootstrap token.
A fully compromised agent can therefore *use* a key (make a metered call via the
proxy) but can never *read* its value: the key is on no file, env var, or
process the agent's uid/namespace can reach.

Design constraints honored:

* No new third-party deps — stdlib ``http.server`` + ``urllib`` only.
* First-Agent is non-streaming (single POST → single JSON response), so the
  proxy is a simple request/response forwarder; no SSE handling required.
* The proxy **strips** any inbound ``Authorization`` / ``x-api-key`` and injects
  the real one from its own mounted secrets file, so the agent never supplies
  (and cannot influence) provider auth.
"""

from __future__ import annotations

from fa.egress_proxy.routing import (
    ProxyConfigError,
    ProxyRoute,
    RouteTable,
    build_route_table,
    route_name_for,
)

__all__ = [
    "ProxyConfigError",
    "ProxyRoute",
    "RouteTable",
    "build_route_table",
    "route_name_for",
]
