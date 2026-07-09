"""Battery + rooftop solar — thin configuration over the shared combo mechanism (combo.py).

The realistic pairing: rooftop PV (25-yr escalating/degrading stream) plus a home battery
(10-yr flat stream), combined additively. See combo.py for the chain and the namespacing rules.
Pairing-interaction economics are open research (docs/options-integration-notes.md); until they
land, the interaction assumption defaults to 0 and the combo is exactly additive.
"""

from __future__ import annotations

import combo
from combo import ComboResult  # noqa: F401  (re-exported for callers)


def compute_from_assumptions(a: dict) -> combo.ComboResult:
    return combo.compute_from_assumptions(a, "rooftop")
