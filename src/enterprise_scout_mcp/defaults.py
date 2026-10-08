"""Shared defaults for registry / tiered collect."""

from __future__ import annotations

# ENScan field list for a usable EnterpriseLake row + equity edges.
# Matches ENScan_GO ENSMapLN section keys (aqc/tyc/kc/rb).
DEFAULT_REGISTRY_FIELDS: tuple[str, ...] = (
    "enterprise_info",
    "partner",
    "holds",
    "invest",
    "branch",
)

# Checkpoint / resume: only these grades are skipped on next run.
DONE_GRADES: frozenset[str] = frozenset({"ok", "partial"})
