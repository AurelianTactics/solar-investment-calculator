"""Battery + balcony (plug-in) solar — thin configuration over the shared combo mechanism.

A renter-scale pairing: a plug-in kit (25-yr escalating/degrading stream, self-consumption only —
no NEB) plus a home battery (10-yr flat stream), combined additively. See combo.py for the chain
and the namespacing rules. Pairing-interaction economics are open research
(docs/options-integration-notes.md); the interaction assumption defaults to 0.
"""

from __future__ import annotations

import combo
from combo import ComboResult  # noqa: F401  (re-exported for callers)


def compute_from_assumptions(a: dict) -> combo.ComboResult:
    return combo.compute_from_assumptions(a, "balcony")
