import os

from nika.config import MCP_SERVER_DIR

# Keyword sets that trigger inclusion of each optional Kathara MCP server.
_FRR_KEYWORDS = frozenset({"bgp", "ospf", "rip", "frr", "routing"})
_BMV2_KEYWORDS = frozenset({"p4", "bmv2", "sdn", "bloom", "mpls", "int", "counter"})
_TELEMETRY_KEYWORDS = frozenset({"telemetry"})


def select_diagnosis_servers(scenario_name: str, problem_names: list[str]) -> list[str]:
    """Return the set of Kathara MCP server names needed for *scenario*.

    Tool granularity is selected by the ``TOOL_GRANULARITY`` environment
    variable (``fine`` | ``coarse``; default ``fine``):

    * ``coarse`` -> only ``kathara_coarse_mcp_server`` (the three per-layer
      aggregate tools). The atomic base/frr servers are intentionally NOT
      loaded, so the agent cannot bypass the aggregates.
    * ``fine`` (default) -> ``kathara_base_mcp_server`` plus the specialised
      servers selected by keyword signals in the scenario/problem names
      (tokens split on ``_`` and ``-``).

    Parameters
    ----------
    scenario_name:
        E.g. ``"dc_clos_bgp"`` or ``"p4_counter"``.
    problem_names:
        E.g. ``["bgp_session_down"]``.
    """
    granularity = os.environ.get("TOOL_GRANULARITY", "fine").strip().lower()

    if granularity == "coarse":
        return ["kathara_coarse_mcp_server"]
    if granularity != "fine":
        raise ValueError(
            f"TOOL_GRANULARITY must be 'fine' or 'coarse', got {granularity!r}."
        )

    combined = (scenario_name + " " + " ".join(problem_names)).lower()
    tokens = set(combined.replace("_", " ").replace("-", " ").split())

    servers = ["kathara_base_mcp_server"]
    if tokens & _FRR_KEYWORDS:
        servers.append("kathara_frr_mcp_server")
    if tokens & _BMV2_KEYWORDS:
        servers.append("kathara_bmv2_mcp_server")
    if tokens & _TELEMETRY_KEYWORDS:
        servers.append("kathara_telemetry_mcp_server")
    return servers


class MCPServerConfig:
    def __init__(self, session_id: str):
        if not session_id:
            raise ValueError("session_id is required to start MCP servers.")
        self.mcp_server_dir = str(MCP_SERVER_DIR)
        self.session_id = session_id

    def _server_env(self) -> dict[str, str]:
        return {
            "NIKA_SESSION_ID": self.session_id,
        }

    def load_config(self, if_submit: bool = False) -> dict:
        if if_submit:
            config = {
                "task_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/task_mcp_server.py"],
                    "transport": "stdio",
                },
            }
        else:
            config = {
                "kathara_base_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/kathara_base_mcp_server.py"],
                    "transport": "stdio",
                },
                "kathara_frr_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/kathara_frr_mcp_server.py"],
                    "transport": "stdio",
                },
                "kathara_bmv2_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/kathara_bmv2_mcp_server.py"],
                    "transport": "stdio",
                },
                "kathara_telemetry_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/kathara_telemetry_mcp_server.py"],
                    "transport": "stdio",
                },
                "kathara_coarse_mcp_server": {
                    "command": "python3",
                    "args": [f"{self.mcp_server_dir}/kathara_coarse_mcp_server.py"],
                    "transport": "stdio",
                },
            }

        for server in config.values():
            server["env"] = self._server_env()
        return config

    def load_filtered_config(self, server_names: list[str]) -> dict:
        """Diagnosis config restricted to *server_names*.

        Useful when only a subset of Kathara MCP servers is relevant for a
        given scenario (e.g. skip bmv2 tools for a pure routing problem).
        Unknown names in *server_names* are silently ignored.
        """
        full = self.load_config(if_submit=False)
        return {k: v for k, v in full.items() if k in server_names}
