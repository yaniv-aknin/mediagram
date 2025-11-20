import asyncio

import pytest
import pytest_asyncio
from aiohttp import web

from mediagram.agent.tools import http_fetch, set_driver_callbacks, set_tool_subdir
from mediagram.agent.callbacks import (
    ErrorMessage,
    ProgressMessage,
    StartMessage,
    SuccessMessage,
)


class MockCallbacks:
    def __init__(self):
        self.started = []
        self.progress = []
        self.successes = []
        self.errors = []

    async def on_tool_start(self, start: StartMessage, tool_id: str) -> None:
        self.started.append((start, tool_id))

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        self.progress.append((progress, tool_id))

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        self.successes.append((success, tool_id))

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        self.errors.append((error, tool_id))


@pytest_asyncio.fixture
async def http_server():
    """Start a test HTTP server."""

    async def handle_root(request):
        return web.Response(text="Hello World", content_type="text/plain")

    async def handle_json(request):
        return web.json_response({"status": "ok", "data": [1, 2, 3]})

    async def handle_headers(request):
        headers = dict(request.headers)
        return web.json_response({"received_headers": headers})

    async def handle_cookies(request):
        cookies = {name: request.cookies.get(name) for name in request.cookies}
        return web.json_response({"received_cookies": cookies})

    async def handle_not_found(request):
        return web.Response(status=404, text="Not Found")

    async def handle_large(request):
        return web.Response(body=b"x" * 100000, content_type="application/octet-stream")

    async def handle_timeout(request):
        await asyncio.sleep(0.5)
        return web.Response(text="Slow response")

    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/json", handle_json)
    app.router.add_get("/headers", handle_headers)
    app.router.add_get("/cookies", handle_cookies)
    app.router.add_get("/notfound", handle_not_found)
    app.router.add_get("/large", handle_large)
    app.router.add_get("/timeout", handle_timeout)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    yield base_url

    await runner.cleanup()


@pytest.mark.asyncio
async def test_fetch_basic(http_server, tmp_path):
    """Test basic fetch functionality."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(url=f"{http_server}/", output="test.txt")

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0
    assert "test.txt" in callbacks.successes[0][0].text
    assert "200" in callbacks.successes[0][0].text

    output_file = tmp_path / "test.txt"
    assert output_file.exists()
    assert output_file.read_text() == "Hello World"


@pytest.mark.asyncio
async def test_fetch_json(http_server, tmp_path):
    """Test fetching JSON data."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(url=f"{http_server}/json", output="data.json")

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0

    output_file = tmp_path / "data.json"
    assert output_file.exists()
    content = output_file.read_text()
    assert "ok" in content
    assert "[1, 2, 3]" in content or "[1,2,3]" in content


@pytest.mark.asyncio
async def test_fetch_auto_filename(http_server, tmp_path):
    """Test automatic filename detection from URL."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(url=f"{http_server}/json")

    assert len(callbacks.successes) == 1
    output_file = tmp_path / "json"
    assert output_file.exists()


@pytest.mark.asyncio
async def test_fetch_custom_headers(http_server, tmp_path):
    """Test sending custom headers."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/headers",
        output="headers.json",
        header=["X-Custom-Header: test-value", "X-Another: foo bar"],
    )

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0

    output_file = tmp_path / "headers.json"
    content = output_file.read_text()
    assert "X-Custom-Header" in content
    assert "test-value" in content
    assert "X-Another" in content
    assert "foo bar" in content


@pytest.mark.asyncio
async def test_fetch_user_agent(http_server, tmp_path):
    """Test custom user agent."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/headers",
        output="headers.json",
        user_agent="TestBot/1.0",
    )

    assert len(callbacks.successes) == 1

    output_file = tmp_path / "headers.json"
    content = output_file.read_text()
    assert "TestBot/1.0" in content


@pytest.mark.asyncio
async def test_fetch_invalid_header_format(http_server, tmp_path):
    """Test error handling for invalid header format."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/",
        output="test.txt",
        header=["InvalidHeaderNoColon"],
    )

    assert len(callbacks.errors) == 1
    assert len(callbacks.successes) == 0
    assert "Invalid header format" in callbacks.errors[0][0].text


