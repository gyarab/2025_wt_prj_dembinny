"""
app/context_processors.py
─────────────────────────
Compatibility shim — processor has moved to core/context_processors.py.
"""

from core.context_processors import fund_balance  # noqa: F401

__all__ = ['fund_balance']
