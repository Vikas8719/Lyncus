"""
Pytest plugin — Lyncus ka extended Hypothesis run profile apply karta hai.

pytest-cov ke saath -p flag se load hota hai:
  pytest -p Lyncus.core.hypothesis_profile --cov=. ...

Profile "lyncus" register karta hai:
  - max_examples=1000  (env LYNCUS_HYPOTHESIS_MAX_EXAMPLES se override ho sakta hai)
  - deadline=None      (slow CI machines pe flaky timeout se bachao)
  - suppress_health_check=[HealthCheck.too_slow]  (database / fixture setup slow ho to)
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

_PROFILE_NAME = "lyncus"
_MAX_EXAMPLES = int(os.environ.get("LYNCUS_HYPOTHESIS_MAX_EXAMPLES", "1000"))

# Duplicate registration se AlreadyRegistered error aata hai —
# conftest.py bhi yahi karta hai, isliye try/except guard lagao
try:
    settings.register_profile(
        _PROFILE_NAME,
        max_examples=_MAX_EXAMPLES,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
except Exception:
    # Profile pehle se registered hai — safe to ignore
    pass

settings.load_profile(_PROFILE_NAME)
