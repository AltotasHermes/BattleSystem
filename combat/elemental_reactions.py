"""
combat/elemental_reactions.py
Стихийные взаимодействия — срабатывают после применения атаки к цели.

check_elemental_reaction() вызывается из execute_basic_attack() и скиллов
сразу после того как урон и stagger зафиксированы, до записи в лог.

ВАЖНО — разделение ответственности:
    Взаимное снятие Горения и Озноба при наложении противоположного статуса
    обрабатывается ТОЛЬКО в on_apply хуках make_burn() и make_chill() в status.py.
    Здесь эта логика не дублируется.

    get_poison_damage_mult() и POISON_WITHER_DMG_MULT живут в status.py,
    чтобы избежать циклического импорта (status.py -> elemental_reactions.py -> status.py).
"""

from dataclasses import dataclass
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
# Параметры наложения статуса
# Заменяет список-обёртку [float] для передачи изменяемого шанса.
# ---------------------------------------------------------------------------

@dataclass
class StatusApplyParams:
    """
    Передаётся в check_elemental_reaction() вместо отдельных аргументов.
    Реакция может изменить chance и флаги — вызывающий код читает
    результат из того же объекта после вызова.

    status_id   — идентификатор статуса который скилл собирается наложить
    chance      — базовый шанс наложения (0.0..1.0); реакция может повысить
    wet_paralyze_extended — флаг: Промокший+Гроза дают удлинённый Паралич
    allowed     — False если реакция заблокировала наложение статуса
    """
    status_id:              str   = ""
    chance:                 float = 1.0
    wet_paralyze_extended:  bool  = False
    allowed:                bool  = True


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

_STEAM_BURST_STUN_DURATION = 1

CHILL_BONUS_CHANCE_WET    = 0.35
CHILL_BONUS_CHANCE_WITHER = 0.30


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
                              params: StatusApplyParams = None):
    """
    Проверяет и разрешает стихийные взаимодействия.

    attacker    — Combatant, совершающий атаку
    target      — Combatant, получающий атаку
    damage_type — одна из констант DMG_*
    log         — список строк лога боя (изменяется на месте)
    params      — StatusApplyParams; реакция может изменить params.chance,
                  params.allowed, params.wet_paralyze_extended.
                  Если None — реакция не затрагивает наложение статуса.

    Возвращает params (тот же объект, изменённый на месте), либо None
    если params не передан.

    Взаимное снятие Горения/Озноба при наложении противоположного статуса
    делается в on_apply хуках make_burn/make_chill — здесь не дублируется.
    Здесь обрабатывается только взрыв пара (Горение+Мороз / Мороз+Горение).
    """
    sid = params.status_id if params is not None else ""

    # --- Горение + Мороз → взрыв пара (Горение уже есть, бьём Морозом) ---
    if damage_type == DMG_FROST and has_status(target, S_BURN):
        remove_status(target, S_BURN)
        _apply_steam_burst(target, log)
        # Озноб накладывается штатно (make_chill.on_apply снял бы Горение,
        # но оно уже снято выше — дублирования нет)

    # --- Озноб + Огонь → взрыв пара (Озноб уже есть, бьём Огнём) ---
    elif damage_type == DMG_FIRE and has_status(target, S_CHILL):
        remove_status(target, S_CHILL)
        _apply_steam_burst(target, log)
        # Горение накладывается штатно (make_burn.on_apply снял бы Озноб,
        # но он уже снят выше)

    # --- Промокший + Огонь → Промокший снят, Горение заблокировано ---
    elif damage_type == DMG_FIRE and has_status(target, S_WET):
        remove_status(target, S_WET)
        log.append(f"{target.name}: вода гасит огонь — Горение не накладывается.")
        if params is not None and sid == S_BURN:
            params.allowed = False

    # --- Промокший + Мороз → повышенный шанс Озноба ---
    elif damage_type == DMG_FROST and has_status(target, S_WET):
        if params is not None and sid == S_CHILL:
            params.chance = min(1.0, params.chance + CHILL_BONUS_CHANCE_WET)

    # --- Промокший + Гроза → Паралич удлинённой длительности ---
    elif damage_type == DMG_THUNDER and has_status(target, S_WET):
        if params is not None and sid == S_PARALYZE:
            params.wet_paralyze_extended = True

    # --- Увядание + Мороз → повышенный шанс Озноба ---
    elif damage_type == DMG_FROST and has_status(target, S_WITHER):
        if params is not None and sid == S_CHILL:
            params.chance = min(1.0, params.chance + CHILL_BONUS_CHANCE_WITHER)

    # --- Озноб + Увядание → повышенный шанс повторного Озноба ---
    elif damage_type == DMG_WITHER and has_status(target, S_CHILL):
        if params is not None and sid == S_CHILL:
            params.chance = min(1.0, params.chance + CHILL_BONUS_CHANCE_WITHER)

    return params


# ---------------------------------------------------------------------------
# Проверка для Увядания + Яд
# ---------------------------------------------------------------------------

def check_wither_poison(target):
    """
    Вызывается перед наложением S_POISON / S_POISON_HEAVY на цель.
    Если на цели есть S_WITHER — временно подавляет иммунитет к яду
    и устанавливает флаг усиления урона (_wither_poison_active).

    Флаг _wither_poison_active читается через get_poison_damage_mult()
    в status.py — без обратного импорта elemental_reactions.
    """
    if not has_status(target, S_WITHER):
        return True

    target._wither_poison_active = True

    if hasattr(target, "resistances"):
        poison_res = target.resistances.get("poison", 1.0)
        if poison_res == 0.0:
            target._wither_suppressed_poison_immunity = True
            target.resistances["poison"] = 1.0

    return True


def restore_poison_immunity(target):
    """
    Вызывается после завершения apply_status для яда.
    Восстанавливает подавленный иммунитет.
    """
    if getattr(target, "_wither_suppressed_poison_immunity", False):
        if hasattr(target, "resistances"):
            target.resistances["poison"] = 0.0
        target._wither_suppressed_poison_immunity = False


# ---------------------------------------------------------------------------
# Длительность Паралича с учётом Промокшего
# ---------------------------------------------------------------------------

_WET_PARALYZE_DURATION_BONUS = 1

def get_paralyze_duration(target, base_duration, params: StatusApplyParams = None):
    """
    Возвращает длительность Паралича с учётом Промокшего.
    Читает флаг из params.wet_paralyze_extended если params передан,
    иначе читает legacy-флаг _wet_paralyze_bonus напрямую с цели.
    """
    if params is not None:
        bonus = _WET_PARALYZE_DURATION_BONUS if params.wet_paralyze_extended else 0
        return base_duration + bonus

    # Обратная совместимость для кода без StatusApplyParams
    bonus = 0
    if getattr(target, "_wet_paralyze_bonus", False):
        bonus = _WET_PARALYZE_DURATION_BONUS
        target._wet_paralyze_bonus = False
    return base_duration + bonus
