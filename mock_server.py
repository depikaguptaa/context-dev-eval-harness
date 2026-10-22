"""Local mock of api.context.dev/v1 for offline tests and demos.

Implements the response shapes verified from https://docs.context.dev
(2026-10-21) closely enough to exercise the client, the agent, and the
probe runner end to end without an API key:

  POST /v1/web/scrape   -> {"url", "markdown": {"requested", "success", "data"},
                            "metadata": {"title"}, "key_metadata": {"credits_consumed"},
                            "request_id"}
  POST /v1/web/search   -> {"results": [{"url", "title", "snippet"}],
                            "key_metadata": {"credits_consumed"}}
  POST /v1/web/answers  -> {"json_content", "sources", "partial",
                            "key_metadata": {"credits_consumed"}}

URL-driven behavior for /web/scrape:
  * url containing "hindi"   -> Devanagari markdown (exercises script_coverage)
  * url containing "tamil"   -> Tamil markdown
  * url containing "thin"    -> success=true but near-empty data (exercises
                                the min-chars failure path)
  * url containing "notfound"-> HTTP 400 {"error_code": "NOT_FOUND"} mirroring
                                the documented no-match error semantics

Stdlib only. Run:  python mock_server.py [port]   (default 8899)
"""

from __future__ import annotations

import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HINDI_MD = (
    "# मुख्य समाचार\n\n"
    "भारत में डिजिटल भुगतान तेजी से बढ़ रहा है। "
    "यूपीआई लेनदेन ने नया रिकॉर्ड बनाया है। "
    "विशेषज्ञों का कहना है कि ग्रामीण क्षेत्रों में भी अपनाया जा रहा है।\n"
)

TAMIL_MD = (
    "# முக்கிய செய்திகள்\n\n"
    "இந்தியாவில் டிஜிட்டல் கட்டணங்கள் வேகமாக வளர்ந்து வருகின்றன. "
    "யுபிஐ பரிவர்த்தனைகள் புதிய சாதனை படைத்துள்ளன.\n"
)

ENGLISH_MD = (
    "# Example Research Page\n\n"
    "AI agents need live web data to answer questions about the real world. "
    "Extraction quality determines whether a retrieval pipeline grounds "
    "answers or hallucinates. This page exists to test scraping pipelines "
    "with enough sentences that an extractive summarizer can rank them. "
    "Observability per API call keeps cost and quality visible at every step.\n"
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json()
        request_id = f"mock-{uuid.uuid4().hex[:8]}"

        if path == "/v1/web/scrape":
            url = body.get("url", "")
            if "notfound" in url:
                self._send(400, {"error_code": "NOT_FOUND",
                                 "message": "no content found for url"})
                return
            if "hindi" in url:
                md, title = HINDI_MD, "मुख्य समाचार"
            elif "tamil" in url:
                md, title = TAMIL_MD, "முக்கிய செய்திகள்"
            elif "thin" in url:
                md, title = "# ", "Thin page"
            else:
                md, title = ENGLISH_MD, "Example Research Page"
            self._send(200, {
                "url": url,
                "markdown": {"requested": True, "success": True, "data": md},
                "metadata": {"title": title},
                "cache_metadata": {"status": "miss", "age_ms": 0},
                "key_metadata": {"credits_consumed": 1},
                "request_id": request_id,
            })
        elif path == "/v1/web/search":
            query = body.get("query", "")
            self._send(200, {
                "results": [
                    {"url": "https://example.com/research",
                     "title": "Example Research Page",
                     "snippet": f"Result about {query}"},
                    {"url": "https://example.com/hindi-news",
                     "title": "Hindi news page",
                     "snippet": "Devanagari content page"},
                ],
                "key_metadata": {"credits_consumed": 1},
                "request_id": request_id,
            })
        elif path == "/v1/web/answers":
            task = body.get("task", "")
            self._send(200, {
                "json_content": {"answer": f"mock answer for: {task}"},
                "sources": ["https://example.com/research"],
                "partial": False,
                "key_metadata": {"credits_consumed": 10},
                "request_id": request_id,
            })
        else:
            self._send(404, {"error_code": "NOT_FOUND", "message": "unknown route"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"mock context.dev API on http://127.0.0.1:{port}/v1")
    server.serve_forever()


if __name__ == "__main__":
    main()
