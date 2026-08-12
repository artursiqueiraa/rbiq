"""
Configuração do Live Execution Engine e credenciais (Sprint 7, passo 2).

Contém a PRIMEIRA das três travas redundantes contra operar em conta REAL por
acidente (seção 7): `ExecutionConfig.__post_init__` recusa a própria
construção de uma config com `account_type=REAL` a menos que `allow_real`
tenha sido setado explicitamente. As outras duas travas (seção 12 e a
verificação de sessão em `iqoption.py`) são independentes desta — nenhuma
delas assume que as outras já rodaram.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .types import AccountType, InstrumentType


class RealAccountNotAllowedError(ValueError):
    """Levantado quando algo tenta construir/usar conta REAL sem as travas."""


@dataclass
class ExecutionConfig:
    """Não é `frozen`: o kill switch (seção 30 do escopo) precisa poder ser
    ligado em runtime, no MESMO objeto que a guarda já está observando, sem
    reiniciar o processo. Os demais campos podem mudar entre execuções, mas
    não devem ser mutados no meio de uma operação em andamento."""

    account_type: AccountType = AccountType.PRACTICE
    allow_real: bool = False

    fixed_stake: float = 1.0
    instrument: InstrumentType = InstrumentType.BINARY
    expiry_minutes: int = 1

    max_daily_loss: float | None = None
    max_daily_trades: int | None = None
    max_concurrent_orders: int = 1

    poll_interval_s: float = 1.0
    poll_timeout_s: float = 60.0

    kill_switch: bool = False

    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Trava 1 de 3 (seção 7): a config nem chega a existir em estado
        # REAL sem allow_real explícito. As travas 2 (guard.py) e 3
        # (iqoption.py) são checadas de novo, independentemente desta —
        # nenhuma confia que esta já rodou.
        if self.account_type is AccountType.REAL and not self.allow_real:
            raise RealAccountNotAllowedError(
                "account_type=REAL exige allow_real=True explícito na ExecutionConfig. "
                "Isto não é o default em nenhum caminho do sistema."
            )
        if self.fixed_stake <= 0:
            raise ValueError("fixed_stake deve ser positivo.")
        if self.expiry_minutes <= 0:
            raise ValueError("expiry_minutes deve ser positivo.")
        if self.max_concurrent_orders <= 0:
            raise ValueError("max_concurrent_orders deve ser positivo.")
        if self.poll_interval_s <= 0 or self.poll_timeout_s <= 0:
            raise ValueError("poll_interval_s e poll_timeout_s devem ser positivos.")
        if self.poll_interval_s > self.poll_timeout_s:
            raise ValueError("poll_interval_s não pode ser maior que poll_timeout_s.")

    @property
    def is_real_account(self) -> bool:
        return self.account_type is AccountType.REAL and self.allow_real


@dataclass(frozen=True)
class Credentials:
    """Nunca construída a partir de literais no código nem de argumentos de
    CLI — apenas `from_env()`. `__repr__`/`__str__` mascaram o segredo para
    que um `logger.info(config)` ou traceback acidental não vaze a senha."""

    email: str
    password: str

    @classmethod
    def from_env(cls) -> "Credentials":
        email = os.environ.get("IQOPTION_EMAIL")
        password = os.environ.get("IQOPTION_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "Credenciais ausentes: defina IQOPTION_EMAIL e IQOPTION_PASSWORD "
                "no ambiente (.env). Nunca hardcode credenciais no código."
            )
        return cls(email=email, password=password)

    def __repr__(self) -> str:
        return "Credentials(email=***, password=***)"

    def __str__(self) -> str:
        return self.__repr__()
