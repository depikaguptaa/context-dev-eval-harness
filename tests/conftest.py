"""Shared fixtures: mock context.dev API on an ephemeral port."""

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mock_server import Handler  # noqa: E402
from context_eval import ContextDevClient, Observer  # noqa: E402


@pytest.fixture(scope="session")
def mock_base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/v1"
    server.shutdown()


@pytest.fixture()
def client(mock_base_url):
    return ContextDevClient(api_key="test-key", base_url=mock_base_url)


@pytest.fixture()
def observer(tmp_path):
    return Observer(log_path=tmp_path / "trace.jsonl")
