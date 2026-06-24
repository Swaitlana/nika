from mcp.server.fastmcp import FastMCP

from nika.service.kathara import KatharaFRRAPI
from nika.service.mcp_server.mcp_session_context import get_lab_name
from nika.utils.errors import safe_tool

# Initialize FastMCP server
mcp = FastMCP("kathara_bmv2_mcp_server")


@safe_tool
@mcp.tool()
def frr_get_bgp_conf(router_name: str) -> str:
    """Get the BGP configuration from the FRR router.

    Args:
        router_name (str): The name of the router.

    Returns:
        str: The BGP configuration from the FRR router.
    """
    kathara_api = KatharaFRRAPI(lab_name=get_lab_name())
    return kathara_api.frr_get_bgp_conf(router_name)


@safe_tool
@mcp.tool()
def frr_show_running_config(router_name: str) -> str:
    """Get the running configuration from the FRR router.

    Args:
        router_name (str): The name of the router.
    Returns:
        str: The running configuration from the FRR router.
    """
    kathara_api = KatharaFRRAPI(lab_name=get_lab_name())
    return kathara_api.frr_show_running_config(router_name)


@safe_tool
@mcp.tool()
def frr_show_ip_route(router_name: str) -> str:
    """Get the IP routing table from the FRR router.

    Args:
        router_name (str): The name of the router.
    Returns:
        str: The IP routing table from the FRR router.
    """
    kathara_api = KatharaFRRAPI(lab_name=get_lab_name())
    return kathara_api.frr_show_route(router_name)


@safe_tool
@mcp.tool()
def frr_get_ospf_conf(router_name: str) -> str:
    """Get the OSPF configuration from the FRR router.

    Args:
        router_name (str): The name of the router.

    Returns:
        str: The OSPF configuration from the FRR router.
    """
    kathara_api = KatharaFRRAPI(lab_name=get_lab_name())
    return kathara_api.frr_get_ospf_conf(router_name)


# FINE-condition underlay whitelist for frr_exec.
# MUST equal the frr_exec commands bundled by check_underlay in the COARSE
# server (kathara_coarse_mcp_server._RIP_EXEC_CMDS). Keeping these two lists
# identical is what makes the information-matched claim for the underlay layer
# verifiable by reading the two lists rather than trusting a runtime diff.
_FRR_EXEC_WHITELIST = frozenset({"show ip rip", "show ip rip status", "show interface"})


@safe_tool
@mcp.tool()
def frr_exec(router_name: str, command: str) -> str:
    """Execute a whitelisted read-only vtysh command on a FRR router.

    Only the fixed set of RIP/interface show-commands is permitted, matching
    the commands bundled by the COARSE check_underlay aggregate. Any other
    command is rejected so the two tool conditions stay information-matched.

    Args:
        router_name (str): The name of the router.
        command (str): The vtysh command (must be in the whitelist).

    Returns:
        str: The command output, or a rejection message if not whitelisted.
    """
    normalized = " ".join(command.strip().lower().split())
    if normalized not in _FRR_EXEC_WHITELIST:
        allowed = ", ".join(sorted(_FRR_EXEC_WHITELIST))
        return (
            f"[REJECTED] frr_exec is restricted to: {allowed}. "
            f"Received: {command!r}."
        )
    kathara_api = KatharaFRRAPI(lab_name=get_lab_name())
    return kathara_api.frr_exec(router_name, normalized)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
