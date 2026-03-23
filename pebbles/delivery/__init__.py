"""Delivery adapters for pebbles."""

from .telegram import TelegramDelivery
from .email import EmailDelivery

__all__ = ["TelegramDelivery", "EmailDelivery"]