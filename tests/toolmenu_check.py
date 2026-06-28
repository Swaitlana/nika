# phase1_toolmenu_check.py
# Confirms the FINE/COARSE wiring. No lab or fault injection needed —
# just run with your nika env active, from the repo root.
import asyncio
import importlib
import os


def list_tools_for(module_path):
    """Import a server module and return the names of its registered MCP tools."""
    mod = importlib.import_module(module_path)
    tools = asyncio.run(mod.mcp.list_tools())
    return sorted(t.name for t in tools)


def main():
    base = "nika.service.mcp_server.kathara_base_mcp_server"
    frr = "nika.service.mcp_server.kathara_frr_mcp_server"
    coarse = "nika.service.mcp_server.kathara_coarse_mcp_server"

    print("=== COARSE server tool menu ===")
    coarse_tools = list_tools_for(coarse)
    print(coarse_tools)

    print("\n=== FINE server tool menus ===")
    base_tools = list_tools_for(base)
    frr_tools = list_tools_for(frr)
    print("base:", base_tools)
    print("frr :", frr_tools)

    print("\n=== CHECKS ===")
    expected_coarse = {"check_overlay", "check_underlay", "check_endpoint"}
    print("COARSE == 3 aggregates only:",
          set(coarse_tools) == expected_coarse,
          "" if set(coarse_tools) == expected_coarse else f"(got {set(coarse_tools)})")

    banned = {"exec_shell", "exec_shell_dual", "cat_file"}
    leaked = banned & set(base_tools)
    print("escape hatches gone from FINE:", not leaked,
          "" if not leaked else f"(LEAKED: {leaked})")

    print("get_tunnel_status in FINE base:", "get_tunnel_status" in base_tools)
    endpoints = {"get_reachability", "ping_pair", "curl_web_test", "get_host_net_config"}
    print("endpoint checks in FINE base:", endpoints.issubset(base_tools),
          "" if endpoints.issubset(base_tools) else f"(missing {endpoints - set(base_tools)})")


if __name__ == "__main__":
    main()