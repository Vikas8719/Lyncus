"""
conftest.py — pytest session-level setup

Hypothesis profile yahan NAHI banate — woh Lyncus/core/hypothesis_profile.py
plugin mein hota hai jo pytest-cov ke sath -p flag se load hota hai.
Yahan sirf ensure karo ki profile loaded hai (agar pehle se nahi hua).
"""
from hypothesis import settings, HealthCheck
import os

_MAX = int(os.environ.get("LYNCUS_HYPOTHESIS_MAX_EXAMPLES", "1000"))

# Profile pehle se registered na ho to hi register karo
try:
    settings.register_profile(
        "lyncus",
        max_examples=_MAX,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,  # slow machines pe timeout se bachao
    )
except Exception:
    pass  # pehle se registered hai — theek hai

settings.load_profile("lyncus")
