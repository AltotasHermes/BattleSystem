"""
Скиллы Леди Веспергрейв.

Ветви:
    Озноб           (стартовая)
    Ледяной барьер  (открывается по нарративу)
    Владычество     (открывается через личный квест)

Ресурс: Эфир (MP). Базовый пул 120, шкала полна в начале боя.
Базовая атака тратит 10 Эфира.

ПАССИВЫ (6 штук, по 2 на ветвь):

    Озноб:
        Хрупкость       — цель под Ознобом получает +50% к stagger-вкладу атак
        Глубокий холод  — повторное наложение Озноба продлевает его вместо сброса

    Ледяной барьер:
        Вечная мерзлота — пока союзник под Барьером/Отражением, Веспергрейв
                          получает бонус +8 к магической защите
        Ледяная реакция — если союзник получает удар >= ПОРОГ_РЕАКЦИИ урона,
                          Веспергрейв получает лёгкий ускорение в CTB (push_back -4)

    Владычество:
        Регентская воля — при наложении любого дебаффа на врага все союзники
                          получают лёгкий ускорение в CTB (push_back -2)
        Холодный расчёт — если Веспергрейв наложила >= 2 дебаффов за ход,
                          следующая способность стоит на 10 Эфира дешевле
"""

import random

from combat.skills import (
    Skill, SkillSet,
    TARGET_SINGLE, TARGET_SELF, TARGET_ALL_FOE, TARGET_ALL_ALLY, TARGET_AREA_FOE,
)
from combat.ctb import ActionWeight, push_back
from combat.damage import resolve_damage, AttackData, DMG_FROST
from combat.stagger import add_stagger
from combat.status import (
    apply_status, remove_status, has_status, get_status,
    make_chill, make_slow, make_slow_light, make_wet,
    StatusEffect,
    S_CHILL, S_FROSTBITE, S_WET, S_SLOW, S_SLOW_LIGHT,
    NEGATIVE_STATUSES,
)
from combat.elemental_reactions import StatusApplyParams, check_elemental_reaction

BRANCH_CHILL   = "Озноб"
BRANCH_BARRIER = "Ледяной барьер"
BRANCH_RULE    = "Владычество"

# Идентификаторы служебных статусов
S_ICE_BARRIER  = "ice_barrier"
S_ICE_SHELL    = "ice_shell"
S_REFLECT_ICE  = "reflect_ice"
S_EDICT        = "edict"

# Порог урона для Ледяной реакции (абсолютное значение)
_REACTION_THRESHOLD        = 25
_REACTION_THRESHOLD_ITEM   = 15   # с Походным плащом

# Бонус магзащиты от Вечной мерзлоты
_PERMAFROST_MAG_DEF_BONUS  = 8

# Скидка Эфира от Холодного расчёта
_COLD_CALC_DISCOUNT        = 10


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _frost_hit(user, target, weapon_mult, stagger_fill, ctx):
    """Базовый удар Морозом. Возвращает DamageResult."""
    atk = AttackData(
        damage_type=DMG_FROST,
        scaling_stat=user.sense,
        weapon_mult=weapon_mult,
        stagger_fill=stagger_fill,
        is_magical=True,
    )
    res = resolve_damage(user, target, atk)
    if res.hit and not res.evaded:
        # Хрупкость: если на цели Озноб — stagger-вклад увеличен
        sf = res.stagger_fill
        if has_status(target, S_CHILL) or has_status(target, S_FROSTBITE):
            if getattr(user, "_fragility_passive", False):
                sf *= 1.5
        target.take_damage(res.damage)
        add_stagger(target, sf * target.stagger_max)
        label = "КРИТ" if res.crit else "удар"
        ctx.log.append(f"{user.name} -> {target.name}: {label} {res.damage} [[Мороз]]")
    elif res.evaded:
        ctx.log.append(f"{user.name} -> {target.name}: уклонение")
    return res


def _try_apply_chill(user, target, base_chance, duration, power, ctx):
    """
    Накладывает Озноб с учётом Глубокого холода и стихийных реакций.
    Если на цели уже Озноб и активен Глубокий холод — продлевает вместо сброса.
    """
    params = StatusApplyParams(status_id=S_CHILL, chance=base_chance)
    check_elemental_reaction(user, target, DMG_FROST, ctx.log, params)

    if not params.allowed:
        return False

    if random.random() >= params.chance:
        return False

    existing = get_status(target, S_CHILL)
    if existing and getattr(user, "_deep_cold_passive", False):
        # Глубокий холод: продлеваем вместо сброса
        existing.duration += duration
        ctx.log.append(f"{target.name}: Глубокий холод — Озноб продлён [[+{duration}]].")
        return True

    applied = apply_status(target, make_chill(duration=duration, power=power))
    if applied:
        ctx.log.append(f"{target.name}: Озноб.")
    return applied


