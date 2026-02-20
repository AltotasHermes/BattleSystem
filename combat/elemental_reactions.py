"""
combat/elemental_reactions.py
Стихийные взаимодействия — срабатывают после применения атаки к цели.

check_elemental_reaction() вызывается из execute_basic_attack() и скиллов
сразу после того как урон и stagger зафиксированы, до записи в лог.

Каждая реакция возвращает список строк для лога или пустой список.
"""

from combat.status import (
    has_status, remove_status, apply_status, get_status,
    make_stun, make_chill,
    S_CHILL, S_BURN, S_WET, S_WITHER, S_POISON, S_POISON_HEAVY,
    S_PARALYZE,
)
from combat.damage import (
    DMG_FIRE, DMG_FROST, DMG_THUNDER, DMG_WITHER,
)


# ---------------------------------------------------------------------------
# Длительность оглушения от взрыва пара
# ---------------------------------------------------------------------------

_STEAM_BURST_STUN_DURATION = 1

# Бонус шанса наложения Озноба на цели с Промокшим или Увяданием
CHILL_BONUS_CHANCE_WET    = 0.35   # абсолютный бонус к шансу
CHILL_BONUS_CHANCE_WITHER = 0.30

# Множитель урона от Яда при активном Увядании
POISON_WITHER_DMG_MULT = 2.0

# Флаг на объекте статуса: иммунитет к яду временно подавлен
_WITHER_POISON_IMMUNITY_SUPPRESS = "_wither_suppresses_poison_immunity"


# ---------------------------------------------------------------------------
# Вспомогательная функция оглушения от взрыва пара
# ---------------------------------------------------------------------------

def _apply_steam_burst(target, log):
    """Накладывает оглушение взрыва пара и пишет в лог."""
    applied = apply_status(target, make_stun(duration=_STEAM_BURST_STUN_DURATION))
    if applied:
        log.append(f"{target.name}: взрыв пара — оглушение!")
    return applied


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------

def check_elemental_reaction(attacker, target, damage_type, log,
                               status_being_applied=None,
                               status_apply_chance_ref=None):
    """
    Проверяет и разрешает стихийные взаимодействия.

    attacker              — Combatant, совершающий атаку
    target                — Combatant, получающий атаку
    damage_type           — одна из констант DMG_*
    log                   — список строк лога боя (изменяется на месте)
    status_being_applied  — идентификатор статуса который скилл собирается наложить
                            (например S_CHILL, S_BURN). Реакция может заблокировать
                            наложение, вернув False из get_status_apply_allowed().
    status_apply_chance_ref — список из одного float [шанс] — реакция может
                              изменить значение шанса для наложения статуса.

    Возвращает True если статус разрешён к наложению, False если заблокирован.
    """
    allowed = True

    # --- Озноб + Огонь → взрыв пара ---
    if damage_type == DMG_FIRE and has_status(target, S_CHILL):
        remove_status(target, S_CHILL)
        _apply_steam_burst(target, log)
        # Горение накладывается в штатном режиме (Озноб уже снят)

    # --- Горение + Мороз → взрыв пара ---
    elif damage_type == DMG_FROST and has_status(target, S_BURN):
        remove_status(target, S_BURN)
        _apply_steam_burst(target, log)
        # Озноб накладывается в штатном режиме (Горение уже снято)

    # --- Промокший + Огонь → Промокший снят, Горение заблокировано ---
    elif damage_type == DMG_FIRE and has_status(target, S_WET):
        remove_status(target, S_WET)
        log.append(f"{target.name}: вода гасит огонь — Горение не накладывается.")
        if status_being_applied == S_BURN:
            allowed = False

    # --- Промокший + Мороз → повышенный шанс Озноба ---
    elif damage_type == DMG_FROST and has_status(target, S_WET):
        if status_being_applied == S_CHILL and status_apply_chance_ref is not None:
            status_apply_chance_ref[0] = min(1.0,
                status_apply_chance_ref[0] + CHILL_BONUS_CHANCE_WET)

    # --- Промокший + Гроза → Паралич повышенной длительности ---
    elif damage_type == DMG_THUNDER and has_status(target, S_WET):
        if status_being_applied == S_PARALYZE and status_apply_chance_ref is not None:
            # Не меняем шанс, но скилл должен учесть флаг для длительности
            # Флаг читается в make_paralyze_wet() ниже
            target._wet_paralyze_bonus = True

    # --- Увядание + Мороз → повышенный шанс Озноба ---
    elif damage_type == DMG_FROST and has_status(target, S_WITHER):
        if status_being_applied == S_CHILL and status_apply_chance_ref is not None:
            status_apply_chance_ref[0] = min(1.0,
                status_apply_chance_ref[0] + CHILL_BONUS_CHANCE_WITHER)

    # --- Озноб + Увядание → повышенный шанс повторного Озноба ---
    elif damage_type == DMG_WITHER and has_status(target, S_CHILL):
        if status_being_applied == S_CHILL and status_apply_chance_ref is not None:
            status_apply_chance_ref[0] = min(1.0,
                status_apply_chance_ref[0] + CHILL_BONUS_CHANCE_WITHER)

    return allowed


# ---------------------------------------------------------------------------
# Проверка для Увядания + Яд (вызывается при попытке наложить Яд)
# ---------------------------------------------------------------------------

def check_wither_poison(target):
    """
    Вызывается перед наложением S_POISON / S_POISON_HEAVY на цель.
    Если на цели есть S_WITHER:
      - временно подавляет иммунитет к яду
      - устанавливает флаг усиления урона от яда

    Возвращает True если наложение разрешено (включая случай подавленного иммунитета).
    """
    if not has_status(target, S_WITHER):
        return True

    # Отмечаем что урон яда должен быть усилен
    target._wither_poison_active = True

    # Временно подавляем иммунитет к яду чтобы apply_status не заблокировал
    if hasattr(target, "resistances"):
        poison_res = target.resistances.get("poison", 1.0)
        if poison_res == 0.0:
            target._wither_suppressed_poison_immunity = True
            target.resistances["poison"] = 1.0   # временно снимаем иммунитет

    return True


def restore_poison_immunity(target):
    """
    Вызывается после того как apply_status для яда завершён.
    Восстанавливает подавленный иммунитет.
    """
    if getattr(target, "_wither_suppressed_poison_immunity", False):
        if hasattr(target, "resistances"):
            target.resistances["poison"] = 0.0
        target._wither_suppressed_poison_immunity = False


# ---------------------------------------------------------------------------
# Модификатор урона яда (вызывается внутри _poison_tick в status.py)
# ---------------------------------------------------------------------------

def get_poison_damage_mult(target):
    """Возвращает множитель урона яда с учётом Увядания."""
    if getattr(target, "_wither_poison_active", False):
        return POISON_WITHER_DMG_MULT
    return 1.0


# ---------------------------------------------------------------------------
# Параметры Паралича с учётом Промокшего
# ---------------------------------------------------------------------------

_WET_PARALYZE_DURATION_BONUS = 1   # дополнительный ход длительности

def get_paralyze_duration(target, base_duration):
    """Возвращает длительность Паралича с учётом Промокшего."""
    bonus = 0
    if getattr(target, "_wet_paralyze_bonus", False):
        bonus = _WET_PARALYZE_DURATION_BONUS
        target._wet_paralyze_bonus = False
    return base_duration + bonus
