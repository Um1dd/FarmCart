"""Cross-platform local launcher. No hosting or publication required."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description='Run FarmCart locally')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--setup-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    os.chdir(ROOT)
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Preparing Python environment...', flush=True)
        venv.create(ROOT / '.venv', with_pip=True)
    def run(*command):
        subprocess.run([str(python), *command], check=True)
    run('-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements.txt')
    first_run = not (ROOT / 'db.sqlite3').exists()
    run('manage.py', 'migrate', '--noinput')
    if first_run:
        run('manage.py', 'seed_demo')
    run('manage.py', 'check')
    if args.setup_only:
        return
    # Check before starting: never open an unrelated service on the selected port.
    import socket
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', args.port))
        except OSError:
            raise SystemExit(f'Port {args.port} is occupied. Retry with --port {args.port + 1}.')
    url = f'http://127.0.0.1:{args.port}/'
    print(f'FarmCart: {url}\nKeep this window open. Press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        def open_when_ready():
            for _ in range(60):
                try:
                    with urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            webbrowser.open(url)
                            return
                except OSError:
                    time.sleep(.5)
        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        run('manage.py', 'runserver', f'127.0.0.1:{args.port}', '--noreload')
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
