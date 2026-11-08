import logging
import threading
import time

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)

import httpx
import pytest

from models.ollama import (
    OllamaChatModelProvider,
)


logger = logging.getLogger(__name__)


class UnresponsiveOllamaHandler(BaseHTTPRequestHandler):

    request_received = threading.Event()
    release_request = threading.Event()

    def do_POST(self):

        self.request_received.set()

        self.release_request.wait(timeout=30.0)

    def log_message(self, format, *args):
        pass

class StreamingOllamaHandler(BaseHTTPRequestHandler):

    request_received = threading.Event()
    release_request = threading.Event()

    def do_POST(self):

        self.request_received.set()

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/x-ndjson",
        )

        self.end_headers()

        start_time = time.monotonic()

        try:

            while not self.release_request.is_set():

                elapsed_seconds = (
                    time.monotonic() - start_time
                )

                if elapsed_seconds >= 5.0:
                    break

                self.wfile.write(
                    b'{"message":{"role":"assistant",'
                    b'"content":"working"},"done":false}\n'
                )

                self.wfile.flush()

                time.sleep(0.25)

        except (
            BrokenPipeError,
            ConnectionResetError,
        ):
            pass

    def log_message(self, format, *args):
        pass


@pytest.fixture
def unresponsive_ollama_server():

    UnresponsiveOllamaHandler.request_received.clear()
    UnresponsiveOllamaHandler.release_request.clear()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        UnresponsiveOllamaHandler,
    )

    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    server_thread.start()

    try:

        host, port = server.server_address

        yield f"http://{host}:{port}"

    finally:

        UnresponsiveOllamaHandler.release_request.set()

        server.shutdown()
        server.server_close()

        server_thread.join(timeout=5.0)


@pytest.fixture
def streaming_ollama_server():

    StreamingOllamaHandler.request_received.clear()
    StreamingOllamaHandler.release_request.clear()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        StreamingOllamaHandler,
    )

    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    server_thread.start()

    try:

        host, port = server.server_address

        yield f"http://{host}:{port}"

    finally:

        StreamingOllamaHandler.release_request.set()

        server.shutdown()
        server.server_close()

        server_thread.join(timeout=5.0)


def test_ollama_request_timeout(
    unresponsive_ollama_server,
):

    timeout_seconds = 2.0

    provider = OllamaChatModelProvider(
        model_name="timeout-test",
        base_url=unresponsive_ollama_server,
        temperature=0.2,
        timeout_seconds=timeout_seconds,
    )

    model = provider.create()

    start_time = time.monotonic()

    with pytest.raises(httpx.TimeoutException):

        model.invoke(
            "Test request timeout."
        )

    elapsed_seconds = (
        time.monotonic() - start_time
    )

    logger.info(
        "Ollama timeout test completed in %.2f seconds.",
        elapsed_seconds,
    )

    assert UnresponsiveOllamaHandler.request_received.is_set()

    assert elapsed_seconds >= timeout_seconds

    assert elapsed_seconds < 10.0


def test_ollama_streaming_timeout(
    streaming_ollama_server,
):

    timeout_seconds = 2.0

    provider = OllamaChatModelProvider(
        model_name="timeout-test",
        base_url=streaming_ollama_server,
        temperature=0.2,
        timeout_seconds=timeout_seconds,
    )

    model = provider.create()

    start_time = time.monotonic()

    try:

        model.invoke(
            "Test streaming timeout."
        )

    except httpx.TimeoutException:

        pytest.fail(
            "HTTP timeout occurred despite "
            "continuous streaming data."
        )

    elapsed_seconds = (
        time.monotonic() - start_time
    )

    logger.info(
        "Ollama streaming test completed "
        "in %.2f seconds.",
        elapsed_seconds,
    )

    assert StreamingOllamaHandler.request_received.is_set()

    assert elapsed_seconds >= 4.5

    assert elapsed_seconds < 10.0