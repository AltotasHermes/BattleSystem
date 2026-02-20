"""
Слой 3 — разрешение урона.

resolve_damage() принимает атакующего, цель и данные атаки.
Возвращает DamageResult без побочных эффектов —
применение урона к цели остаётся за вызывающим кодом.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Optional

# --- Константа балансировки защиты ---
DEFENSE_K = 75.0

# --- Типы урона ---
# Физические
DMG_SLASH    = "slash"
DMG_BLUNT    = "blunt"
DMG_BALLISTIC = "ballistic"
# Стихийные
DMG_FIRE     = "fire"
DMG_FROST    = "frost"
DMG_THUNDER  = "thunder"
DMG_WITHER   = "wither"

PHYSICAL_TYPES  = {DMG_SLASH, DMG_BLUNT, DMG_BALLISTIC}
ELEMENTAL_TYPES = {DMG_FIRE, DMG_FROST, DMG_THUNDER, DMG_WITHER}


# --- Данные атаки ---

@dataclass
class AttackData:
    """Описание одной атаки. Задаётся на уровне скилла или базовой атаки."""
    damage_type:   str            # одна из констант DMG_*
    scaling_stat:  float          # значение стата урона (mettle/sense/finesse/glamour)
    weapon_mult:   float = 1.0    # множитель оружия
    stagger_fill:  float = 0.15   # вклад в stagger-шкалу (0.0 – 1.0)
    is_magical:    bool  = False   # определяет какую защиту использовать
    can_crit:      bool  = True


# --- Результат атаки ---

@dataclass
class DamageResult:
    hit:          bool  = False
    crit:         bool  = False
    damage:       int   = 0
    stagger_fill: float = 0.0
    evaded:       bool  = False   # True если уклонение сработало
    log:          list  = field(default_factory=list)  # отладочная цепочка


# --- Вспомогательные функции ---

def _defense_pct(stat, armor, k=DEFENSE_K):
    total = stat + armor
    return total / (total + k)


def _raw_damage(scaling_stat, weapon_mult):
    spread = random.uniform(0.85, 1.15)
    return (scaling_stat ** 1.4) * weapon_mult * spread


def _resistance_mult(target, damage_type):
    """
    Возвращает множитель урона из профиля сопротивлений цели.
    Профиль хранится как dict в target.resistances.
    Если тип отсутствует — норма (1.0).
    Специальное значение 'absorb' обрабатывается отдельно.
    """
    if not hasattr(target, "resistances"):
        return 1.0
    val = target.resistances.get(damage_type, 1.0)
    return val  # 'absorb' проверяется в resolve_damage


# --- Основная функция ---

def resolve_damage(attacker, target, atk: AttackData) -> DamageResult:
    res = DamageResult()

    # 1. Проверка уклонения
    evade_chance = max(0.0, target.evade_pct - attacker.accuracy_pct)
    if random.random() < evade_chance:
        res.evaded = True
        res.log.append(f"EVADE ({evade_chance*100:.1f}% шанс)")
        return res

    res.hit = True

    # 2. Сопротивление цели
    resist = _resistance_mult(target, atk.damage_type)

    # Абсорб — урон превращается в лечение
    if resist == "absorb":
        raw = _raw_damage(atk.scaling_stat, atk.weapon_mult)
        res.damage = -int(round(raw))   # отрицательный урон = лечение
        res.log.append(f"ABSORB heal={-res.damage}")
        return res

    if resist == 0.0:
        res.log.append("IMMUNE")
        return res

    # 3. Базовый урон
    raw = _raw_damage(atk.scaling_stat, atk.weapon_mult)

    # 4. Крит
    if atk.can_crit and random.random() < attacker.crit_chance:
        res.crit = True
        raw *= attacker.crit_mult

    # 5. Защита
    if atk.is_magical:
        def_pct = _defense_pct(target.mag_def_stat, target.magic_armor)
    else:
        def_pct = _defense_pct(target.phys_def_stat, target.armor)

    # 6. Итоговый урон с сопротивлением
    final = raw * resist * (1.0 - def_pct)
    res.damage = max(1, int(round(final)))  # минимум 1 урона если попало

    # 7. Stagger
    res.stagger_fill = atk.stagger_fill * resist  # иммунитет к стихии = нет stagger от неё

    res.log.append(
        f"raw={raw:.1f} resist=x{resist} "
        f"def={def_pct*100:.1f}% "
        f"{'CRIT ' if res.crit else ''}"
        f"-> {res.damage} dmg  stagger+{res.stagger_fill:.2f}"
    )
    return res
