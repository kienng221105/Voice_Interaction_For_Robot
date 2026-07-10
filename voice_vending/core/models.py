"""
Data Models for Voice Vending Machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Product:
    """Represents a vendable product."""

    id: str  # internal key, e.g. "coca"
    display_name: str
    price: int
    stock: int
    max_stock: int
    category: str
    enabled: bool
    slot: int | None = None
    aliases: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, product_id: str, data: dict) -> Product:
        return cls(
            id=product_id,
            display_name=data.get("display_name", product_id),
            price=int(data.get("price", 0)),
            stock=int(data.get("stock", 0)),
            max_stock=int(data.get("max_stock", 0)),
            category=data.get("category", "unknown"),
            enabled=bool(data.get("enabled", False)),
            slot=data.get("slot"),
            aliases=data.get("aliases", []),
        )
