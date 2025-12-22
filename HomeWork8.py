from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List

YA_DISK_API = "https://cloud-api.yandex.net/v1/disk"


def get_token_from_user() -> str:
    token = input("Введите OAuth-токен Яндекс.Диска: ").strip()
    if not token:
        raise RuntimeError("Токен не может быть пустым")
    return token


def yadisk_request(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"OAuth {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_uploaded_files(token: str) -> List[str]:
    files = []
    offset = 0
    limit = 100

    while True:
        url = f"{YA_DISK_API}/resources/files?limit={limit}&offset={offset}"
        data = yadisk_request(url, token)
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            files.append(item.get("name", ""))
        offset += limit

    return files


def upload_file_to_yadisk(file_name: str, data: bytes, token: str) -> None:
    params = urllib.parse.urlencode({"path": file_name, "overwrite": "true"})
    url = f"{YA_DISK_API}/resources/upload?{params}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"OAuth {token}")
    with urllib.request.urlopen(req) as resp:
        upload_href = json.loads(resp.read().decode())["href"]

    upload_req = urllib.request.Request(upload_href, data=data, method="PUT")
    upload_req.add_header("Content-Type", "application/octet-stream")
    urllib.request.urlopen(upload_req)


def render_html(files: List[str]) -> bytes:
    rows = []
    for f in files:
        rows.append(
            f'<li style="background-color: rgba(0, 200, 0, 0.25); padding: 4px">{f}</li>'
        )

    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Яндекс.Диск</title></head>
    <body>
        <h2>Загрузка файла</h2>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" />
            <button type="submit">Загрузить</button>
        </form>
        <h3>Уже загруженные файлы</h3>
        <ul>
            {''.join(rows)}
        </ul>
    </body>
    </html>
    """
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    token: str = ""

    def do_GET(self) -> None:
        files = get_uploaded_files(self.token)
        body = render_html(files)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400)
            return

        boundary = content_type.split("boundary=")[-1].encode()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        parts = body.split(boundary)
        for part in parts:
            if b"filename=" in part:
                header, file_data = part.split(b"\r\n\r\n", 1)
                file_data = file_data.rstrip(b"\r\n--")
                header_str = header.decode(errors="ignore")
                filename = header_str.split("filename=\"")[1].split("\"")[0]
                upload_file_to_yadisk(filename, file_data, self.token)
                break

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        return


def main() -> None:
    token = get_token_from_user()
    Handler.token = token
    server = ThreadingHTTPServer(("127.0.0.1", 8080), Handler)
    print("Server started: http://127.0.0.1:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
