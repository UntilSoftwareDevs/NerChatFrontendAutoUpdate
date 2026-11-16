"""Build a reproducible Element release overlay; fail closed on upstream errors."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work'
DIST = ROOT / 'dist'
WORK.mkdir(exist_ok=True)


def download(url, authenticated=False):
    headers = {'User-Agent': 'NerChatFrontendAutoUpdate', 'Accept': 'application/vnd.github+json'} if authenticated else {'User-Agent': 'NerChatFrontendAutoUpdate'}
    if authenticated and os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return response.read()


release = json.loads(download('https://api.github.com/repos/element-hq/element-web/releases/latest', True))
tag = release['tag_name']
assert re.fullmatch(r'v\d+\.\d+\.\d+', tag) and not release['prerelease'] and not release['draft'], 'Not a stable release'
asset = next(a for a in release['assets'] if a['name'] == f'element-{tag}.tar.gz')
assert asset['browser_download_url'].startswith('https://github.com/element-hq/element-web/releases/download/')
digest = asset.get('digest', '')
assert digest.startswith('sha256:'), 'Release asset must include a GitHub SHA-256 digest'
archive = WORK / asset['name']
if not archive.exists() or 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
    archive.write_bytes(download(asset['browser_download_url']))
assert 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest() == digest, 'Archive checksum mismatch'
versions = json.loads(download('https://matrix.neboer.site:8448/_matrix/client/versions'))
assert isinstance(versions.get('versions'), list) and versions['versions'], 'Invalid Matrix versions response'

if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir()
with tarfile.open(archive) as tar:
    members = tar.getmembers()
    prefix = members[0].name.split('/')[0]
    for member in members:
        parts = Path(member.name).parts
        assert parts[0] == prefix and '..' not in parts and not member.name.startswith('/'), 'Unsafe archive path'
        assert member.isfile() or member.isdir(), 'Archive links are not accepted'
        relative = Path(*parts[1:])
        if str(relative) == '.':
            continue
        target = DIST / relative
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
shutil.copytree(ROOT / 'overlay', DIST, dirs_exist_ok=True)
# Embedded Element Call no longer ships a config after removing its last
# obsolete option (element-call#4317). Until the HTML-response fallback in
# element-call#4440 ships, SPA fallback pages break its JSON initialization.
# An empty object selects upstream defaults; preserve any supplied config.
call_config = DIST / 'widgets/element-call/config.json'
if (call_config.parent / 'index.html').is_file() and not call_config.exists():
    call_config.write_text('{}\n', encoding='utf-8')
shutil.copyfile(ROOT / 'edgeone.json', DIST / 'edgeone.json')
shutil.copytree(ROOT / 'edge-functions', DIST / 'edge-functions', dirs_exist_ok=True)
snapshot = DIST / '_matrix/client/versions'
snapshot.parent.mkdir(parents=True, exist_ok=True)
snapshot.write_text(json.dumps(versions) + '\n')
# Bundle the same validated snapshot into the exact function route. Wildcard
# redirects must never take precedence over this Matrix capability endpoint.
function = DIST / 'edge-functions/_matrix/client/versions.js'
function.write_text('const versions = ' + json.dumps(versions) + ';\n' + (ROOT / 'scripts/versions-function.js').read_text())
metadata = {'tag': tag, 'asset': asset['browser_download_url'], 'sha256': digest.split(':')[1]}
(DIST / 'nerchat-release.json').write_text(json.dumps(metadata, indent=2) + '\n')
(WORK / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(f'Prepared {tag}; verified SHA-256; applied overlay and routing configuration')
