"""Lightweight data classes shared by Loader and Dispenser."""

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Dict, Optional


@dataclass
class AssetSnapshot:
    """Minimal in-memory view of an asset.

    Only the scheduling-critical fields are represented to keep the closed loop
    lightweight. Additional metadata is accepted and preserved so tests can
    assert on it if needed.
    """

    asset_id: str
    sku_category: str
    sku_code: str
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceHint:
    """Hint from a TaskOrder describing the desired asset."""

    sku_category: str
    sku_code: Optional[str] = None
    min_count: int = 1

    def matches(self, asset: AssetSnapshot) -> bool:
        """Return True when the asset satisfies this hint.

        * Categories must match exactly.
        * ``sku_code`` supports simple glob matching ("ip.*"), mirroring how
          BOM hints are often specified in the docs.
        """

        if asset.sku_category != self.sku_category:
            return False

        if self.sku_code is None:
            return True

        return fnmatch(asset.sku_code, self.sku_code)
