"""Commands for fault injection."""

import typer

failure_app = typer.Typer(help="Inject faults into the running lab.")


@failure_app.command("list")
def failure_list() -> None:
    """Print injectable problem ids."""
    from nika.orchestrator.problems.prob_pool import list_avail_problem_names

    for name in sorted(list_avail_problem_names()):
        typer.echo(name)


@failure_app.command("inject")
def failure_inject(
    problems: list[str] = typer.Argument(
        ...,
        metavar="PROBLEM",
        help="One or more problem ids (see `nika failure list`).",
    ),
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Inject one or more faults for the current session."""
    from nika.workflows.failure_inject import inject_failure

    if not problems:
        raise typer.BadParameter("Provide at least one problem name.")
    try:
        inject_failure(problems, session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
