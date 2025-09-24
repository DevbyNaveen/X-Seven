"""Food service endpoints package."""

from . import menu, order, table, inventory, qr
from .websocket import dashboard_websocket, kitchen_websocket

__all__ = ["menu", "order", "table", "inventory", "qr", "dashboard_websocket", "kitchen_websocket"]