def _apply_chill_with_log(user, target, duration, ctx):
    """Упрощённый вызов для скиллов с гарантированным Ознобом."""
    _try_apply_chill(user, target, base_chance=1.0,
                     duration=duration, power=3.0, ctx=ctx)


def _cost_discount(user):
    """Скидка Эфира от Холодного расчёта."""
    return getattr(user, "_cold_calc_discount_pending", 0)


def _spend_with_discount(user, base_cost):
    """Тратит Эфир с учётом скидки. Возвращает True если хватило."""
    disc = _cost_discount(user)
    actual = max(0, base_cost - disc)
    if user.resource_current < actual:
        return False
    user.resource_current -= actual
    user._cold_calc_discount_pending = 0
    return True


# ---------------------------------------------------------------------------
# ВЕТВЬ: ОЗНОБ — активные скиллы
# ---------------------------------------------------------------------------

def _ice_arrow_1(user, targets, ctx):
    for t in targets:
        res = _frost_hit(user, t, weapon_mult=1.0, stagger_fill=0.12, ctx=ctx)
        if res.hit and not res.evaded:
            _try_apply_chill(user, t, base_chance=0.40, duration=3, power=3.0, ctx=ctx)

def _ice_arrow_2(user, targets, ctx):
    for t in targets:
        bonus_mult = 1.25 if (has_status(t, S_CHILL) or has_status(t, S_FROSTBITE)) else 1.0
        res = _frost_hit(user, t, weapon_mult=1.1 * bonus_mult, stagger_fill=0.14, ctx=ctx)
        if res.hit and not res.evaded:
            _try_apply_chill(user, t, base_chance=0.60, duration=3, power=3.0, ctx=ctx)

def _ice_arrow_3(user, targets, ctx):
    """Стрела раскалывается — поражает цель и одну случайную соседнюю."""
    primary = targets[0] if targets else None
    if primary is None:
        return
    res = _frost_hit(user, primary, weapon_mult=1.0, stagger_fill=0.12, ctx=ctx)
    if res.hit and not res.evaded:
        _try_apply_chill(user, primary, base_chance=0.60, duration=3, power=3.0, ctx=ctx)

    # Соседняя цель (из того же лагеря что primary)
    side = getattr(ctx, "_get_adjacent", None)
    if side:
        splash_target = side(primary)
    else:
        # Запасной вариант: случайная другая цель из врагов/союзников
        pool = [c for c in (ctx.alive_enemies() if primary in ctx.enemies
                             else ctx.alive_party())
                if c is not primary]
        splash_target = random.choice(pool) if pool else None

    if splash_target:
        _frost_hit(user, splash_target, weapon_mult=0.55, stagger_fill=0.08, ctx=ctx)
        _try_apply_chill(user, splash_target, base_chance=0.45, duration=2, power=2.0, ctx=ctx)


def _frostbite_1(user, targets, ctx):
    """Обморожение I: высокий урон, гарантированный Озноб, тяжёлое действие."""
    for t in targets:
        _frost_hit(user, t, weapon_mult=1.6, stagger_fill=0.22, ctx=ctx)
        _apply_chill_with_log(user, t, duration=4, ctx=ctx)

def _frostbite_2(user, targets, ctx):
    """Обморожение II: усиленный Озноб с удлинённым замедлением CTB."""
    for t in targets:
        _frost_hit(user, t, weapon_mult=1.9, stagger_fill=0.25, ctx=ctx)
        # make_chill даёт push_back 4 в on_apply; здесь добавляем ещё 3
        _apply_chill_with_log(user, t, duration=5, ctx=ctx)
        push_back(t, 3.0)

def _frostbite_3(user, targets, ctx):
    """Обморожение III: Озноб + Замедление шага."""
    for t in targets:
        _frost_hit(user, t, weapon_mult=2.1, stagger_fill=0.28, ctx=ctx)
        _apply_chill_with_log(user, t, duration=5, ctx=ctx)
        apply_status(t, make_slow_light(duration=2))
        ctx.log.append(f"{t.name}: Замедление шага.")


def _hoarfrost_1(user, targets, ctx):
    """Иней I: два случайных врага, Озноб + Замедление шага."""
    pool = ctx.alive_enemies()
    chosen = random.sample(pool, min(2, len(pool)))
    for t in chosen:
        _frost_hit(user, t, weapon_mult=0.75, stagger_fill=0.10, ctx=ctx)
        _try_apply_chill(user, t, base_chance=0.70, duration=3, power=2.5, ctx=ctx)
        apply_status(t, make_slow_light(duration=2))