@pytest.mark.asyncio
async def test_fetch_cookies(http_server, tmp_path):
    """Test cookie handling."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        "127.0.0.1\tFALSE\t/\tFALSE\t0\ttest_cookie\ttest_value\n"
        "127.0.0.1\tFALSE\t/\tFALSE\t0\tsession\tabc123\n"
    )

    await http_fetch(
        url=f"{http_server}/cookies",
        output="cookies.json",
        use_cookies=True,
    )

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0

    output_file = tmp_path / "cookies.json"
    content = output_file.read_text()
    assert "test_cookie" in content
    assert "test_value" in content
    assert "session" in content
    assert "abc123" in content


@pytest.mark.asyncio
async def test_fetch_cookies_file_missing(http_server, tmp_path):
    """Test error when cookies.txt is missing but use_cookies is explicitly True."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/",
        output="test.txt",
        use_cookies=True,
    )

    assert len(callbacks.errors) == 1
    assert len(callbacks.successes) == 0
    assert "cookies.txt not found" in callbacks.errors[0][0].text


@pytest.mark.asyncio
async def test_fetch_cookies_auto_detect(http_server, tmp_path):
    """Test that cookies are automatically used if cookies.txt exists."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        "127.0.0.1\tFALSE\t/\tFALSE\t0\tauto_cookie\tauto_value\n"
    )

    await http_fetch(
        url=f"{http_server}/cookies",
        output="cookies.json",
    )

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0

    output_file = tmp_path / "cookies.json"
    content = output_file.read_text()
    assert "auto_cookie" in content
    assert "auto_value" in content


@pytest.mark.asyncio
async def test_fetch_404_error(http_server, tmp_path):
    """Test handling of HTTP 404 error."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/notfound",
        output="notfound.txt",
    )

    assert len(callbacks.errors) == 1
    assert len(callbacks.successes) == 0
    assert "404" in callbacks.errors[0][0].text


@pytest.mark.asyncio
async def test_fetch_timeout(http_server, tmp_path):
    """Test request timeout handling."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/timeout",
        output="slow.txt",
        timeout=0.1,
    )

    assert len(callbacks.errors) == 1
    assert len(callbacks.successes) == 0
    assert "timed out" in callbacks.errors[0][0].text.lower()


@pytest.mark.asyncio
async def test_fetch_large_file(http_server, tmp_path):
    """Test downloading a larger file with progress updates."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url=f"{http_server}/large",
        output="large.bin",
    )

    assert len(callbacks.successes) == 1
    assert len(callbacks.errors) == 0
    assert len(callbacks.progress) > 0

    output_file = tmp_path / "large.bin"
    assert output_file.exists()
    assert output_file.stat().st_size == 100000


@pytest.mark.asyncio
async def test_fetch_progress_messages(http_server, tmp_path):
    """Test that progress messages are emitted during fetch."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(url=f"{http_server}/", output="test.txt")

    assert len(callbacks.progress) >= 3
    progress_texts = [p[0].text for p in callbacks.progress]
    assert any("Fetching" in text for text in progress_texts)
    assert any("Sending request" in text for text in progress_texts)
    assert any("Downloading" in text for text in progress_texts)


@pytest.mark.asyncio
async def test_fetch_invalid_url(tmp_path):
    """Test handling of invalid URL."""
    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)
    set_tool_subdir(tmp_path)

    await http_fetch(
        url="http://this-domain-does-not-exist-12345.invalid/",
        output="test.txt",
        timeout=2.0,
    )

    assert len(callbacks.errors) == 1
    assert len(callbacks.successes) == 0
