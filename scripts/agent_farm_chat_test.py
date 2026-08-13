#!/usr/bin/env python3
"""Entry point — thin wrapper around modular agent_farm package.

Layout:
  scripts/agent_farm/
    common.py          shared helpers
    runner.py          CLI + concurrent subprocess runner
    agents/
      _base.py         AgentPlugin interface
      hermes.py        one file per agent
      pi.py
      ...
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_farm.runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
