from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs
import uuid

DATA_FILE = "tasks.txt"


class Task:
    def __init__(self, title: str, priority: str, is_done: bool = False, task_id: Optional[str] = None):
        self.id = task_id if task_id else str(uuid.uuid4().int)[:8]
        self.title = title
        self.priority = priority if priority in ["low", "normal", "high"] else "normal"
        self.is_done = is_done

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "isDone": self.is_done
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Task:
        return cls(
            title=data["title"],
            priority=data["priority"],
            is_done=data["isDone"],
            task_id=data["id"]
        )


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.load_tasks()

    def add_task(self, title: str, priority: str) -> Task:
        task = Task(title, priority)
        self.tasks[task.id] = task
        self.save_tasks()
        return task

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def mark_as_done(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task:
            task.is_done = True
            self.save_tasks()
            return True
        return False

    def save_tasks(self) -> None:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            tasks_data = [task.to_dict() for task in self.tasks.values()]
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)

    def load_tasks(self) -> None:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                    for task_data in tasks_data:
                        task = Task.from_dict(task_data)
                        self.tasks[task.id] = task
            except (json.JSONDecodeError, KeyError):
                print("Ошибка при загрузке задач. Начинаем с чистого списка.")
                self.tasks = {}


class TaskHandler(BaseHTTPRequestHandler):
    task_manager = TaskManager()

    def _send_json_response(self, status_code: int, data: Optional[Dict | List] = None) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_html_response(self, status_code: int, html: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_empty_response(self, status_code: int) -> None:
        self.send_response(status_code)
        self.end_headers()

    def _parse_path(self) -> tuple:
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip("/").split("/")
        query_params = parse_qs(parsed.query)
        return path_parts, query_params

    def _read_json_body(self) -> Optional[Dict]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None

        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def _generate_html(self) -> str:
        tasks = self.task_manager.get_all_tasks()

        task_rows = ""
        for task in tasks:
            status = "✅ Выполнено" if task.is_done else "⏳ В процессе"
            priority_color = {
                "high": "#ff6b6b",
                "normal": "#4ecdc4",
                "low": "#ffe66d"
            }.get(task.priority, "#4ecdc4")

            task_rows += f"""
            <div style="border:1px solid #ddd; margin:10px; padding:10px; border-radius:5px;">
                <h3>{task.title}</h3>
                <p><strong>ID:</strong> {task.id}</p>
                <p><strong>Приоритет:</strong> 
                    <span style="background-color:{priority_color}; padding:2px 8px; border-radius:3px;">
                        {task.priority}
                    </span>
                </p>
                <p><strong>Статус:</strong> {status}</p>
                <form method="POST" action="/tasks/{task.id}/complete" style="display:inline;">
                    <button type="submit" {'disabled' if task.is_done else ''}>
                        {'✓ Выполнено' if task.is_done else 'Отметить выполненным'}
                    </button>
                </form>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Todo Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .form-group {{ margin: 20px 0; }}
                input, select, button {{ padding: 10px; margin: 5px; }}
                button {{ cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📝 Todo Server</h1>

                <h2>Добавить новую задачу</h2>
                <form method="POST" action="/tasks">
                    <div class="form-group">
                        <input type="text" name="title" placeholder="Название задачи" required style="width:300px;">
                    </div>
                    <div class="form-group">
                        <select name="priority">
                            <option value="low">Низкий</option>
                            <option value="normal" selected>Обычный</option>
                            <option value="high">Высокий</option>
                        </select>
                    </div>
                    <button type="submit">Добавить задачу</button>
                </form>

                <h2>Список задач ({len(tasks)})</h2>
                <div id="tasks">
                    {task_rows if tasks else "<p>Задач пока нет</p>"}
                </div>

                <hr>
            </div>
        </body>
        </html>
        """

    def do_GET(self):
        path_parts, _ = self._parse_path()

        if len(path_parts) == 0 or (len(path_parts) == 1 and path_parts[0] == ""):
            # Главная страница с HTML интерфейсом
            html = self._generate_html()
            self._send_html_response(200, html)

        elif len(path_parts) == 1 and path_parts[0] == "tasks":
            # API: получить все задачи в JSON
            tasks = self.task_manager.get_all_tasks()
            tasks_data = [task.to_dict() for task in tasks]
            self._send_json_response(200, tasks_data)

        else:
            self._send_empty_response(404)

    def do_POST(self):
        path_parts, query_params = self._parse_path()

        if len(path_parts) == 1 and path_parts[0] == "tasks":
            # Создание задачи
            if self.headers.get('Content-Type') == 'application/json':
                # JSON запрос
                data = self._read_json_body()
                if not data or "title" not in data:
                    self._send_empty_response(400)
                    return

                priority = data.get("priority", "normal")
                task = self.task_manager.add_task(data["title"], priority)
                self._send_json_response(201, task.to_dict())
            else:
                # HTML форма
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length).decode('utf-8')
                    # Парсим form-data
                    import urllib.parse
                    params = urllib.parse.parse_qs(body)
                    title = params.get('title', [''])[0]
                    priority = params.get('priority', ['normal'])[0]

                    if title:
                        self.task_manager.add_task(title, priority)

                # Перенаправляем на главную
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()

        elif len(path_parts) == 3 and path_parts[0] == "tasks" and path_parts[2] == "complete":
            # Отметка задачи как выполненной
            task_id = path_parts[1]
            if self.task_manager.mark_as_done(task_id):
                if self.headers.get('Content-Type') == 'application/json':
                    self._send_empty_response(200)
                else:
                    # Перенаправляем на главную для HTML запросов
                    self.send_response(303)
                    self.send_header('Location', '/')
                    self.end_headers()
            else:
                self._send_empty_response(404)
        else:
            self._send_empty_response(404)

    def log_message(self, format: str, *args) -> None:
        # Логируем запросы для отладки
        print(f"{self.address_string()} - {self.command} {self.path}")


def main() -> None:
    server_address = ("127.0.0.1", 8080)
    httpd = ThreadingHTTPServer(server_address, TaskHandler)

    print(f"✅ Сервер запущен. Перейдите по ссылке на http://{server_address[0]}:{server_address[1]}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n Сервер остановлен")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()