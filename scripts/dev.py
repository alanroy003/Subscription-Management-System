"""Developer commands (Windows-friendly, no bash needed).

    python scripts/dev.py doctor     check tools, .env and database
    python scripts/dev.py setup      create backend venv, install backend + frontend deps
    python scripts/dev.py up         run API (:8000) and web app (:5173) together
    python scripts/dev.py migrate    apply database migrations
    python scripts/dev.py seed       load demo data (add --reset to wipe first, --subs 10000 for load testing)
    python scripts/dev.py billing    run billing for today (add --dry-run)
    python scripts/dev.py test       backend tests + frontend type-check/build
    python scripts/dev.py perf       time the main API endpoints against the configured database
"""
import os
import shutil
import subprocess
import sys
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


def doctor(_):
    ok = True
    for tool in ("git", "node", NPM):
        found = shutil.which(tool)
        print(f"{'OK ' if found else 'MISSING'} {tool}")
        ok &= bool(found)
    print(f"{'OK ' if sys.version_info >= (3, 11) else 'OLD'} python {sys.version.split()[0]}")
    env = ROOT / ".env"
    names = {line.split("=", 1)[0] for line in env.read_text(encoding="utf-8-sig").splitlines() if "=" in line} if env.exists() else set()
    for name in ("DATABASE_URL", "DJANGO_SECRET_KEY"):
        print(f"{'OK ' if name in names else 'MISSING'} .env {name}")
    print(f"{'OK ' if PY.exists() else 'MISSING'} backend venv (run: python scripts/dev.py setup)")
    if PY.exists():
        run([PY, "-c", "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();"
                       "from django.db import connection;connection.cursor().execute('select 1');print('OK  database', connection.vendor)"],
            cwd=BACKEND, check=False)
    sys.exit(0 if ok else 1)


def setup(_):
    if not PY.exists():
        run([sys.executable, "-m", "venv", BACKEND / ".venv"])
    run([PY, "-m", "pip", "install", "-r", BACKEND / "requirements.txt"])
    run([NPM, "install"], cwd=FRONTEND)


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


def test(_):
    run([PY, "-m", "pytest"], cwd=BACKEND)
    if (FRONTEND / "node_modules").exists():
        run([NPM, "run", "build"], cwd=FRONTEND)


def perf(args):
    run([PY, ROOT / "scripts" / "perf_check.py", *args], cwd=BACKEND)


COMMANDS = {
    "doctor": doctor, "setup": setup, "up": up, "test": test, "perf": perf,
    "migrate": lambda a: manage("migrate", *a),
    "seed": lambda a: manage("seed", *a),
    "billing": lambda a: manage("run_billing", *a),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
