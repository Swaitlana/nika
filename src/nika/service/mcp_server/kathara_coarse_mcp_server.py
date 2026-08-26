"""kathara_coarse_mcp_server.py

COARSE tool-granularity condition for the MCP tool-granularity experiment.

Instead of exposing atomic per-protocol tools, this server exposes three
per-layer AGGREGATE tools that mirror how SD-WAN management platforms surface
health (per-layer rollups rather than raw commands):

    - check_overlay   : WireGuard tunnel state across every VPN endpoint
    - check_underlay  : RIP/FRR routing state across every router
    - check_endpoint  : reachability, host config, sockets, counters, web test

Each aggregate bundles exactly the atomic calls that make up its layer in the
FINE condition, so the two conditions remain information-matched (Phase 3).

Controls preserved from the experiment design:
    - The raw escape hatches (exec_shell / exec_shell_dual / cat_file) are
      intentionally NOT exposed here, matching their removal from FINE.
    - The underlay bundle (_RIP_EXEC_CMDS plus the two named FRR calls) MUST
      stay equal to the FINE frr surface; keep them in sync.

The server is wired: select_diagnosis_servers returns this server alone when
TOOL_GRANULARITY=coarse, and the atomic base/frr servers are not loaded.
"""

from mcp.server.fastmcp import FastMCP

from nika.service.kathara import KatharaAPIALL as KatharaAPI
from nika.service.mcp_server.mcp_session_context import get_lab_name
from nika.utils.errors import safe_tool

# Initialize FastMCP server
mcp = FastMCP(name="kathara_coarse_mcp_server", host="127.0.0.1", port=8003, log_level="INFO")


# ---------------------------------------------------------------------------
# Underlay bundle definition.
#
# This MUST equal the underlay surface exposed in the FINE condition:
#   frr_show_ip_route + frr_show_running_config (named tools)        +
#   frr_exec restricted to the three show-commands listed below.
# If the FINE frr_exec whitelist changes, change this list too, or the
# information-matched claim for the underlay layer breaks.
# ---------------------------------------------------------------------------
_RIP_EXEC_CMDS = ["show ip rip", "show ip rip status", "show interface"]

# Web service port for the endpoint web test (apache listens on :80 in this
# scenario; see confs/web_server_*/etc/apache2/ports.conf).
_WEB_PORT = 80


def _discover_nodes(kathara_api):
    """Classify lab nodes by role using image-based detection.

    Returns (routers, vpn_hosts, client_hosts, web_hosts).

    Uses load_machines() rather than get_hosts(): get_hosts() filters on
    'base' in image and would return an EMPTY list for this scenario, whose
    hosts use the kathara/nika-wireguard image. load_machines() classifies
    by image and name, so wireguard hosts land in .hosts / .servers correctly.
    """
    kathara_api.load_machines()
    routers = list(kathara_api.routers)
    client_hosts = list(kathara_api.hosts)
    vpn_hosts = list(kathara_api.servers.get("vpn", []))
    web_hosts = list(kathara_api.servers.get("web", []))
    return routers, vpn_hosts, client_hosts, web_hosts


@safe_tool
@mcp.tool()
def check_overlay() -> str:
    """OVERLAY health rollup: WireGuard tunnel status on every VPN endpoint.

    Bundles the per-host overlay check (`wg show`) across all WireGuard-capable
    hosts (VPN server, internal clients, web servers). For each host this
    reports peer public keys, handshake recency, and transfer counters.

    Returns:
        str: `wg show` output for every endpoint, labelled per host.
    """
    kathara_api = KatharaAPI(lab_name=get_lab_name())
    _, vpn_hosts, client_hosts, web_hosts = _discover_nodes(kathara_api)
    wg_hosts = vpn_hosts + client_hosts + web_hosts

    sections = []
    for host in wg_hosts:
        out = kathara_api.exec_cmd(host_name=host, command="wg show")
        sections.append(f"===== {host} : wg show =====\n{out}")
    return "\n\n".join(sections) if sections else "No WireGuard endpoints found."


