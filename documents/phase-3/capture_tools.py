#!/usr/bin/env python3
"""capture_tools.py

Phase-3 evidence capture: calls NIKA's MCP tool functions directly (unwrapped
from their `@safe_tool`/`@mcp.tool()` decorators, since `mcp.tool()` returns
the original function unmodified and `safe_tool` already converts internal
exceptions to `{"error": ...}` dicts) and dumps their raw output to a text
file for manual FINE vs. COARSE comparison.
In simple terms :- 
It reads the lab and writes down what every tool says. Nothing else — it never breaks anything or fixes anything.

Finds running lab session automatically.
Asks NIKA which machines exist and sorts them into groups: routers, VPN server, clients, web servers. It uses the same sorting code COARSE uses, so both sides look at the same machines.
Runs the three COARSE tools.
Runs the FINE tools, one call per machine.
Writes everything to tools-<label>.txt with a heading above each result showing

Usage:
    uv run python documents/phase-3/capture_tools.py <label>

Writes to documents/phase-3/tools-<label>.txt

Requires exactly one running NIKA session (as created by `nika env run ...`).
This script only reads state — it never injects or restores faults.
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <label>", file=sys.stderr)
    sys.exit(1)

LABEL = sys.argv[1]
OUT_PATH = Path(__file__).resolve().parent / f"tools-{LABEL}.txt"

from nika.utils.session_store import SessionStore  # noqa: E402

# get_lab_name() (used inside every tool function) reads NIKA_SESSION_ID from
# the environment, so it must be set before the tool modules are imported and
# called, exactly as the MCP subprocess harness does for a live agent.
session = SessionStore().get_unique_running_session()
SESSION_ID = session["session_id"]
LAB_NAME = session.get("lab_name") or (session.get("scenario_params") or {}).get("lab_name")
os.environ["NIKA_SESSION_ID"] = SESSION_ID

from nika.service.kathara import KatharaAPIALL as KatharaAPI  # noqa: E402
from nika.service.mcp_server import kathara_base_mcp_server as fine  # noqa: E402
from nika.service.mcp_server import kathara_coarse_mcp_server as coarse  # noqa: E402

out_lines: list[str] = []


def log(text: str = "") -> None:
    out_lines.append(text)


def section(title: str) -> None:
    log()
    log("=" * 80)
    log(title)
    log("=" * 80)


def call(title: str, fn, *args, **kwargs):
    """Call a tool function, label it with its exact args, and record output
    or the exception, without ever crashing the capture run."""
    section(title)
    try:
        if asyncio.iscoroutinefunction(fn):
            result = asyncio.run(fn(*args, **kwargs))
        else:
            result = fn(*args, **kwargs)
        log(str(result))
    except Exception as exc:  # noqa: BLE001 - this script only observes, never crashes
        log(f"[EXCEPTION] {type(exc).__name__}: {exc}")
        log(traceback.format_exc())


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    log(f"timestamp: {now}")
    log(f"session_id: {SESSION_ID}")
    log(f"lab_name: {LAB_NAME}")
    log(f"label: {LABEL}")

    # Discover nodes once, the same way the COARSE server does, so FINE and
    # COARSE below cover exactly the same machines.
    kathara_api = KatharaAPI(lab_name=LAB_NAME)
    routers, vpn_hosts, client_hosts, web_hosts = coarse._discover_nodes(kathara_api)
    endpoint_hosts = vpn_hosts + client_hosts + web_hosts
    wg_hosts = vpn_hosts + client_hosts + web_hosts
    all_nodes = endpoint_hosts + routers

    log()
    log(f"routers: {routers}")
    log(f"vpn_hosts: {vpn_hosts}")
    log(f"client_hosts: {client_hosts}")
    log(f"web_hosts: {web_hosts}")
    log(f"wg_hosts (overlay): {wg_hosts}")
    log(f"endpoint_hosts (net config): {endpoint_hosts}")
    log(f"all_nodes (netstat/ip_addr): {all_nodes}")

    # ------------------------------------------------------------------
    # COARSE section
    # ------------------------------------------------------------------
    section("COARSE SECTION")

    call("COARSE: check_overlay()", coarse.check_overlay)
    call("COARSE: check_underlay()", coarse.check_underlay)
    call("COARSE: check_endpoint()", coarse.check_endpoint)

    # ------------------------------------------------------------------
    # FINE section
    # ------------------------------------------------------------------
    section("FINE SECTION")

    call("FINE: get_reachability()", fine.get_reachability)

    for host in wg_hosts:
        call(f"FINE: get_tunnel_status(host_name={host!r})", fine.get_tunnel_status, host_name=host)

    for host in endpoint_hosts:
        call(f"FINE: get_host_net_config(host_name={host!r})", fine.get_host_net_config, host_name=host)

    for host in all_nodes:
        call(f"FINE: netstat(host_name={host!r})", fine.netstat, host_name=host)

    for host in all_nodes:
        call(f"FINE: ip_addr_statistics(host_name={host!r})", fine.ip_addr_statistics, host_name=host)

    # curl_web_test: each client -> each web server's wg0 address, matching
    # what COARSE's check_endpoint does.
    for web in web_hosts:
        try:
            web_ip = kathara_api.get_host_ip(web, iface="wg0")
        except Exception as exc:  # noqa: BLE001
            section(f"FINE: curl_web_test(...) skipped for web={web!r}")
            log(f"[EXCEPTION] Could not resolve wg0 IP: {exc}")
            continue
        if not web_ip:
            section(f"FINE: curl_web_test(...) skipped for web={web!r}")
            log("No wg0 IP found.")
            continue
        url = f"http://{web_ip}:80"
        for client in client_hosts:
            call(
                f"FINE: curl_web_test(host_name={client!r}, url={url!r}, times=3)",
                fine.curl_web_test,
                host_name=client,
                url=url,
                times=3,
            )

    for host in wg_hosts:
        call(
            f'FINE: systemctl_ops(host_name={host!r}, service_name="wg-quick@wg0", operation="status")',
            fine.systemctl_ops,
            host_name=host,
            service_name="wg-quick@wg0",
            operation="status",
        )

    OUT_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
