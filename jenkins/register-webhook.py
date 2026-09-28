#!/usr/bin/env python3
"""Register or update this installation's GitHub push webhook using gh authentication."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REPO = 'vvennela/cmpe272-github'
STATE = ROOT / '.webhook-state.json'


def api(path, payload=None):
    command = ['gh', 'api', path]
    if payload is not None:
        command += ['--method', 'PATCH' if path.rsplit('/', 1)[-1].isdigit() else 'POST', '--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    os.chdir(ROOT)
    subprocess.run(['gh', 'auth', 'status'], check=True)
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
    else:
        logs = subprocess.run(['docker', 'compose', 'logs', '--no-color', 'tunnel'],
                              text=True, capture_output=True, check=True).stdout
        urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', logs)
        if not urls:
            raise SystemExit('Tunnel URL unavailable. Wait for startup or pass a public HTTPS base URL.')
        base = urls[-1]
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise SystemExit('Expected a public HTTPS base URL without credentials, query, or fragment.')
    url = base + '/github-webhook/'
    secret = (ROOT / '.secrets/webhook-secret').read_text().strip()
    if not secret:
        raise SystemExit('Webhook secret is empty. Run bash jenkins/setup.sh first.')
    payload = {'name': 'web', 'active': True, 'events': ['push'],
               'config': {'url': url, 'content_type': 'json', 'secret': secret, 'insecure_ssl': '0'}}
    endpoint = f'repos/{REPO}/hooks'
    state = json.loads(STATE.read_text()) if STATE.exists() else None
    if state:
        hook = api(f"{endpoint}/{state['id']}")
        if hook['config']['url'] != state['url']:
            raise SystemExit('Saved webhook was modified externally; inspect it before updating.')
        hook = api(f"{endpoint}/{state['id']}", payload)
    else:
        pages = subprocess.run(['gh', 'api', '--paginate', '--slurp', endpoint],
                               capture_output=True, text=True, check=True)
        matches = [h for page in json.loads(pages.stdout) for h in page if h['config']['url'] == url]
        if matches:
            hook = api(f"{endpoint}/{matches[0]['id']}", payload)
        else:
            hook = api(endpoint, payload)
    STATE.write_text(json.dumps({'id': hook['id'], 'url': url}, indent=2) + '\n')
    subprocess.run(['gh', 'api', '--method', 'POST', f"{endpoint}/{hook['id']}/pings"], check=True)
    print(f"Push webhook registered: {url}")
    print(f"Inspect delivery results at https://github.com/{REPO}/settings/hooks/{hook['id']}")


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        # API requests contain a secret: never print the payload or command stdin.
        raise SystemExit(f'Command failed (exit {error.returncode}). Check GitHub login, repo admin access, and Docker.')
