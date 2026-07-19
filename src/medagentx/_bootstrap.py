from __future__ import annotations

import sys

from medagentx.paths import SRC_ROOT


def ensure_src_on_path() -> None:
    src = str(SRC_ROOT)
    if src not in sys.path:
        sys.path.insert(0, src)
