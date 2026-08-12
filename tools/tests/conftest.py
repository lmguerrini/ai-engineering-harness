"""Put ``tools/`` on the import path so tests can ``import gitread`` and friends.

Deliberately not the kernel's conftest: the toolbelt is required to run with
plain ``python3 -m pytest tools/tests/`` and no installed package, so the only
thing this does is make the sibling ``tools/`` directory importable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