def _hoarfrost_2(user, targets, ctx):
    """Иней II: три случайных врага, Замедление вместо Замедления шага."""
    pool = ctx.alive_enemies()
    chosen = random.sample(pool, min(3, len(pool)))
    for t in chosen:
        _frost_hit(user, t, weapon_mult=0.75, stagger_fill=0.10, ctx=ctx)
        _try_apply_chill(user, t, base_chance=0.70, duration=3, power=2.5, ctx=ctx)
        apply_status(t, make_slow(duration=2))

def _hoarfrost_3(user, targets, ctx):
    """Иней III: все поражённые получают Промокший — синергия с Хисс."""
    pool = ctx.alive_enemies()
    chosen = random.sample(pool, min(3, len(pool)))
    for t in chosen:
        _frost_hit(user, t, weapon_mult=0.75, stagger_fill=0.10, ctx=ctx)
        _try_apply_chill(user, t, base_chance=0.70, duration=3, power=2.5, ctx=ctx)
        apply_status(t, make_slow(duration=2))
        apply_status(t, make_wet(duration=4))
        ctx.log.append(f"{t.name}: Промокший.")


# ---------------------------------------------------------------------------
# ВЕТВЬ: ЛЕДЯНОЙ БАРЬЕР — активные скиллы
# ---------------------------------------------------------------------------

# --- Барьер ---