@safe_tool
@mcp.tool()
def check_underlay() -> str:
    """UNDERLAY health rollup: RIP/FRR routing state on every router.

    For each FRR router this bundles exactly the FINE underlay surface:
      - IP routing table          (frr_show_ip_route)
      - running configuration     (frr_show_running_config)
      - RIP neighbor table        (`show ip rip`)
      - RIP status                (`show ip rip status`)
      - interface state           (`show interface`)

    Returns:
        str: Routing diagnostics for every router, labelled per router/command.
    """
    kathara_api = KatharaAPI(lab_name=get_lab_name())
    routers, _, _, _ = _discover_nodes(kathara_api)

    sections = []
    for r in routers:
        parts = [
            f"===== {r} =====",
            f"--- ip route ---\n{kathara_api.frr_show_route(r)}",
            f"--- running-config ---\n{kathara_api.frr_show_running_config(r)}",
        ]
        for cmd in _RIP_EXEC_CMDS:
            parts.append(f"--- {cmd} ---\n{kathara_api.frr_exec(r, cmd)}")
        sections.append("\n".join(parts))
    return "\n\n".join(sections) if sections else "No FRR routers found."


@safe_tool
@mcp.tool()
async def check_endpoint() -> str:
    """ENDPOINT health rollup: reachability, host config, sockets, counters, web.

    Bundles the symptom-layer atomic checks:
      - all-pairs reachability matrix     (get_reachability)
      - per-host network config           (get_host_net_config) for each endpoint
      - listening sockets                 (netstat -tuln) for every node
      - per-interface counters            (ip -s addr) for every node
      - application-layer web test: each internal client curls each web service
        over the VPN tunnel (curl_web_test to the web server's inner tunnel IP)

    The all-pairs matrix subsumes targeted ping_pair information, so ping_pair
    is not separately bundled.

    Sockets and counters are bundled to match FINE's netstat and
    ip_addr_statistics tools, both of which accept any node name including
    routers. Both conditions therefore expose the same surface (Phase 3).

    DESIGN DECISION (confirmed): the web test loops client x web-server and
    curls each web service over the tunnel. This is the superset choice.

    Returns:
        str: Endpoint diagnostics, labelled per section.
    """
    kathara_api = KatharaAPI(lab_name=get_lab_name())
    routers, vpn_hosts, client_hosts, web_hosts = _discover_nodes(kathara_api)
    endpoint_hosts = vpn_hosts + client_hosts + web_hosts
    all_nodes = endpoint_hosts + routers

    sections = []

    # 1) all-pairs reachability
    reach = await kathara_api.get_reachability()
    sections.append(f"===== reachability matrix =====\n{reach}")

    # 2) per-host network config
    for host in endpoint_hosts:
        cfg = kathara_api.get_host_net_config(host_name=host)
        sections.append(f"===== {host} : net config =====\n{cfg}")

    # 2b) listening sockets (matches FINE's netstat tool, callable on any node)
    for node in all_nodes:
        sock = kathara_api.netstat(host_name=node)
        sections.append(f"===== {node} : netstat -tuln =====\n{sock}")

    # 2c) per-interface counters (matches FINE's ip_addr_statistics tool,
    #     also callable on any node)
    for node in all_nodes:
        stats = kathara_api.ip_addr_statistics(host_name=node)
        sections.append(f"===== {node} : ip -s addr =====\n{stats}")

    # 3) application-layer web test over the tunnel
    for web in web_hosts:
        # the web service is published on the host's inner (wg0) tunnel address
        try:
            web_ip = kathara_api.get_host_ip(web, iface="wg0")
        except Exception as exc:  # noqa: BLE001 - diagnostic tool, surface the error
            sections.append(f"===== {web} : web test skipped =====\nCould not resolve wg0 IP: {exc}")
            continue
        if not web_ip:
            sections.append(f"===== {web} : web test skipped =====\nNo wg0 IP found.")
            continue
        url = f"http://{web_ip}:{_WEB_PORT}"
        for client in client_hosts:
            out = kathara_api.curl_web_test(host_name=client, url=url, times=3)
            sections.append(f"===== {client} -> {web} ({url}) =====\n{out}")

    return "\n\n".join(sections) if sections else "No endpoint information found."

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")