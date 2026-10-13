"""video.js iOS 복제 실험용 정적 서버.

- iOS Safari는 mp4를 byte-range로 요청하므로 Range(206)를 지원한다.
- 페이지가 POST /log로 결과를 보내면 results.jsonl에 쌓고, GET /wait?id=...가 그 결과를 기다려 돌려준다.

usage: python3 server.py <www-dir> <port>
"""

import http.server
import json
import mimetypes
import os
import re
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

ROOT = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2])
RESULTS_FILE = os.path.join(os.path.dirname(ROOT), "results", "results.jsonl")

results = {}
cond = threading.Condition()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        if not self.path.startswith("/log"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length))
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        with cond:
            results[data.get("id")] = data
            cond.notify_all()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/wait":
            run_id = parse_qs(url.query)["id"][0]
            deadline = time.time() + 60
            with cond:
                while run_id not in results and time.time() < deadline:
                    cond.wait(deadline - time.time())
            body = json.dumps(results.get(run_id, {"id": run_id, "timeout": True}), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        path = self.translate_path(url.path)
        range_header = self.headers.get("Range")
        if not range_header or not os.path.isfile(path):
            super().do_GET()
            return

        size = os.path.getsize(path)
        match = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        else:
            start = max(0, size - int(match.group(2)))
            end = size - 1
        end = min(end, size - 1)
        with open(path, "rb") as f:
            f.seek(start)
            chunk = f.read(end - start + 1)
        self.send_response(206)
        self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(len(chunk)))
        self.end_headers()
        self.wfile.write(chunk)


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
