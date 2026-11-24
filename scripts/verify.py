"""Verify the artifact, and optionally its deployed HTTP behavior."""
import json
from captcha_csp import verify as verify_captcha_csp
from pathlib import Path
import sys
import urllib.request
import urllib.error
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
dist = ROOT / 'dist'
release = json.loads((dist / 'nerchat-release.json').read_text())
assert (dist / 'index.html').is_file()
verify_captcha_csp((dist / 'index.html').read_text(encoding='utf-8'))
assert (dist / 'version').read_text().strip() == release['tag'].removeprefix('v') or (dist / 'version').read_text().strip() == release['tag']
assert json.loads((dist / 'config.json').read_text())['brand'] == 'NerChat!'
assert isinstance(json.loads((dist / 'widgets/element-call/config.json').read_text()), dict)
for name in ['client', 'server']:
    json.loads((dist / '.well-known/matrix' / name).read_text())
assert json.loads((dist / '_matrix/client/versions').read_text())['versions']
assert not (dist / 'staticwebapp.config.json').exists()

if len(sys.argv) > 1:
    base_parts = urllib.parse.urlsplit(sys.argv[1])
    base = urllib.parse.urlunsplit((base_parts.scheme, base_parts.netloc, '', '', ''))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    # The temporary Tencent URL authorizes this IP on first access. Visit it
    # once; do not mix the platform access parameters into Matrix business URLs.
    if base_parts.query:
        with opener.open(sys.argv[1], timeout=60) as response:
            assert response.status == 200
    def fetch(path, method='GET'):
        try:
            url = base + path
            return opener.open(urllib.request.Request(url, method=method), timeout=60)
        except urllib.error.HTTPError as response:
            return response
    translation = next((dist / 'i18n').rglob('*.json'))
    for path in ['/', '/index.html', '/config.json', '/widgets/element-call/config.json', '/version', '/' + translation.relative_to(dist).as_posix(), '/.well-known/matrix/client', '/.well-known/matrix/server', '/_matrix/client/versions', '/nerchat-release.json']:
        response = fetch(path)
        assert response.status == 200, (path, response.status)
        assert 'no-cache' in response.headers.get('Cache-Control', '') or 'no-store' in response.headers.get('Cache-Control', ''), (path, dict(response.headers))
        if path in ['/', '/index.html']:
            verify_captcha_csp(response.read().decode('utf-8'))
            assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
            assert "frame-ancestors 'self'" in response.headers.get('Content-Security-Policy', '')
        if path.startswith('/.well-known/') or path == '/_matrix/client/versions':
            assert response.headers.get('Access-Control-Allow-Origin') == '*'
            assert response.headers.get_content_type() == 'application/json'
            json.loads(response.read())
        elif path == '/widgets/element-call/config.json':
            assert response.headers.get_content_type() == 'application/json'
            assert isinstance(json.loads(response.read()), dict)
        elif path == '/nerchat-release.json':
            assert json.loads(response.read()) == release
        print('HTTP OK', path)
    for path in ['/_matrix/client/v3/login?probe=nerchat%20test&x=1', '/_synapse/client/oidc/callback?probe=1']:
        for method in ['GET', 'POST']:
            response = fetch(path, method)
            assert response.status == 307, (path, method, response.status)
            location = response.headers['Location']
            assert location == 'https://matrix.neboer.site:8448' + path, (path, location)
        print('REDIRECT OK', path)
    response = fetch('/_matrix/client/versions', 'OPTIONS')
    assert response.status == 204 and response.headers.get('Access-Control-Allow-Origin') == '*'
print('Verified', release['tag'])
