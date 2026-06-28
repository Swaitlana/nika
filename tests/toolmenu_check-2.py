# phase1_switch_and_whitelist_check.py
# Tests (a) the TOOL_GRANULARITY file switch, (b) frr_exec whitelist rejection,
# and (c) the cross-file invariant: FINE whitelist == COARSE underlay bundle.
# No lab needed — the reject path and the switch both run before any lab call.
import importlib
import os


def check_switch():
    print("=== (a) TOOL_GRANULARITY switch -> which server FILES load ===")
    mod = importlib.import_module("agent.utils.mcp_servers")
    f = mod.select_diagnosis_servers
    scenario, probs = "rip_small_internet_vpn", ["host_vpn_membership_missing"]

    os.environ.pop("TOOL_GRANULARITY", None)
    default = f(scenario, probs)
    os.environ["TOOL_GRANULARITY"] = "fine"
    fine = f(scenario, probs)
    os.environ["TOOL_GRANULARITY"] = "coarse"
    coarse = f(scenario, probs)
    os.environ["TOOL_GRANULARITY"] = "COARSE"   # case-insensitivity
    coarse_uc = f(scenario, probs)

    print("default (no env) :", default)
    print("fine             :", fine)
    print("coarse           :", coarse)
    print("COARSE (caps)    :", coarse_uc)

    print("  default == fine:", default == fine)
    print("  coarse is coarse-server only:", coarse == ["kathara_coarse_mcp_server"])
    print("  case-insensitive:", coarse == coarse_uc)
    print("  no atomic servers leak into coarse:",
          not ({"kathara_base_mcp_server", "kathara_frr_mcp_server"} & set(coarse)))

    os.environ["TOOL_GRANULARITY"] = "bogus"
    try:
        f(scenario, probs)
        print("  bogus value rejected: False (NO error raised — BAD)")
    except ValueError as e:
        print("  bogus value rejected:", True, f"({e})")
    finally:
        os.environ.pop("TOOL_GRANULARITY", None)


def check_whitelist_rejection():
    print("\n=== (b) frr_exec rejects off-whitelist commands ===")
    frr = importlib.import_module("nika.service.mcp_server.kathara_frr_mcp_server")
    should_reject = [
        "show running-config",
        "configure terminal",
        "show ip bgp",
        "show ip rip; show running-config",   # injection-style
        "",
    ]
    for cmd in should_reject:
        out = frr.frr_exec("router1", cmd)
        ok = isinstance(out, str) and out.startswith("[REJECTED]")
        print(f"  reject {cmd!r:40} -> {ok}")


def check_whitelist_matches_bundle():
    print("\n=== (c) INVARIANT: FINE whitelist == COARSE underlay bundle ===")
    frr = importlib.import_module("nika.service.mcp_server.kathara_frr_mcp_server")
    coarse = importlib.import_module("nika.service.mcp_server.kathara_coarse_mcp_server")
    fine_set = set(frr._FRR_EXEC_WHITELIST)
    coarse_set = set(coarse._RIP_EXEC_CMDS)
    print("  FINE  _FRR_EXEC_WHITELIST:", sorted(fine_set))
    print("  COARSE _RIP_EXEC_CMDS    :", sorted(coarse_set))
    match = fine_set == coarse_set
    print("  MATCH (must be True):", match)
    if not match:
        print("  >>> DRIFT: only in FINE:", fine_set - coarse_set,
              "| only in COARSE:", coarse_set - fine_set)


if __name__ == "__main__":
    check_switch()
    check_whitelist_rejection()
    check_whitelist_matches_bundle()