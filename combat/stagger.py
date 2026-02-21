"""
Слой 5 — stagger-шкала и Прорыв стойки.

Шкала невидима игроку. Убывает в начале хода носителя.
При заполнении автоматически накладывается S_STAGGER_BREAK.
"""

from combat.status import (
    apply_status, remove_status, has_status,
    StatusEffect,
    S_STAGGER_BREAK, S_STALWART, S_CC_IMMUNE, S_DEFENSE_BREAK, S_BERSERK,
)
from combat.ctb import push_back

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

STAGGER_DECAY          = 0.08
STAGGER_BREAK_PUSHBACK = 12.0
STAGGER_BREAK_DMG_MULT = 1.35
DEFENSE_BREAK_MULT     = 2.0
STALWART_DECAY_MULT    = 1.5


# ---------------------------------------------------------------------------
# Инициализация
# ---------------------------------------------------------------------------

def init_stagger(combatant, stagger_max):
    combatant.stagger_max     = float(stagger_max)
    combatant.stagger_current = 0.0
    combatant._in_stagger_break = False


# ---------------------------------------------------------------------------
# Заполнение шкалы
# ---------------------------------------------------------------------------

def add_stagger(combatant, amount):
    if combatant._in_stagger_break:
        return False

    if has_status(combatant, S_STALWART):
        amount *= 0.5

    if has_status(combatant, S_DEFENSE_BREAK):
        amount *= DEFENSE_BREAK_MULT

    combatant.stagger_current = min(
        combatant.stagger_max,
        combatant.stagger_current + amount
    )

    if combatant.stagger_current >= combatant.stagger_max:
        return _trigger_stagger_break(combatant)
    return False


# ---------------------------------------------------------------------------
# Прорыв стойки
# ---------------------------------------------------------------------------

def _stagger_break_apply(owner, effect):
    owner._in_stagger_break = True

def _stagger_break_remove(owner, effect):
    owner._in_stagger_break = False
    owner.stagger_current   = 0.0

def _trigger_stagger_break(combatant):
    if has_status(combatant, S_CC_IMMUNE):
        return False
    if has_status(combatant, S_STALWART):
        return False
    if has_status(combatant, S_BERSERK):
        return False

    effect = StatusEffect(
        S_STAGGER_BREAK,
        duration=1,
        on_apply=_stagger_break_apply,
        on_remove=_stagger_break_remove,
    )
    applied = apply_status(combatant, effect)
    if applied:
        push_back(combatant, STAGGER_BREAK_PUSHBACK)
    return applied


# ---------------------------------------------------------------------------
# Убывание шкалы
# ---------------------------------------------------------------------------

def decay_stagger(combatant):
    if combatant._in_stagger_break:
        return

    decay = combatant.stagger_max * STAGGER_DECAY
    if has_status(combatant, S_STALWART):
        decay *= STALWART_DECAY_MULT

    combatant.stagger_current = max(0.0, combatant.stagger_current - decay)


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def stagger_pct(combatant):
    return combatant.stagger_current / combatant.stagger_max * 100


def is_staggered(combatant):
    return combatant._in_stagger_break
