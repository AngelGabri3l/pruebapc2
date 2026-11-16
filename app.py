import os
import time

import pymysql
from flask import Flask, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Notas DevSecOps</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
    form { display: flex; gap: .5rem; margin-bottom: 1.5rem; }
    input[type=text] { flex: 1; padding: .5rem; }
    button { padding: .5rem 1rem; }
    li { margin: .4rem 0; }
    small { color: #666; }
  </style>
</head>
<body>
  <h1>Notas (Flask + MySQL)</h1>
  <form method="post" action="{{ url_for('add') }}">
    <input type="text" name="title" maxlength="200" placeholder="Escribe una nota" required>
    <button type="submit">Agregar</button>
  </form>
  <ul>
    {% for n in notes %}
      <li>{{ n.title }} <small>({{ n.created_at }})</small></li>
    {% else %}
      <li><em>Aún no hay notas.</em></li>
    {% endfor %}
  </ul>
</body>
</html>
"""

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4
"""

_db_ready = False


def get_conn():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
    )


def ensure_db(retries=15, delay=2):
    """Crea la tabla si no existe; reintenta mientras MySQL arranca."""
    global _db_ready
    if _db_ready:
        return
    last_error = None
    for _ in range(retries):
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(CREATE_TABLE)
            _db_ready = True
            return
        except pymysql.err.OperationalError as exc:
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"No se pudo conectar a MySQL: {last_error}")


@app.get("/")
def index():
    ensure_db()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, created_at FROM notes ORDER BY id DESC LIMIT 50")
        notes = cur.fetchall()
    return render_template_string(PAGE, notes=notes)


@app.post("/add")
def add():
    ensure_db()
    title = request.form.get("title", "").strip()
    if not title or len(title) > 200:
        return "Título inválido (1 a 200 caracteres).", 400
    with get_conn() as conn, conn.cursor() as cur:
        # Consulta parametrizada: evita inyección SQL
        cur.execute("INSERT INTO notes (title) VALUES (%s)", (title,))
    return redirect(url_for("index"))


@app.get("/health")
def health():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok", db="ok")
    except Exception:
        return jsonify(status="error", db="down"), 503
