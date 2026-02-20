"""
Слой 4 — статусные эффекты.

Каждый статус — объект StatusEffect с типом, длительностью и хуками.
Носитель хранит список активных статусов в combatant.statuses.
Тик вызывается вручную в начале хода носителя.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Any


# ---------------------------------------------------------------------------
# Идентификаторы статусов
# ---------------------------------------------------------------------------

# Периодический урон
S_BLEED         = "bleed"
S_BLEED_HEAVY   = "bleed_heavy"
S_POISON        = "poison"
S_POISON_HEAVY  = "poison_heavy"
S_BURN          = "burn"

# Контроль
S_STUN          = "stun"
S_SLEEP         = "sleep"
S_CONFUSION     = "confusion"
S_TERROR        = "terror"
S_GRAB          = "grab"
S_PARALYZE      = "paralyze"
S_SILENCE       = "silence"
S_STAGGER_BREAK = "stagger_break"

# Ослабление
S_BLIND         = "blind"
S_SLOW          = "slow"
S_SLOW_LIGHT    = "slow_light"
S_WEAKNESS      = "weakness"
S_WEAKNESS_HEAVY = "weakness_heavy"
S_DISTRACT      = "distract"
S_DRAIN_MP      = "drain_mp"
S_DRAIN_ENERGY  = "drain_energy"
S_VULNERABLE    = "vulnerable"
S_DEFENSE_BREAK = "defense_break"
S_TAUNT         = "taunt"
S_CURSE         = "curse"

# Стихийные состояния
S_CHILL         = "chill"
S_FROSTBITE     = "frostbite"
S_WET           = "wet"
S_SCORCH        = "scorch"
S_WITHER        = "wither"   # Стихия Увядания

# Позитивные
S_REGEN         = "regen"
S_FOCUS_ATK     = "focus_atk"
S_FOCUS_ACC     = "focus_acc"
S_FOCUS_LUCK    = "focus_luck"
S_HASTE         = "haste"
S_GUARD_AURA    = "guard_aura"
S_MAG_BARRIER   = "mag_barrier"
S_REFLECT       = "reflect"
S_CC_IMMUNE     = "cc_immune"
S_STALWART      = "stalwart"
S_INVINCIBLE    = "invincible"
S_SPIRIT_REGEN  = "spirit_regen"
S_BERSERK       = "berserk"
S_DARK_AURA     = "dark_aura"

# Служебные
S_PROVOKE       = "provoke"
S_EDICT         = "edict"
S_OMEN          = "omen"


# ---------------------------------------------------------------------------
# Категории для быстрых проверок
# ---------------------------------------------------------------------------

CC_STATUSES = {S_STUN, S_SLEEP, S_CONFUSION, S_TERROR, S_GRAB, S_PARALYZE,
               S_SILENCE, S_STAGGER_BREAK}

NEGATIVE_STATUSES = {
    S_BLEED, S_BLEED_HEAVY, S_POISON, S_POISON_HEAVY, S_BURN,
    S_STUN, S_SLEEP, S_CONFUSION, S_TERROR, S_GRAB, S_PARALYZE, S_SILENCE,
    S_BLIND, S_SLOW, S_SLOW_LIGHT, S_WEAKNESS, S_WEAKNESS_HEAVY, S_DISTRACT,
    S_DRAIN_MP, S_DRAIN_ENERGY, S_VULNERABLE, S_DEFENSE_BREAK, S_CURSE,
    S_CHILL, S_FROSTBITE, S_WET, S_SCORCH, S_WITHER, S_STAGGER_BREAK,
}

SKILL_BLOCK_STATUSES = {S_SLOW, S_SILENCE}


# ---------------------------------------------------------------------------
# Класс статуса
# ---------------------------------------------------------------------------

@dataclass
class StatusEffect:
    status_id:  str
    duration:   int
    source:     Any               = None
    power:      float             = 0.0
    on_tick:    Optional[Callable] = None
    on_apply:   Optional[Callable] = None
    on_remove:  Optional[Callable] = None
    stacks:     int               = 1

    def tick(self, owner):
        if self.on_tick:
            self.on_tick(owner, self)
        if self.duration > 0:
            self.duration -= 1
            if self.duration == 0:
                self.remove(owner)
                return True
        return False

    def apply(self, owner):
        if self.on_apply:
            self.on_apply(owner, self)

    def remove(self, owner):
        if self.on_remove:
            self.on_remove(owner, self)


# ---------------------------------------------------------------------------
# Менеджер статусов на Combatant
# ---------------------------------------------------------------------------

def get_statuses(owner):
    if not hasattr(owner, "statuses"):
        owner.statuses = []
    return owner.statuses


def has_status(owner, status_id):
    return any(s.status_id == status_id for s in get_statuses(owner))


def get_status(owner, status_id):
    for s in get_statuses(owner):
        if s.status_id == status_id:
            return s
    return None


def apply_status(owner, effect: StatusEffect, resistance_override=None):
    if hasattr(owner, "resistances"):
        element_map = {
            S_CHILL: "frost", S_FROSTBITE: "frost",
            S_BURN: "fire", S_SCORCH: "fire",
            S_WET: "thunder",
            S_WITHER: "wither",
        }
        if effect.status_id in element_map:
            elem = element_map[effect.status_id]
            if owner.resistances.get(elem, 1.0) == 0.0:
                # Иммунитет к яду может быть временно подавлен Увяданием
                if effect.status_id in (S_POISON, S_POISON_HEAVY):
                    if not getattr(owner, "_wither_suppressed_poison_immunity", False):
                        return False
                else:
                    return False

    if effect.status_id in CC_STATUSES and has_status(owner, S_CC_IMMUNE):
        return False

    statuses = get_statuses(owner)

    stackable = {S_BLEED, S_BLEED_HEAVY, S_POISON, S_POISON_HEAVY}
    if effect.status_id in stackable:
        existing = get_status(owner, effect.status_id)
        if existing:
            existing.stacks += 1
            existing.duration = max(existing.duration, effect.duration)
            return True

    existing = get_status(owner, effect.status_id)
    if existing:
        existing.duration = max(existing.duration, effect.duration)
        existing.power    = effect.power
        return True

    statuses.append(effect)
    effect.apply(owner)
    return True


def remove_status(owner, status_id):
    statuses = get_statuses(owner)
    for s in list(statuses):
        if s.status_id == status_id:
            s.remove(owner)
            statuses.remove(s)
            return True
    return False


def tick_statuses(owner):
    statuses = get_statuses(owner)
    expired = []
    for s in list(statuses):
        done = s.tick(owner)
        if done:
            statuses.remove(s)
            expired.append(s.status_id)
    return expired


def clear_statuses(owner, negative_only=False):
    statuses = get_statuses(owner)
    if negative_only:
        to_remove = [s for s in statuses if s.status_id in NEGATIVE_STATUSES]
    else:
        to_remove = list(statuses)
    for s in to_remove:
        s.remove(owner)
        statuses.remove(s)


def skills_blocked(owner) -> bool:
    return any(has_status(owner, sid) for sid in SKILL_BLOCK_STATUSES)


# ---------------------------------------------------------------------------
# Фабрики — периодический урон
# ---------------------------------------------------------------------------

def _bleed_tick(owner, effect):
    dmg = max(1, int(effect.power * effect.stacks))
    owner.take_damage(dmg)
    effect._tick_log = f"BLEED x{effect.stacks} -{dmg} HP"

def make_bleed(duration=3, power=8.0):
    return StatusEffect(S_BLEED, duration=duration, power=power, on_tick=_bleed_tick)

def make_bleed_heavy(duration=3, power=14.0):
    return StatusEffect(S_BLEED_HEAVY, duration=duration, power=power, on_tick=_bleed_tick)


def _poison_tick(owner, effect):
    from combat.elemental_reactions import get_poison_damage_mult
    base = effect.power
    mult = get_poison_damage_mult(owner)
    dmg = max(1, int(base * effect.stacks * mult))
    owner.take_damage(dmg)
    effect._tick_log = f"POISON x{effect.stacks} -{dmg} HP"

def make_poison(duration=4, power=6.0):
    return StatusEffect(S_POISON, duration=duration, power=power, on_tick=_poison_tick)

def make_poison_heavy(duration=4, power=12.0, source=None):
    def tick(owner, effect):
        from combat.elemental_reactions import get_poison_damage_mult
        base = effect.power
        if effect.source is not None:
            base = max(base, effect.source.sense * 0.6)
        mult = get_poison_damage_mult(owner)
        dmg = max(1, int(base * effect.stacks * mult))
        owner.take_damage(dmg)
        effect._tick_log = f"POISON_HEAVY x{effect.stacks} -{dmg} HP"
    return StatusEffect(S_POISON_HEAVY, duration=duration, power=power,
                        source=source, on_tick=tick)


# Горение
_BURN_HEAL_REDUCTION = 0.4

def _burn_apply(owner, effect):
    owner._burn_heal_mod = getattr(owner, "_burn_heal_mod", 1.0) * (1.0 - _BURN_HEAL_REDUCTION)
    if has_status(owner, S_CHILL):
        remove_status(owner, S_CHILL)

def _burn_remove(owner, effect):
    owner._burn_heal_mod = 1.0

def _burn_tick(owner, effect):
    dmg = max(1, int(effect.power))
    owner.take_damage(dmg)
    effect._tick_log = f"BURN -{dmg} HP"

def make_burn(duration=3, power=5.0):
    return StatusEffect(S_BURN, duration=duration, power=power,
                        on_apply=_burn_apply, on_remove=_burn_remove, on_tick=_burn_tick)


# Увядание
_WITHER_HEAL_REDUCTION = 0.7   # эффективность лечения снижена на 70%
_WITHER_STAT_DECAY     = 0.05  # снижение атакующих параметров за тик

def _wither_apply(owner, effect):
    owner._wither_heal_mod_saved = getattr(owner, "_burn_heal_mod", 1.0)
    owner._burn_heal_mod = getattr(owner, "_burn_heal_mod", 1.0) * (1.0 - _WITHER_HEAL_REDUCTION)

def _wither_remove(owner, effect):
    if hasattr(owner, "_wither_heal_mod_saved"):
        owner._burn_heal_mod = owner._wither_heal_mod_saved
        del owner._wither_heal_mod_saved
    owner._wither_poison_active = False

def _wither_tick(owner, effect):
    dmg = max(1, int(effect.power))
    owner.take_damage(dmg)
    # Постепенное снижение атакующих параметров
    owner._weakness_mult = max(0.4, getattr(owner, "_weakness_mult", 1.0) - _WITHER_STAT_DECAY)
    effect._tick_log = f"WITHER -{dmg} HP, weakness_mult={owner._weakness_mult:.2f}"

def make_wither(duration=4, power=4.0):
    return StatusEffect(S_WITHER, duration=duration, power=power,
                        on_apply=_wither_apply, on_remove=_wither_remove,
                        on_tick=_wither_tick)


# ---------------------------------------------------------------------------
# Фабрики — регенерация
# ---------------------------------------------------------------------------

def _regen_tick(owner, effect):
    amt = max(1, int(effect.power))
    owner.heal(amt)
    effect._tick_log = f"REGEN +{amt} HP"

def make_regen(duration=3, power=15.0):
    return StatusEffect(S_REGEN, duration=duration, power=power, on_tick=_regen_tick)


def _spirit_regen_tick(owner, effect):
    amt = max(1, int(effect.power))
    owner.restore_resource(amt)
    effect._tick_log = f"SPIRIT_REGEN +{amt} MP"

def make_spirit_regen(duration=3, power=10.0):
    return StatusEffect(S_SPIRIT_REGEN, duration=duration, power=power,
                        on_tick=_spirit_regen_tick)


# ---------------------------------------------------------------------------
# Фабрики — контроль
# ---------------------------------------------------------------------------

_STUN_MAG_DEF_MULT = 0.75

def _stun_apply(owner, effect):
    from combat.ctb import push_back
    owner._stunned = True
    owner._stun_mag_def_saved = owner.mag_def_stat
    owner.mag_def_stat = owner.mag_def_stat * _STUN_MAG_DEF_MULT
    push_back(owner, 5.0)

def _stun_remove(owner, effect):
    owner._stunned = False
    if hasattr(owner, "_stun_mag_def_saved"):
        owner.mag_def_stat = owner._stun_mag_def_saved
        del owner._stun_mag_def_saved

def make_stun(duration=1):
    return StatusEffect(S_STUN, duration=duration,
                        on_apply=_stun_apply, on_remove=_stun_remove)


def _sleep_apply(owner, effect):
    owner._asleep = True

def _sleep_remove(owner, effect):
    owner._asleep = False

def make_sleep(duration=2):
    return StatusEffect(S_SLEEP, duration=duration,
                        on_apply=_sleep_apply, on_remove=_sleep_remove)


def make_silence(duration=2):
    return StatusEffect(S_SILENCE, duration=duration)


def make_terror(duration=2):
    def apply(owner, effect):
        owner._terrified = True
    def remove(owner, effect):
        owner._terrified = False
    return StatusEffect(S_TERROR, duration=duration,
                        on_apply=apply, on_remove=remove)


_PARALYZE_DEF_MULT = 1.3

def _paralyze_apply(owner, effect):
    from combat.ctb import push_back
    owner._paralyzed = True
    owner._paralyze_def_saved = owner.phys_def_stat, owner.mag_def_stat
    owner.phys_def_stat = owner.phys_def_stat * _PARALYZE_DEF_MULT
    owner.mag_def_stat  = owner.mag_def_stat  * _PARALYZE_DEF_MULT
    push_back(owner, 8.0)

def _paralyze_remove(owner, effect):
    owner._paralyzed = False
    if hasattr(owner, "_paralyze_def_saved"):
        owner.phys_def_stat, owner.mag_def_stat = owner._paralyze_def_saved
        del owner._paralyze_def_saved

def make_paralyze(duration=1):
    return StatusEffect(S_PARALYZE, duration=duration,
                        on_apply=_paralyze_apply, on_remove=_paralyze_remove)


# ---------------------------------------------------------------------------
# Фабрики — ослабление
# ---------------------------------------------------------------------------

def _slow_apply(owner, effect):
    owner._slow_mod = getattr(owner, "_slow_mod", 1.0) * 0.6
    owner.ctb_speed = owner.finesse * 1.5 * owner._slow_mod

def _slow_remove(owner, effect):
    owner._slow_mod = 1.0
    owner.ctb_speed = owner.finesse * 1.5

def make_slow(duration=2):
    return StatusEffect(S_SLOW, duration=duration,
                        on_apply=_slow_apply, on_remove=_slow_remove)


def make_slow_light(duration=2):
    def apply(owner, effect):
        owner._slow_mod = getattr(owner, "_slow_mod", 1.0) * 0.8
        owner.ctb_speed = owner.finesse * 1.5 * owner._slow_mod
    return StatusEffect(S_SLOW_LIGHT, duration=duration,
                        on_apply=apply, on_remove=_slow_remove)


_BLIND_ACC_MULT  = 0.3
_BLIND_EVADE_MULT = 0.7

def _blind_apply(owner, effect):
    owner._blind_acc_saved   = owner.accuracy_pct
    owner._blind_evade_saved = owner.evade_pct
    owner.accuracy_pct = owner.accuracy_pct * _BLIND_ACC_MULT
    owner.evade_pct    = owner.evade_pct    * _BLIND_EVADE_MULT

def _blind_remove(owner, effect):
    if hasattr(owner, "_blind_acc_saved"):
        owner.accuracy_pct = owner._blind_acc_saved
        owner.evade_pct    = owner._blind_evade_saved
        del owner._blind_acc_saved, owner._blind_evade_saved

def make_blind(duration=2):
    return StatusEffect(S_BLIND, duration=duration,
                        on_apply=_blind_apply, on_remove=_blind_remove)


_DISTRACT_ACC_MULT = 0.65

def _distract_apply(owner, effect):
    owner._distract_acc_saved = owner.accuracy_pct
    owner.accuracy_pct = owner.accuracy_pct * _DISTRACT_ACC_MULT

def _distract_remove(owner, effect):
    if hasattr(owner, "_distract_acc_saved"):
        owner.accuracy_pct = owner._distract_acc_saved
        del owner._distract_acc_saved

def make_distract(duration=2):
    return StatusEffect(S_DISTRACT, duration=duration,
                        on_apply=_distract_apply, on_remove=_distract_remove)


_WEAKNESS_MULT       = 0.8
_WEAKNESS_HEAVY_MULT = 0.6

def _make_weakness_factory(status_id, mult):
    def apply(owner, effect):
        owner._weakness_saved = (
            owner.mettle, owner.sense, owner.finesse, owner.glamour,
            owner.phys_def_stat, owner.mag_def_stat,
            owner.accuracy_pct, owner.evade_pct,
        )
        owner.phys_def_stat = owner.phys_def_stat * mult
        owner.mag_def_stat  = owner.mag_def_stat  * mult
        owner.accuracy_pct  = owner.accuracy_pct  * mult
        owner.evade_pct     = owner.evade_pct      * mult
        owner._weakness_mult = mult

    def remove(owner, effect):
        if hasattr(owner, "_weakness_saved"):
            (owner.mettle, owner.sense, owner.finesse, owner.glamour,
             owner.phys_def_stat, owner.mag_def_stat,
             owner.accuracy_pct, owner.evade_pct) = owner._weakness_saved
            del owner._weakness_saved
        owner._weakness_mult = 1.0

    return StatusEffect(status_id, duration=0,
                        on_apply=apply, on_remove=remove)

def make_weakness(duration=3):
    s = _make_weakness_factory(S_WEAKNESS, _WEAKNESS_MULT)
    s.duration = duration
    return s

def make_weakness_heavy(duration=3):
    s = _make_weakness_factory(S_WEAKNESS_HEAVY, _WEAKNESS_HEAVY_MULT)
    s.duration = duration
    return s


def make_vulnerable(duration=3, physical=True):
    def apply(owner, effect):
        if physical:
            owner._vuln_phys_saved = owner.phys_def_stat
            owner.phys_def_stat = owner.phys_def_stat * 0.75
        else:
            owner._vuln_mag_saved = owner.mag_def_stat
            owner.mag_def_stat = owner.mag_def_stat * 0.75

    def remove(owner, effect):
        if physical and hasattr(owner, "_vuln_phys_saved"):
            owner.phys_def_stat = owner._vuln_phys_saved
            del owner._vuln_phys_saved
        elif not physical and hasattr(owner, "_vuln_mag_saved"):
            owner.mag_def_stat = owner._vuln_mag_saved
            del owner._vuln_mag_saved

    return StatusEffect(S_VULNERABLE, duration=duration,
                        on_apply=apply, on_remove=remove)


def make_defense_break(duration=2):
    return StatusEffect(S_DEFENSE_BREAK, duration=duration)


_CURSE_LUCK_MULT = 0.5

def _curse_apply(owner, effect):
    owner._curse_luck_saved  = owner.luck
    owner._curse_crit_saved  = owner.crit_chance, owner.crit_mult
    owner.luck        = max(0, int(owner.luck * _CURSE_LUCK_MULT))
    owner.crit_chance = owner.crit_chance * 0.5
    owner.crit_mult   = max(1.0, owner.crit_mult - 0.3)

def _curse_remove(owner, effect):
    if hasattr(owner, "_curse_luck_saved"):
        owner.luck       = owner._curse_luck_saved
        owner.crit_chance, owner.crit_mult = owner._curse_crit_saved
        del owner._curse_luck_saved, owner._curse_crit_saved

def make_curse(duration=3):
    return StatusEffect(S_CURSE, duration=duration,
                        on_apply=_curse_apply, on_remove=_curse_remove)


# ---------------------------------------------------------------------------
# Фабрики — стихийные состояния
# ---------------------------------------------------------------------------

_CHILL_FROST_VULN = 0.25

def _chill_apply(owner, effect):
    from combat.ctb import push_back
    push_back(owner, 4.0)
    owner._chill_frost_bonus = _CHILL_FROST_VULN
    if has_status(owner, S_BURN):
        remove_status(owner, S_BURN)

def _chill_remove(owner, effect):
    owner._chill_frost_bonus = 0.0

def _chill_tick(owner, effect):
    dmg = max(1, int(effect.power))
    owner.take_damage(dmg)

def make_chill(duration=3, power=3.0):
    return StatusEffect(S_CHILL, duration=duration, power=power,
                        on_apply=_chill_apply, on_remove=_chill_remove,
                        on_tick=_chill_tick)


def _wet_apply(owner, effect):
    owner._wet_active = True

def _wet_remove(owner, effect):
    owner._wet_active = False

def make_wet(duration=4):
    return StatusEffect(S_WET, duration=duration,
                        on_apply=_wet_apply, on_remove=_wet_remove)


def _frostbite_apply(owner, effect):
    from combat.ctb import push_back
    push_back(owner, 10.0)
    owner._chill_frost_bonus = _CHILL_FROST_VULN * 2

def _frostbite_remove(owner, effect):
    owner._chill_frost_bonus = 0.0

def _frostbite_tick(owner, effect):
    dmg = max(1, int(effect.power))
    owner.take_damage(dmg)

def make_frostbite(duration=3, power=8.0):
    return StatusEffect(S_FROSTBITE, duration=duration, power=power,
                        on_apply=_frostbite_apply, on_remove=_frostbite_remove,
                        on_tick=_frostbite_tick)
