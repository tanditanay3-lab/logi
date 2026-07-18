"""
Route Optimization Agent

This agent generates and dynamically re-optimizes multi-stop routes against
vehicle capacity, time windows, and driver hours.
"""

from .main import app
from .schemas import (
    Route,
    RouteCreate,
    RouteUpdate,
    RouteStop,
    RouteStopCreate,
    RouteStopUpdate,
    RouteOptimizationRequest,
    RouteOptimizationResponse,
    RouteReoptimizationRequest,
    RouteReoptimizationResponse,
    RouteAssignment,
    RouteStats,
)
from .service import RouteOptimizationService
from .config import RouteOptimizationConfig

__all__ = [
    "app",
    "Route",
    "RouteCreate",
    "RouteUpdate",
    "RouteStop",
    "RouteStopCreate",
    "RouteStopUpdate",
    "RouteOptimizationRequest",
    "RouteOptimizationResponse",
    "RouteReoptimizationRequest",
    "RouteReoptimizationResponse",
    "RouteAssignment",
    "RouteStats",
    "RouteOptimizationService",
    "RouteOptimizationConfig",
]
