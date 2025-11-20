from collections.abc import AsyncGenerator
import time
from typing import Annotated

import httpx
from typer import Option

from ..callbacks import ErrorMessage, ProgressMessage, SuccessMessage
from . import get_tool_subdir, tool


@tool
async def http_fetch(
    url: str,
    output: Annotated[
        str | None,
        Option(help="Output filename (defaults to URL's filename or 'output')"),
    ] = None,
    use_cookies: Annotated[
        bool,
        Option(
            help="Use cookies from cookies.txt (default: true if cookies.txt exists)"
        ),
    ] = None,
    user_agent: Annotated[
        str | None,
        Option(help="Custom User-Agent header"),
    ] = None,
    header: Annotated[
        list[str] | None,
        Option(help="Additional headers as 'Name: Value' pairs"),
    ] = None,
    timeout: Annotated[
        float,
        Option(help="Request timeout in seconds"),
    ] = 30.0,
) -> AsyncGenerator[ProgressMessage | SuccessMessage | ErrorMessage, None]:
    """Fetch a URL via HTTP GET and save to file."""
    subdir = get_tool_subdir()

    yield ProgressMessage(text=f"Fetching {url}", completion_ratio=0.1)

    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    if header:
        for h in header:
            if ": " not in h:
                yield ErrorMessage(
                    text=f"Invalid header format: {h}. Expected 'Name: Value'"
                )
                return
            name, value = h.split(": ", 1)
            headers[name] = value

    cookies = None
    cookies_file = subdir / "cookies.txt"
    if use_cookies is None:
        use_cookies = cookies_file.exists()

    if use_cookies:
        if not cookies_file.exists():
            yield ErrorMessage(text=f"cookies.txt not found in {subdir}")
            return

        cookies = httpx.Cookies()
        with cookies_file.open() as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    domain, _, path, secure, expires, name, value = parts[:7]
                    cookies.set(name, value, domain=domain, path=path)

    if not output:
        output = url.rstrip("/").split("/")[-1] or "output"
        if "?" in output:
            output = output.split("?")[0]
        if not output:
            output = "output"

    output_path = subdir / output

    try:
        async with httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            yield ProgressMessage(text="Sending request")

            async with client.stream("GET", url) as response:
                response.raise_for_status()

                total = response.headers.get("content-length")
                total_bytes = int(total) if total else None

                yield ProgressMessage(text=f"Downloading to {output_path.name}")

                downloaded = 0
                last_progress_timestamp = None
                with output_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_bytes:
                            progress = downloaded / total_bytes
                            if time.time() - (last_progress_timestamp or 0) < 1:
                                continue
                            last_progress_timestamp = time.time()
                            yield ProgressMessage(
                                text=f"Downloaded {downloaded}/{total_bytes} bytes",
                                completion_ratio=progress,
                            )

                size_kb = downloaded / 1024
                yield SuccessMessage(
                    text=f"Saved {output_path.name} ({size_kb:.1f} KB, status {response.status_code})"
                )

    except httpx.HTTPStatusError as e:
        yield ErrorMessage(
            text=f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        )
    except httpx.TimeoutException:
        yield ErrorMessage(text=f"Request timed out after {timeout} seconds")
    except httpx.RequestError as e:
        yield ErrorMessage(text=f"Request failed: {e}")
    except Exception as e:
        yield ErrorMessage(text=f"Unexpected error: {e}")
