"""Apply and verify the narrow mainland reCAPTCHA script allowance."""
import re

SOURCE = "https://www.gstatic.cn/recaptcha/"
PATTERN = r'(<meta\s+http-equiv="Content-Security-Policy"\s+content=")([^"]+)(")'


def verify(html):
    policies = re.findall(PATTERN, html, re.I)
    assert len(policies) == 1, "Expected one Element meta CSP"
    directives = [part.split() for part in policies[0][1].split(";") if part.strip()]
    scripts = [d for d in directives if d[0] == "script-src"]
    assert len(scripts) == 1 and SOURCE in scripts[0], "Mainland reCAPTCHA script missing from CSP"
    for directive in directives:
        if directive[0] == "script-src-elem":
            assert SOURCE in directive, "script-src-elem blocks mainland reCAPTCHA"


def patch(html):
    policies = re.findall(PATTERN, html, re.I)
    assert len(policies) == 1, "Upstream meta CSP changed; review before deployment"
    policy = policies[0][1]
    scripts = re.findall(r"(?:^|;)\s*script-src\s+([^;]+)", policy)
    assert len(scripts) == 1, "Upstream script-src changed"
    assert "https://www.gstatic.com/recaptcha/" in scripts[0].split(), "Upstream reCAPTCHA policy changed"
    if SOURCE not in scripts[0].split():
        policy = re.sub(r"(https://www\.gstatic\.com/recaptcha/)(?=\s|;|$)", r"\1 " + SOURCE, policy, count=1)
    result = re.sub(PATTERN, lambda m: m[1] + policy + m[3], html, count=1, flags=re.I)
    verify(result)
    return result
