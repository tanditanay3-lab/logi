"""
Chat Copilot for Lanework.

This module provides the chat interface that uses the Conversation Router
to route messages to the appropriate agents.
"""

from .main import app
from .schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
)
from .service import ChatCopilotService

__all__ = [
    "app",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConversationListResponse",
    "ChatCopilotService",
]
