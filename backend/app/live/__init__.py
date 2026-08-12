"""Loop de trading ao vivo — orquestra Data (candles reais) -> Strategy Engine
(Sprint 5) -> Live Execution Engine (Sprint 7). Não faz parte da spec formal
de nenhuma Sprint anterior; construído sob pedido explícito do usuário depois
de `IQOptionGateway` ser validado ponta a ponta contra a conta real."""

from .loop import LiveTradingLoop

__all__ = ["LiveTradingLoop"]
