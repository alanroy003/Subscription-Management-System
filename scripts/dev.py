"""Developer commands (Windows-friendly, no bash needed).

    python scripts/dev.py doctor     check tools, .env (names only, never values), git hooks and database
    python scripts/dev.py setup      create backend venv, install backend + frontend deps, install git hooks
    python scripts/dev.py hooks      install the pre-commit secret scan for manual commits
    python scripts/dev.py up         run API (:8000) and web app (:5173) together
    python scripts/dev.py migrate    apply database migrations
    python scripts/dev.py seed       load demo data (add --reset to wipe first, --subs 10000 for load testing)
    python scripts/dev.py billing    run billing for today (add --dry-run)
    python scripts/dev.py test       backend tests (SQLite) + frontend type-check/build
    python scripts/dev.py test --pg  same, plus the Postgres-only concurrency tests in a throwaway docker container
    python scripts/dev.py lint       ruff (Python) + oxlint (frontend)
    python scripts/dev.py down       stop the docker compose stack and the test Postgres container
    python scripts/dev.py perf       time the main API endpoints against the configured database
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PY = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NPM = "npm.cmd" if os.name == "nt" else "npm"


def run(cmd, cwd=ROOT, check=True):
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check)


def manage(*args):
    return run([PY, "manage.py", *args], cwd=BACKEND)


REQUIRED_ENV = ("DATABASE_URL", "DJANGO_SECRET_KEY")


def _env_file(path: Path) -> dict:
    """Parse a dotenv file. Values stay in memory and are never printed."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def doctor(_):
    ok = True

    def report(good: bool, label: str, hint: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"{'OK     ' if good else 'PROBLEM'} {label}{'' if good or not hint else f'  -> {hint}'}")

    for tool in ("git", "node", NPM):
        report(bool(shutil.which(tool)), tool, "install it and reopen the terminal")
    report(sys.version_info >= (3, 11), f"python {sys.version.split()[0]}", "use Python 3.11+")

    env, example = _env_file(ROOT / ".env"), _env_file(ROOT / ".env.example")
    report(bool(env), ".env exists", "copy .env.example to .env and fill it in")
    for name in REQUIRED_ENV:
        report(bool(env.get(name)), f".env {name} is set", "required")
    missing = sorted(set(example) - set(env))
    if missing:
        print(f"INFO    optional .env names not set: {', '.join(missing)}")
    module = env.get("DJANGO_SETTINGS_MODULE", "config.settings")
    report(module == "config.settings", f".env DJANGO_SETTINGS_MODULE={module}",
           "set it to config.settings (the only settings module); other values break Docker")
    url = env.get("DATABASE_URL", "")
    if url:
        from urllib.parse import urlparse
        u = urlparse(url)
        session_pooler = "pooler.supabase.com" in (u.hostname or "") and u.port == 5432
        report(session_pooler or "supabase" not in (u.hostname or ""), "DATABASE_URL uses the Supabase session pooler",
               "use the Session pooler string (port 5432), not the transaction pooler or direct host")

    hook = ROOT / ".git" / "hooks" / "pre-commit"
    report(hook.exists() and "pre-commit" in hook.read_text(encoding="utf-8", errors="ignore"),
           "git pre-commit secret scan installed", "run: python scripts/dev.py hooks")
    report(PY.exists(), "backend venv", "run: python scripts/dev.py setup")
    if PY.exists():
        result = run([PY, "-c", "import django,os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();"
                      "from django.db import connection;connection.cursor().execute('select 1');print('OK      database', connection.vendor)"],
                     cwd=BACKEND, check=False)
        ok &= result.returncode == 0
    sys.exit(0 if ok else 1)


def hooks(_):
    run([PY, "-m", "pip", "install", "-q", "-r", BACKEND / "requirements-dev.txt"])
    run([PY, "-m", "pre_commit", "install"])
    run([PY, "-m", "pre_commit", "run", "--all-files"], check=False)


def setup(_):
    if not PY.exists():
        run([sys.executable, "-m", "venv", BACKEND / ".venv"])
    run([PY, "-m", "pip", "install", "-r", BACKEND / "requirements-dev.txt"])
    run([NPM, "install"], cwd=FRONTEND)
    hooks(None)


def up(_):
    api = subprocess.Popen([str(PY), "manage.py", "runserver", "127.0.0.1:8000"], cwd=BACKEND)
    web = subprocess.Popen([NPM, "run", "dev", "--", "--port", "5173"], cwd=FRONTEND)
    print("\nAPI  http://127.0.0.1:8000/api/docs\nApp  http://localhost:5173\nCtrl+C to stop.\n")
    try:
        api.wait()
        web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (api, web):
            p.terminate()


TEST_PG = "brightloop-test-pg"
TEST_PG_URL = "postgres://postgres:postgres@127.0.0.1:54329/postgres"  # pragma: allowlist secret (throwaway container)


def _ensure_test_postgres() -> None:
    """Start (or reuse) a disposable local Postgres for tests. Never points at Supabase."""
    running = subprocess.run(["docker", "ps", "-q", "-f", f"name={TEST_PG}"], capture_output=True, text=True)
    if running.stdout.strip():
        return
    exists = subprocess.run(["docker", "ps", "-aq", "-f", f"name={TEST_PG}"], capture_output=True, text=True)
    if exists.stdout.strip():
        run(["docker", "start", TEST_PG])
    else:
        run(["docker", "run", "-d", "--name", TEST_PG, "-e", "POSTGRES_PASSWORD=postgres",
             "-p", "54329:5432", "postgres:17-alpine"])
    for _ in range(30):
        ready = subprocess.run(["docker", "exec", TEST_PG, "pg_isready", "-U", "postgres"], capture_output=True)
        if ready.returncode == 0:
            return
        time.sleep(1)
    sys.exit("test Postgres did not become ready")


def test(args):
    run([PY, "-m", "pytest"], cwd=BACKEND)
    if "--pg" in args:
        _ensure_test_postgres()
        env = {**os.environ, "TEST_DATABASE_URL": TEST_PG_URL}
        print("$ pytest (Postgres)")
        subprocess.run([str(PY), "-m", "pytest"], cwd=BACKEND, env=env, check=True)
    if (FRONTEND / "node_modules").exists():
        run([NPM, "run", "build"], cwd=FRONTEND)


def lint(_):
    run([PY, "-m", "ruff", "check", "."], cwd=BACKEND)
    run([NPM, "run", "lint"], cwd=FRONTEND)


def down(_):
    if (ROOT / "docker-compose.yml").exists():
        run(["docker", "compose", "down"], check=False)
    run(["docker", "rm", "-f", TEST_PG], check=False)


def perf(args):
    run([PY, ROOT / "scripts" / "perf_check.py", *args], cwd=BACKEND)


COMMANDS = {
    "doctor": doctor, "setup": setup, "hooks": hooks, "up": up, "test": test, "perf": perf,
    "lint": lint, "down": down,
    "migrate": lambda a: manage("migrate", *a),
    "seed": lambda a: manage("seed", *a),
    "billing": lambda a: manage("run_billing", *a),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
