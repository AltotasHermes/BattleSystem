"""
Пример стихийного скилла с корректной интеграцией elemental_reactions.
Показывает паттерн для всех скиллов, накладывающих стихийные статусы.

Для физических скиллов (DMG_SLASH / DMG_BLUNT / DMG_BALLISTIC)
check_elemental_reaction вызывается без params — реакции на физический
урон не предусмотрены документом.
"""

import random
from combat.damage import resolve_damage, AttackData, DMG_FROST, DMG_FIRE
from combat.stagger import add_stagger
from combat.status import apply_status, make_chill, make_burn, make_paralyze, S_CHILL, S_BURN, S_PARALYZE
from combat.elemental_reactions import (
    StatusApplyParams,
    check_elemental_reaction,
    check_wither_poison, restore_poison_immunity,
    get_paralyze_duration,
)


# ---------------------------------------------------------------------------
# Паттерн 1: стихийная атака с наложением статуса (Мороз + Озноб)
# ---------------------------------------------------------------------------

def _frost_strike(user, targets, ctx):
    """
    Атака Мороза с шансом наложения Озноба.
    Промокший и Увядание повышают шанс через StatusApplyParams.
    Горение на цели снимается и вызывает взрыв пара.
    """
    for t in targets:
        atk = AttackData(DMG_FROST, scaling_stat=user.sense,
                         weapon_mult=1.2, stagger_fill=0.18, is_magical=True)
        res = resolve_damage(user, t, atk)

        if res.hit and not res.evaded:
            params = StatusApplyParams(status_id=S_CHILL, chance=0.55)
            check_elemental_reaction(user, t, DMG_FROST, ctx.log, params)

            t.take_damage(res.damage)
            add_stagger(t, res.stagger_fill * t.stagger_max)

            if params.allowed and random.random() < params.chance:
                apply_status(t, make_chill(duration=3, power=3.0))

            label = "КРИТ" if res.crit else "удар"
            ctx.log.append(f"{user.name} -> {t.name}: {label} {res.damage} урона [[Мороз]]")


# ---------------------------------------------------------------------------
# Паттерн 2: Огонь + Горение — Промокший блокирует Горение
# ---------------------------------------------------------------------------

def _fire_strike(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_FIRE, scaling_stat=user.sense,
                         weapon_mult=1.3, stagger_fill=0.12, is_magical=True)
        res = resolve_damage(user, t, atk)

        if res.hit and not res.evaded:
            params = StatusApplyParams(status_id=S_BURN, chance=0.50)
            check_elemental_reaction(user, t, DMG_FIRE, ctx.log, params)

            t.take_damage(res.damage)
            add_stagger(t, res.stagger_fill * t.stagger_max)

            if params.allowed and random.random() < params.chance:
                apply_status(t, make_burn(duration=3, power=5.0))

            label = "КРИТ" if res.crit else "удар"
            ctx.log.append(f"{user.name} -> {t.name}: {label} {res.damage} урона [[Огонь]]")


# ---------------------------------------------------------------------------
# Паттерн 3: Гроза + Паралич — Промокший даёт удлинённый Паралич
# ---------------------------------------------------------------------------

def _thunder_strike(user, targets, ctx):
    BASE_PARALYZE_DURATION = 1

    for t in targets:
        atk = AttackData("thunder", scaling_stat=user.sense,
                         weapon_mult=1.1, stagger_fill=0.20, is_magical=True)
        res = resolve_damage(user, t, atk)

        if res.hit and not res.evaded:
            params = StatusApplyParams(status_id=S_PARALYZE, chance=0.45)
            check_elemental_reaction(user, t, "thunder", ctx.log, params)

            t.take_damage(res.damage)
            add_stagger(t, res.stagger_fill * t.stagger_max)

            if params.allowed and random.random() < params.chance:
                # get_paralyze_duration читает wet_paralyze_extended из params
                duration = get_paralyze_duration(t, BASE_PARALYZE_DURATION, params)
                apply_status(t, make_paralyze(duration=duration))

            label = "КРИТ" if res.crit else "удар"
            ctx.log.append(f"{user.name} -> {t.name}: {label} {res.damage} урона [[Гроза]]")


# ---------------------------------------------------------------------------
# Паттерн 4: Яд под Увяданием — подавление иммунитета
# ---------------------------------------------------------------------------

def _apply_poison_with_wither_check(target, poison_effect, log):
    """
    Вспомогательная функция для наложения яда.
    Если на цели Увядание — иммунитет к яду временно снят.
    Множитель урона (_wither_poison_active) читается в status.py
    через get_poison_damage_mult() без обратного импорта.
    """
    from combat.status import apply_status as _apply
    check_wither_poison(target)
    result = _apply(target, poison_effect)
    restore_poison_immunity(target)
    if result:
        if getattr(target, "_wither_poison_active", False):
            log.append(f"{target.name}: яд усилен Увяданием.")
        else:
            log.append(f"{target.name}: отравлен.")
    return result