def _make_barrier_effect(duration, dr, caster=None):
    """
    Барьер: снижает входящий урон (dr = коэффициент снижения).
    Барьер II дополнительно блокирует Горение.
    Барьер III при разрушении накладывает Озноб на атакующего.
    """
    def on_apply(owner, effect):
        owner._barrier_dr     = dr
        owner._barrier_caster = caster
        owner._barrier_active = True
        # Веспергрейв получает бонус от Вечной мерзлоты
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = getattr(caster, "_permafrost_count", 0) + 1
            _update_permafrost(caster)

    def on_remove(owner, effect):
        owner._barrier_dr     = 0.0
        owner._barrier_active = False
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = max(0, getattr(caster, "_permafrost_count", 1) - 1)
            _update_permafrost(caster)

    return StatusEffect(S_ICE_BARRIER, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _update_permafrost(vesp):
    """Обновляет бонус магзащиты от Вечной мерзлоты."""
    count = getattr(vesp, "_permafrost_count", 0)
    if count > 0:
        if not getattr(vesp, "_permafrost_active", False):
            vesp._permafrost_active  = True
            vesp.mag_def_stat       += _PERMAFROST_MAG_DEF_BONUS
    else:
        if getattr(vesp, "_permafrost_active", False):
            vesp._permafrost_active  = False
            vesp.mag_def_stat       -= _PERMAFROST_MAG_DEF_BONUS


def _barrier_1(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_barrier_effect(duration=1, dr=0.30, caster=user))
        ctx.log.append(f"{t.name}: Ледяной барьер [[1 ход]].")

def _barrier_2(user, targets, ctx):
    for t in targets:
        effect = _make_barrier_effect(duration=2, dr=0.35, caster=user)
        # Барьер II: защита от Горения — флаг читается в apply_status
        orig_apply = effect.on_apply
        def on_apply_2(owner, eff, _oa=orig_apply):
            _oa(owner, eff)
            owner._barrier_blocks_fire = True
        def on_remove_2(owner, eff):
            eff.on_remove(owner, eff)
            owner._barrier_blocks_fire = False
        effect.on_apply  = on_apply_2
        effect.on_remove = on_remove_2
        apply_status(t, effect)
        ctx.log.append(f"{t.name}: Ледяной барьер [[2 хода, блок Огня]].")

def _barrier_3(user, targets, ctx):
    """Барьер III: накладывается на двух союзников."""
    alive = ctx.alive_party()
    chosen = targets[:2] if len(targets) >= 2 else alive[:2]
    for t in chosen:
        effect = _make_barrier_effect(duration=2, dr=0.40, caster=user)
        orig_apply  = effect.on_apply
        orig_remove = effect.on_remove
        def on_apply_3(owner, eff, _oa=orig_apply):
            _oa(owner, eff)
            owner._barrier_cryo_counter = True  # при разрушении — Озноб
        def on_remove_3(owner, eff, _or=orig_remove):
            _or(owner, eff)
            owner._barrier_cryo_counter = False
        effect.on_apply  = on_apply_3
        effect.on_remove = on_remove_3
        apply_status(t, effect)
        ctx.log.append(f"{t.name}: Ледяной барьер [[2 хода, Озноб при разрушении]].")


# --- Ледяной панцирь ---

def _make_shell_effect(duration, phys_dr, mag_dr, speed_penalty, caster):
    def on_apply(owner, effect):
        owner._shell_phys_saved = owner.phys_def_stat
        owner._shell_mag_saved  = owner.mag_def_stat
        owner.phys_def_stat    += phys_dr
        owner.mag_def_stat     += mag_dr
        if speed_penalty:
            push_back(owner, 6.0)
        # Вечная мерзлота
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = getattr(caster, "_permafrost_count", 0) + 1
            _update_permafrost(caster)

    def on_remove(owner, effect):
        if hasattr(owner, "_shell_phys_saved"):
            owner.phys_def_stat = owner._shell_phys_saved
            owner.mag_def_stat  = owner._shell_mag_saved
            del owner._shell_phys_saved, owner._shell_mag_saved
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = max(0, getattr(caster, "_permafrost_count", 1) - 1)
            _update_permafrost(caster)

    return StatusEffect(S_ICE_SHELL, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _ice_shell_1(user, targets, ctx):
    apply_status(user, _make_shell_effect(
        duration=2, phys_dr=10, mag_dr=10, speed_penalty=True, caster=user))
    ctx.log.append(f"{user.name}: Ледяной панцирь — защита +10/+10 [[2 хода]].")

def _ice_shell_2(user, targets, ctx):
    """Панцирь II: атакующий может получить Озноб через контакт."""
    effect = _make_shell_effect(
        duration=2, phys_dr=16, mag_dr=16, speed_penalty=True, caster=user)
    orig_apply  = effect.on_apply
    orig_remove = effect.on_remove
    def on_apply_2(owner, eff, _oa=orig_apply):
        _oa(owner, eff)
        owner._shell_cryo_reflect = True
    def on_remove_2(owner, eff, _or=orig_remove):
        _or(owner, eff)
        owner._shell_cryo_reflect = False
    effect.on_apply  = on_apply_2
    effect.on_remove = on_remove_2
    apply_status(user, effect)
    ctx.log.append(f"{user.name}: Ледяной панцирь — защита +16/+16, Озноб при ударе [[2 хода]].")

def _ice_shell_3(user, targets, ctx):
    """Панцирь III: без штрафа к скорости, длится 3 хода."""
    effect = _make_shell_effect(
        duration=3, phys_dr=16, mag_dr=16, speed_penalty=False, caster=user)
    orig_apply  = effect.on_apply
    orig_remove = effect.on_remove
    def on_apply_3(owner, eff, _oa=orig_apply):
        _oa(owner, eff)
        owner._shell_cryo_reflect = True
    def on_remove_3(owner, eff, _or=orig_remove):
        _or(owner, eff)
        owner._shell_cryo_reflect = False
    effect.on_apply  = on_apply_3
    effect.on_remove = on_remove_3
    apply_status(user, effect)
    ctx.log.append(f"{user.name}: Несокрушимый панцирь [[3 хода]].")


# --- Отражение ---

def _make_reflect_effect(charges, caster, dmg_return=False):
    """
    Отражение: следующие N атак по союзнику отражаются — атакующий получает Озноб.
    Отражение III: урон возвращается, атакующий получает Откат.
    """
    def on_apply(owner, effect):
        owner._reflect_charges = charges
        owner._reflect_dmg_return = dmg_return
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = getattr(caster, "_permafrost_count", 0) + 1
            _update_permafrost(caster)

    def on_remove(owner, effect):
        owner._reflect_charges    = 0
        owner._reflect_dmg_return = False
        if caster and hasattr(caster, "_permafrost_passive"):
            caster._permafrost_count = max(0, getattr(caster, "_permafrost_count", 1) - 1)
            _update_permafrost(caster)

    return StatusEffect(S_REFLECT_ICE, duration=99,
                        on_apply=on_apply, on_remove=on_remove)

def _reflect_1(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_reflect_effect(charges=1, caster=user, dmg_return=False))
        ctx.log.append(f"{t.name}: Отражение [[1 заряд]].")

def _reflect_2(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_reflect_effect(charges=2, caster=user, dmg_return=False))
        ctx.log.append(f"{t.name}: Отражение [[2 заряда]].")

def _reflect_3(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_reflect_effect(charges=2, caster=user, dmg_return=True))
        ctx.log.append(f"{t.name}: Отражение с возвратом [[2 заряда, +Откат]].")


# ---------------------------------------------------------------------------
# ВЕТВЬ: ВЛАДЫЧЕСТВО — активные скиллы
# ---------------------------------------------------------------------------

# --- Зимний приговор ---

def _winter_verdict_1(user, targets, ctx):
    for t in targets:
        ctx.apply_debuff_with_passives(user, t, make_slow(duration=2))
        ctx.log.append(f"{t.name}: Зимний приговор — Замедление.")

def _winter_verdict_2(user, targets, ctx):
    for t in targets:
        chance = 1.0 if (has_status(t, S_CHILL) or has_status(t, S_FROSTBITE)) else 0.75
        if random.random() < chance:
            ctx.apply_debuff_with_passives(user, t, make_slow(duration=3))
            ctx.log.append(f"{t.name}: Зимний приговор — усиленное Замедление.")

def _winter_verdict_3(user, targets, ctx):
    chosen = targets[:2]
    for t in chosen:
        ctx.apply_debuff_with_passives(user, t, make_slow(duration=3))
        push_back(t, 8.0)
        ctx.log.append(f"{t.name}: Зимний приговор — Замедление + Откат.")


# --- Королевский мороз ---

def _royal_frost_1(user, targets, ctx):
    for t in ctx.alive_enemies():
        _frost_hit(user, t, weapon_mult=0.65, stagger_fill=0.08, ctx=ctx)
        _try_apply_chill(user, t, base_chance=0.55, duration=2, power=2.5, ctx=ctx)
        apply_status(t, make_slow_light(duration=2))

def _royal_frost_2(user, targets, ctx):
    for t in ctx.alive_enemies():
        _frost_hit(user, t, weapon_mult=0.85, stagger_fill=0.10, ctx=ctx)
        # Уже под Ознобом — полное Замедление, иначе Замедление шага
        if has_status(t, S_CHILL) or has_status(t, S_FROSTBITE):
            _try_apply_chill(user, t, base_chance=0.70, duration=2, power=2.5, ctx=ctx)
            ctx.apply_debuff_with_passives(user, t, make_slow(duration=2))
        else:
            _try_apply_chill(user, t, base_chance=0.55, duration=2, power=2.5, ctx=ctx)
            apply_status(t, make_slow_light(duration=2))

def _royal_frost_3(user, targets, ctx):
    """Волна сдвигает всех врагов в CTB-очереди."""
    for t in ctx.alive_enemies():
        _frost_hit(user, t, weapon_mult=0.9, stagger_fill=0.10, ctx=ctx)
        _try_apply_chill(user, t, base_chance=0.60, duration=2, power=2.5, ctx=ctx)
        ctx.apply_debuff_with_passives(user, t, make_slow_light(duration=2))
        push_back(t, 4.0)
    ctx.log.append(f"{user.name}: Королевский мороз — все враги сдвинуты в очереди.")


# --- Эдикт ---

def _make_edict_effect(duration, mag_def_break=False):
    def on_apply(owner, effect):
        owner._edict_active = True
        owner._edict_dmg_bonus = 0.25
        if mag_def_break:
            owner._edict_mag_break_saved = owner.mag_def_stat
            owner.mag_def_stat = owner.mag_def_stat * 0.75

    def on_remove(owner, effect):
        owner._edict_active    = False
        owner._edict_dmg_bonus = 0.0
        if mag_def_break and hasattr(owner, "_edict_mag_break_saved"):
            owner.mag_def_stat = owner._edict_mag_break_saved
            del owner._edict_mag_break_saved

    return StatusEffect(S_EDICT, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _edict_1(user, targets, ctx):
    for t in targets:
        ctx.apply_debuff_with_passives(user, t, _make_edict_effect(duration=3))
        ctx.log.append(f"{t.name}: Эдикт — урон по цели +25% [[3 хода]].")

def _edict_2(user, targets, ctx):
    for t in targets:
        ctx.apply_debuff_with_passives(user, t, _make_edict_effect(duration=4, mag_def_break=True))
        ctx.log.append(f"{t.name}: Эдикт — урон +25%, маг.защита -25% [[4 хода]].")

def _edict_3(user, targets, ctx):
    for t in targets:
        ctx.apply_debuff_with_passives(user, t, _make_edict_effect(duration=4, mag_def_break=True))
        # III: цель не накапливает заряды способностей (флаг для системы зарядов)
        t._edict_no_charges = True
        ctx.log.append(f"{t.name}: Эдикт — урон +25%, маг.защита -25%, нет зарядов [[4 хода]].")


# ---------------------------------------------------------------------------
# ПАССИВЫ
# ---------------------------------------------------------------------------

# --- Хрупкость ---
# Логика реализована внутри _frost_hit через флаг _fragility_passive.

def _p_fragility_start(owner, ctx):
    owner._fragility_passive = True

def make_passive_fragility():
    return Skill(
        skill_id="fragility", name="Хрупкость",
        tier=0, chain_id="fragility", branch_name=BRANCH_CHILL,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_battle_start=_p_fragility_start,
        description=(
            "Цель под Ознобом или Обморожением получает +50% к stagger-вкладу "
            "от любой атаки Веспергрейв."
        ),
    )


# --- Глубокий холод ---
# Логика реализована в _try_apply_chill через флаг _deep_cold_passive.

def _p_deep_cold_start(owner, ctx):
    owner._deep_cold_passive = True

def make_passive_deep_cold():
    return Skill(
        skill_id="deep_cold", name="Глубокий холод",
        tier=0, chain_id="deep_cold", branch_name=BRANCH_CHILL,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_battle_start=_p_deep_cold_start,
        description=(
            "Повторное наложение Озноба на уже замёрзшую цель продлевает "
            "длительность эффекта вместо сброса."
        ),
    )


# --- Вечная мерзлота ---
# Логика реализована в _update_permafrost, вызывается из on_apply/on_remove барьеров.

def _p_permafrost_start(owner, ctx):
    owner._permafrost_passive = True
    owner._permafrost_count   = 0
    owner._permafrost_active  = False

def make_passive_permafrost():
    return Skill(
        skill_id="permafrost", name="Вечная мерзлота",
        tier=0, chain_id="permafrost", branch_name=BRANCH_BARRIER,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_battle_start=_p_permafrost_start,
        description=(
            "Пока активен Барьер или Отражение на любом союзнике, "
            f"Веспергрейв получает +{_PERMAFROST_MAG_DEF_BONUS} к магической защите."
        ),
    )


# --- Ледяная реакция ---

def _p_ice_reaction_ally_damaged(owner, ally, attacker, result, ctx):
    threshold = getattr(owner, "_reaction_threshold", _REACTION_THRESHOLD)
    if result.damage >= threshold:
        # Лёгкое ускорение — отрицательный push_back
        push_back(owner, -4.0)
        ctx.log.append(
            f"{owner.name}: Ледяная реакция — ускорение "
            f"[[союзник {ally.name} получил {result.damage} урона]]."
        )

def _p_ice_reaction_start(owner, ctx):
    owner._reaction_threshold = _REACTION_THRESHOLD

def make_passive_ice_reaction():
    return Skill(
        skill_id="ice_reaction", name="Ледяная реакция",
        tier=0, chain_id="ice_reaction", branch_name=BRANCH_BARRIER,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_battle_start=_p_ice_reaction_start,
        on_ally_damaged=_p_ice_reaction_ally_damaged,
        description=(
            f"Если союзник получает >= {_REACTION_THRESHOLD} урона за один удар, "
            "Веспергрейв получает лёгкое ускорение в CTB-очереди."
        ),
    )


# --- Регентская воля ---

def _p_regents_will_debuff(owner, target, effect, ctx):
    """При любом дебаффе на врага — все союзники получают лёгкое ускорение."""
    if effect.status_id not in NEGATIVE_STATUSES:
        return
    allies = ctx.alive_party()
    for ally in allies:
        if ally is owner:
            continue
        push_back(ally, -2.0)
    if allies:
        ctx.log.append(f"{owner.name}: Регентская воля — союзники ускорены.")

def make_passive_regents_will():
    return Skill(
        skill_id="regents_will", name="Регентская воля",
        tier=0, chain_id="regents_will", branch_name=BRANCH_RULE,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_debuff_applied_by=_p_regents_will_debuff,
        description=(
            "При наложении любого дебаффа на врага все союзники получают "
            "лёгкое ускорение в CTB-очереди."
        ),
    )


# --- Холодный расчёт ---

def _p_cold_calc_start(owner, ctx):
    owner._cold_calc_debuffs_this_turn = 0
    owner._cold_calc_discount_pending  = 0

def _p_cold_calc_debuff(owner, target, effect, ctx):
    if effect.status_id not in NEGATIVE_STATUSES:
        return
    owner._cold_calc_debuffs_this_turn = getattr(
        owner, "_cold_calc_debuffs_this_turn", 0) + 1
    if owner._cold_calc_debuffs_this_turn >= 2:
        owner._cold_calc_discount_pending = _COLD_CALC_DISCOUNT
        ctx.log.append(
            f"{owner.name}: Холодный расчёт — следующая способность "
            f"дешевле на {_COLD_CALC_DISCOUNT} Эфира."
        )

def make_passive_cold_calc():
    return Skill(
        skill_id="cold_calc", name="Холодный расчёт",
        tier=0, chain_id="cold_calc", branch_name=BRANCH_RULE,
        resource_cost=0, action_weight=ActionWeight.QUICK,
        target_type=TARGET_SELF,
        is_passive=True,
        on_battle_start=_p_cold_calc_start,
        on_debuff_applied_by=_p_cold_calc_debuff,
        description=(
            "Если за ход Веспергрейв наложила дебафф на двух и более врагов, "
            f"следующая её способность стоит на {_COLD_CALC_DISCOUNT} Эфира дешевле."
        ),
    )


# ---------------------------------------------------------------------------
# БАЗОВАЯ АТАКА ВЕСПЕРГРЕЙВ
# ---------------------------------------------------------------------------

def vespergrave_basic_attack(user, target, ctx):
    """
    Базовая атака — ледяной выпад жезлом.
    Тратит 10 Эфира. Шанс Озноба зависит от снаряжения (флаг _staff_chill_bonus).
    """
    if not user.spend_resource(10):
        return
    base_chance = 0.20 + getattr(user, "_staff_chill_bonus", 0.0)
    res = _frost_hit(user, target, weapon_mult=0.8, stagger_fill=0.10, ctx=ctx)
    if res.hit and not res.evaded:
        _try_apply_chill(user, target, base_chance=base_chance,
                         duration=2, power=2.5, ctx=ctx)


# ---------------------------------------------------------------------------
# СБОРКА SKILLSET
# ---------------------------------------------------------------------------

def build_vespergrave_skills() -> SkillSet:
    ss = SkillSet()

    # -----------------------------------------------------------------------
    # Озноб
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="ice_arrow_1", name="Ледяная стрела I",
        tier=1, chain_id="ice_arrow", branch_name=BRANCH_CHILL,
        resource_cost=15, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_ice_arrow_1,
        description="Магическая атака Морозом. Умеренный шанс Озноба (40%).",
    ))
    ss.register(Skill(
        skill_id="ice_arrow_2", name="Ледяная стрела II",
        tier=2, chain_id="ice_arrow", branch_name=BRANCH_CHILL,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_ice_arrow_2,
        description="Повышенный шанс Озноба (60%). Бонус урона по замёрзшей цели.",
    ))
    ss.register(Skill(
        skill_id="ice_arrow_3", name="Ледяная стрела III",
        tier=3, chain_id="ice_arrow", branch_name=BRANCH_CHILL,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_ice_arrow_3,
        description="Стрела раскалывается — поражает цель и соседнюю. Озноб на обе.",
    ))

    ss.register(Skill(
        skill_id="frostbite_1", name="Обморожение I",
        tier=1, chain_id="frostbite", branch_name=BRANCH_CHILL,
        resource_cost=25, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_frostbite_1,
        description="Высокий урон, гарантированный Озноб. Тяжёлое действие.",
    ))
    ss.register(Skill(
        skill_id="frostbite_2", name="Обморожение II",
        tier=2, chain_id="frostbite", branch_name=BRANCH_CHILL,
        resource_cost=35, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_frostbite_2,
        description="Урон повышен. Озноб с удлинённым замедлением CTB.",
    ))
    ss.register(Skill(
        skill_id="frostbite_3", name="Обморожение III",
        tier=3, chain_id="frostbite", branch_name=BRANCH_CHILL,
        resource_cost=45, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_frostbite_3,
        description="Озноб + Замедление шага.",
    ))

    ss.register(Skill(
        skill_id="hoarfrost_1", name="Иней I",
        tier=1, chain_id="hoarfrost", branch_name=BRANCH_CHILL,
        resource_cost=20, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_AREA_FOE, execute=_hoarfrost_1,
        description="Два случайных врага: Озноб + Замедление шага.",
    ))
    ss.register(Skill(
        skill_id="hoarfrost_2", name="Иней II",
        tier=2, chain_id="hoarfrost", branch_name=BRANCH_CHILL,
        resource_cost=28, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_AREA_FOE, execute=_hoarfrost_2,
        description="Три случайных врага: Озноб + полное Замедление.",
    ))
    ss.register(Skill(
        skill_id="hoarfrost_3", name="Иней III",
        tier=3, chain_id="hoarfrost", branch_name=BRANCH_CHILL,
        resource_cost=38, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_AREA_FOE, execute=_hoarfrost_3,
        description="Три врага: Озноб + Замедление + Промокший. Синергия с Хисс.",
    ))

    ss.register(make_passive_fragility())
    ss.register(make_passive_deep_cold())

    # -----------------------------------------------------------------------
    # Ледяной барьер
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="barrier_1", name="Барьер I",
        tier=1, chain_id="barrier", branch_name=BRANCH_BARRIER,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_barrier_1,
        description="Ледяная оболочка на одного союзника. Снижение входящего урона 30% [[1 ход]].",
    ))
    ss.register(Skill(
        skill_id="barrier_2", name="Барьер II",
        tier=2, chain_id="barrier", branch_name=BRANCH_BARRIER,
        resource_cost=28, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_barrier_2,
        description="Снижение урона 35% [[2 хода]]. Блокирует наложение Горения.",
    ))
    ss.register(Skill(
        skill_id="barrier_3", name="Барьер III",
        tier=3, chain_id="barrier", branch_name=BRANCH_BARRIER,
        resource_cost=38, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_ALL_ALLY, execute=_barrier_3,
        description="Снижение урона 40% на двух союзниках. При разрушении — Озноб атакующему.",
    ))

    ss.register(Skill(
        skill_id="ice_shell_1", name="Ледяной панцирь I",
        tier=1, chain_id="ice_shell", branch_name=BRANCH_BARRIER,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_ice_shell_1,
        description="Защита +10/+10 [[2 хода]]. Штраф к скорости при активации.",
    ))
    ss.register(Skill(
        skill_id="ice_shell_2", name="Ледяной панцирь II",
        tier=2, chain_id="ice_shell", branch_name=BRANCH_BARRIER,
        resource_cost=35, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_ice_shell_2,
        description="Защита +16/+16. Атакующий рискует получить Озноб через контакт.",
    ))
    ss.register(Skill(
        skill_id="ice_shell_3", name="Ледяной панцирь III",
        tier=3, chain_id="ice_shell", branch_name=BRANCH_BARRIER,
        resource_cost=45, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_ice_shell_3,
        description="Защита +16/+16 [[3 хода]]. Штраф к скорости снят.",
    ))

    ss.register(Skill(
        skill_id="reflect_1", name="Отражение I",
        tier=1, chain_id="reflect", branch_name=BRANCH_BARRIER,
        resource_cost=30, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_reflect_1,
        description="Следующая атака по союзнику отражается. Атакующий получает Озноб.",
    ))
    ss.register(Skill(
        skill_id="reflect_2", name="Отражение II",
        tier=2, chain_id="reflect", branch_name=BRANCH_BARRIER,
        resource_cost=40, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_reflect_2,
        description="Две атаки отражаются. Озноб при каждом отражении.",
    ))
    ss.register(Skill(
        skill_id="reflect_3", name="Отражение III",
        tier=3, chain_id="reflect", branch_name=BRANCH_BARRIER,
        resource_cost=50, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_reflect_3,
        description="Две атаки с возвратом урона. Атакующий дополнительно получает Откат.",
    ))

    ss.register(make_passive_permafrost())
    ss.register(make_passive_ice_reaction())

    # -----------------------------------------------------------------------
    # Владычество
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="winter_verdict_1", name="Зимний приговор I",
        tier=1, chain_id="winter_verdict", branch_name=BRANCH_RULE,
        resource_cost=30, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_winter_verdict_1,
        description="Замедление на одного врага.",
    ))
    ss.register(Skill(
        skill_id="winter_verdict_2", name="Зимний приговор II",
        tier=2, chain_id="winter_verdict", branch_name=BRANCH_RULE,
        resource_cost=40, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_winter_verdict_2,
        description="Усиленное Замедление. Гарантировано по цели под Ознобом.",
    ))
    ss.register(Skill(
        skill_id="winter_verdict_3", name="Зимний приговор III",
        tier=3, chain_id="winter_verdict", branch_name=BRANCH_RULE,
        resource_cost=50, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_ALL_FOE, execute=_winter_verdict_3,
        description="Замедление на двух врагов + Откат на каждого.",
    ))

    ss.register(Skill(
        skill_id="royal_frost_1", name="Королевский мороз I",
        tier=1, chain_id="royal_frost", branch_name=BRANCH_RULE,
        resource_cost=35, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_ALL_FOE, execute=_royal_frost_1,
        description="Волна холода по всем врагам. Озноб + Замедление шага.",
    ))
    ss.register(Skill(
        skill_id="royal_frost_2", name="Королевский мороз II",
        tier=2, chain_id="royal_frost", branch_name=BRANCH_RULE,
        resource_cost=45, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_ALL_FOE, execute=_royal_frost_2,
        description="Урон повышен. Замёрзшие цели получают полное Замедление.",
    ))
    ss.register(Skill(
        skill_id="royal_frost_3", name="Королевский мороз III",
        tier=3, chain_id="royal_frost", branch_name=BRANCH_RULE,
        resource_cost=60, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_ALL_FOE, execute=_royal_frost_3,
        description="Массовый сдвиг в CTB-очереди. Все враги получают Откат.",
    ))

    ss.register(Skill(
        skill_id="edict_1", name="Эдикт I",
        tier=1, chain_id="edict", branch_name=BRANCH_RULE,
        resource_cost=30, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_edict_1,
        description="Отмечает врага — урон по цели от партии +25% [[3 хода]].",
    ))
    ss.register(Skill(
        skill_id="edict_2", name="Эдикт II",
        tier=2, chain_id="edict", branch_name=BRANCH_RULE,
        resource_cost=40, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_edict_2,
        description="Урон +25%, маг.защита цели -25% [[4 хода]].",
    ))
    ss.register(Skill(
        skill_id="edict_3", name="Эдикт III",
        tier=3, chain_id="edict", branch_name=BRANCH_RULE,
        resource_cost=50, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_edict_3,
        description="Урон +25%, маг.защита -25%, цель не накапливает заряды [[4 хода]].",
    ))

    ss.register(make_passive_regents_will())
    ss.register(make_passive_cold_calc())

    return ss
