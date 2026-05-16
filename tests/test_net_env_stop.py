import unittest
from unittest.mock import patch

from nika.workflows.net_env_stop import stop_net_env


class FakeStore:
    def __init__(self, sessions: list[dict]):
        self._sessions = sessions

    def list_running_sessions(self) -> list[dict]:
        return [s for s in self._sessions if s.get("status") == "running"]

    def get_session(self, session_id: str) -> dict:
        for session in self._sessions:
            if session["session_id"] == session_id:
                return session
        raise FileNotFoundError(session_id)


class NetEnvStopTest(unittest.TestCase):
    def test_stop_all_calls_each_running_record(self) -> None:
        sessions = [
            {"session_id": "sid-1", "status": "running"},
            {"session_id": "sid-2", "status": "running"},
        ]
        fake_store = FakeStore(sessions)
        with (
            patch("nika.workflows.net_env_stop.SessionStore", return_value=fake_store),
            patch("nika.workflows.net_env_stop._stop_session_record") as stop_record,
        ):
            stop_net_env(stop_all=True)
            self.assertEqual(stop_record.call_count, 2)

    def test_stop_specific_requires_running_status(self) -> None:
        sessions = [{"session_id": "sid-finished", "status": "finished"}]
        fake_store = FakeStore(sessions)
        with patch("nika.workflows.net_env_stop.SessionStore", return_value=fake_store):
            with self.assertRaises(FileNotFoundError):
                stop_net_env(session_id="sid-finished")


if __name__ == "__main__":
    unittest.main()
