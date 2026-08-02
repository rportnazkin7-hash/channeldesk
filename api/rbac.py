from __future__ import annotations
from fastapi import HTTPException

# Централизованная матрица разрешений: действие -> набор допустимых ролей.
# Это единый источник истины для новых маршрутов (постепенная миграция
# со старых require_roles / ROLE_LEVEL).
MATRIX: dict[str, frozenset[str]] = {
    'workspace.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'workspace.manage': frozenset({'owner','admin'}),

    'members.view': frozenset({'owner','admin','editor','analyst'}),
    'members.manage': frozenset({'owner','admin'}),

    'invite.create': frozenset({'owner','admin'}),

    'channel.view': frozenset({'owner','admin','editor','author','designer','ad_manager','analyst','viewer'}),
    'channel.connect': frozenset({'owner','admin'}),

    'audit.view': frozenset({'owner','admin','analyst'}),
}


def require_action(member: dict, action: str) -> None:
    allowed = MATRIX.get(action)
    if allowed is None:
        raise HTTPException(status_code=500, detail=f'Неизвестное действие: {action}')
    if member.get('role') not in allowed:
        raise HTTPException(status_code=403, detail='Недостаточно прав')
