"""Pytest plugin that applies Lyncus's extended Hypothesis run profile."""

from __future__ import annotations

from hypothesis import settings
import os


_PROFILE_NAME = "lyncus"
_MAX_EXAMPLES = int(os.environ.get("LYNCUS_HYPOTHESIS_MAX_EXAMPLES", "1000"))

settings.register_profile(_PROFILE_NAME, max_examples=_MAX_EXAMPLES)
settings.load_profile(_PROFILE_NAME)
