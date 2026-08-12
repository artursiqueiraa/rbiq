"""Live Execution Engine (Sprint 7). Ver docs/sprints/SPRINT_7_REPORT.md."""

from .broker import BrokerConnectionError, BrokerGateway, BrokerRejectionError
from .config import Credentials, ExecutionConfig, RealAccountNotAllowedError
from .executor import LiveExecutor
from .guard import ExecutionGuard, GuardDecision, GuardState
from .iqoption import IQOptionGateway, TwoFactorAuthRequired
from .paper import PaperBroker
from .repository import ExecutionRepository, InMemoryExecutionRepository
from .types import (
    AccountType,
    ExecutionRecord,
    ExecutionResult,
    ExecutionStatus,
    InstrumentType,
    OrderDirection,
    OrderRequest,
    SignalLike,
    compute_idempotency_key,
    normalize_order_direction,
)

__all__ = [
    "AccountType",
    "BrokerConnectionError",
    "BrokerGateway",
    "BrokerRejectionError",
    "Credentials",
    "ExecutionConfig",
    "ExecutionGuard",
    "ExecutionRecord",
    "ExecutionRepository",
    "ExecutionResult",
    "ExecutionStatus",
    "GuardDecision",
    "GuardState",
    "IQOptionGateway",
    "InMemoryExecutionRepository",
    "InstrumentType",
    "LiveExecutor",
    "OrderDirection",
    "OrderRequest",
    "PaperBroker",
    "RealAccountNotAllowedError",
    "SignalLike",
    "TwoFactorAuthRequired",
    "compute_idempotency_key",
    "normalize_order_direction",
]
