"""
Скиллы Грэма Воса.

Ветви:
  - Режущее оружие   (стартовая)
  - Кулачный бой     (открывается по нарративу)
  - Парирование      (открывается через личный квест)

chain_id совпадает для всех ступеней одной цепочки — вся цепочка
уходит на общий кулдаун при использовании любой из ступеней.
"""

import random

from combat.skills import Skill, SkillSet, TARGET_SINGLE, TARGET_AREA_FOE, TARGET_SELF
from combat.ctb import ActionWeight, push_back
from combat.damage import resolve_damage, AttackData, DMG_SLASH, DMG_BLUNT
from combat.stagger import add_stagger
from combat.status import (
    apply_status,
    make_bleed, make_bleed_heavy, make_stun, make_weakness,
    has_status, get_status,
    S_STAGGER_BREAK, S_STUN, S_WEAKNESS,
    StatusEffect,
)

BRANCH_CUTTING  = "Режущее оружие"
BRANCH_BRAWL    = "Кулачный бой"
BRANCH_PARRY    = "Парирование"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _apply_result(actor, target, result, ctx, label_override=None):
    """Применяет результат удара и пишет строку в лог."""
    if result.hit and not result.evaded:
        if result.damage > 0:
            target.take_damage(result.damage)
        elif result.damage < 0:
            target.heal(-result.damage)
        add_stagger(target, result.stagger_fill * target.stagger_max)
        if ctx is not None:
            hit_label = label_override or ("КРИТ" if result.crit else "удар")
            ctx.log.append(f"{actor.name} -> {target.name}: {hit_label} {result.damage}")
    elif result.evaded:
        if ctx is not None:
            ctx.log.append(f"{actor.name} -> {target.name}: уклонение")


# ===========================================================================
# ВЕТВЬ: РЕЖУЩЕЕ ОРУЖИЕ
# ===========================================================================

# --- Кровопускание ---

def _bloodletting_1(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.40:
            apply_status(t, make_bleed(duration=3, power=8.0))
            if ctx:
                ctx.log.append(f"{t.name}: Кровотечение.")

def _bloodletting_2(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.65:
            apply_status(t, make_bleed_heavy(duration=3, power=14.0))
            if ctx:
                ctx.log.append(f"{t.name}: Сильное кровотечение.")

def _bloodletting_3(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.85:
            apply_status(t, make_bleed(duration=3, power=8.0))
            if ctx:
                ctx.log.append(f"{t.name}: Кровотечение.")


# --- Рубящий удар ---

def _cleave_1(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.5, stagger_fill=0.30)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx, label_override="Рубящий удар" if not res.crit else "КРИТ Рубящий удар")

def _cleave_2(user, targets, ctx):
    for t in targets:
        has_bleed = has_status(t, "bleed") or has_status(t, "bleed_heavy")
        bonus_mult = 1.25 if has_bleed else 1.0
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.7 * bonus_mult, stagger_fill=0.35)
        res = resolve_damage(user, t, atk)
        suffix = " [кровь]" if has_bleed else ""
        _apply_result(user, t, res, ctx, label_override=("КРИТ" if res.crit else "удар") + suffix)

def _cleave_3(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=2.0, stagger_fill=0.40)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx, label_override="Рубящий удар" if not res.crit else "КРИТ Рубящий удар")
        if res.hit and not res.evaded and has_status(t, S_STAGGER_BREAK):
            push_back(t, 15.0)
            if ctx:
                ctx.log.append(f"{t.name}: Откат — Прорыв стойки.")


# --- Натиск ---

def _rush_1(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded:
            push_back(t, 5.0)
            if ctx:
                ctx.log.append(f"{t.name}: Откат.")

def _rush_2(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded:
            bonus = (ctx is not None and ctx.peek_next() is t)
            amt = 12.0 if bonus else 7.0
            push_back(t, amt)
            if ctx:
                note = " [следующий в очереди]" if bonus else ""
                ctx.log.append(f"{t.name}: Откат {amt:.0f}{note}.")

def _rush_3(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.20)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded:
            push_back(t, 10.0)
            apply_status(t, make_stun(duration=1))
            if ctx:
                ctx.log.append(f"{t.name}: Откат + Оглушение.")


# ===========================================================================
# ВЕТВЬ: КУЛАЧНЫЙ БОЙ
# ===========================================================================

# --- Прямой ---

def _jab_1(user, targets, ctx):
    for t in targets:
        for _ in range(2):
            atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                             weapon_mult=0.55, stagger_fill=0.12)
            res = resolve_damage(user, t, atk)
            _apply_result(user, t, res, ctx)

def _jab_2(user, targets, ctx):
    for t in targets:
        for i in range(3):
            atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                             weapon_mult=0.55, stagger_fill=0.12)
            res = resolve_damage(user, t, atk)
            _apply_result(user, t, res, ctx)
            if res.hit and not res.evaded and i == 2 and random.random() < 0.45:
                apply_status(t, make_stun(duration=1))
                if ctx:
                    ctx.log.append(f"{t.name}: Оглушение.")

def _jab_3(user, targets, ctx):
    for t in targets:
        target_stunned = has_status(t, S_STUN)
        for i in range(4):
            atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                             weapon_mult=0.55, stagger_fill=0.12)
            res = resolve_damage(user, t, atk)
            _apply_result(user, t, res, ctx)
            if res.hit and not res.evaded and i == 3 and target_stunned:
                push_back(t, 10.0)
                if ctx:
                    ctx.log.append(f"{t.name}: Откат — добивание по оглушённому.")


# --- Захват ---

S_GRAB_CUSTOM = "grab"

def _make_grab_effect(duration):
    def on_apply(owner, effect):
        owner._stunned   = True
        owner._paralyzed = True
        push_back(owner, 8.0)
    def on_remove(owner, effect):
        owner._stunned   = False
        owner._paralyzed = False
    return StatusEffect(S_GRAB_CUSTOM, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _grab_1(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_grab_effect(duration=1))
        if ctx:
            ctx.log.append(f"{user.name} захватывает {t.name}.")

def _grab_2(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_grab_effect(duration=2))
        from combat.status import make_vulnerable
        apply_status(t, make_vulnerable(duration=2, physical=True))
        if ctx:
            ctx.log.append(f"{user.name} захватывает {t.name} — Уязвимость.")

def _grab_3(user, targets, ctx):
    for t in targets:
        apply_status(t, _make_grab_effect(duration=1))
        atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                         weapon_mult=1.2, stagger_fill=0.25)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx, label_override="бросок")
        push_back(t, 12.0)
        if ctx:
            ctx.log.append(f"{t.name}: Откат от броска.")


# --- Удар в корпус ---

S_BODY_EXHAUSTION = "body_exhaustion"

def _make_body_exhaustion(duration):
    def on_apply(owner, effect):
        owner._exhaust_saved  = getattr(owner, "_weakness_mult", 1.0)
        owner._weakness_mult  = max(0.6, owner._exhaust_saved * 0.8)
    def on_remove(owner, effect):
        if hasattr(owner, "_exhaust_saved"):
            owner._weakness_mult = owner._exhaust_saved
            del owner._exhaust_saved
    return StatusEffect(S_BODY_EXHAUSTION, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _body_blow_1(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                         weapon_mult=0.85, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.45:
            apply_status(t, _make_body_exhaustion(duration=2))
            if ctx:
                ctx.log.append(f"{t.name}: Истощение тела.")

def _body_blow_2(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                         weapon_mult=0.85, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.65:
            apply_status(t, _make_body_exhaustion(duration=2))
            from combat.status import make_vulnerable
            apply_status(t, make_vulnerable(duration=2, physical=True))
            if ctx:
                ctx.log.append(f"{t.name}: Истощение + Уязвимость.")

def _body_blow_3(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_BLUNT, scaling_stat=user.mettle,
                         weapon_mult=0.85, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(user, t, res, ctx)
        if res.hit and not res.evaded and random.random() < 0.80:
            had_exhaustion = has_status(t, S_BODY_EXHAUSTION)
            apply_status(t, _make_body_exhaustion(duration=2))
            if had_exhaustion:
                apply_status(t, make_weakness(duration=2))
                if ctx:
                    ctx.log.append(f"{t.name}: Истощение + Слабость.")
            elif ctx:
                ctx.log.append(f"{t.name}: Истощение тела.")


# ===========================================================================
# ВЕТВЬ: ПАРИРОВАНИЕ
# ===========================================================================

S_PARRY_READY   = "parry_ready"
S_COUNTER_READY = "counter_ready"
S_IRON_STANCE   = "iron_stance"

_PARRY_ENERGY_GAIN  = 20
_IRON_STANCE_DR     = 0.20
_IRON_STANCE_ENERGY = 8


def _make_parry_ready(duration, chance, energy_gain):
    def on_apply(owner, effect):
        owner._parry_chance = chance
        owner._parry_energy = energy_gain
        owner._parry_active = True
    def on_remove(owner, effect):
        owner._parry_chance = 0.0
        owner._parry_energy = 0
        owner._parry_active = False
    return StatusEffect(S_PARRY_READY, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _make_counter_ready(duration):
    def on_apply(owner, effect):
        owner._counter_active = True
    def on_remove(owner, effect):
        owner._counter_active = False
    return StatusEffect(S_COUNTER_READY, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)

def _make_iron_stance(duration, cc_immune=False):
    def on_apply(owner, effect):
        owner._iron_stance_active = True
        owner._iron_dr            = _IRON_STANCE_DR
        if cc_immune:
            owner._iron_cc_immune = True
    def on_remove(owner, effect):
        owner._iron_stance_active = False
        owner._iron_dr            = 0.0
        owner._iron_cc_immune     = False
    return StatusEffect(S_IRON_STANCE, duration=duration,
                        on_apply=on_apply, on_remove=on_remove)


def _parry_1(user, targets, ctx):
    apply_status(user, _make_parry_ready(duration=2, chance=0.40,
                                         energy_gain=_PARRY_ENERGY_GAIN))
    if ctx:
        ctx.log.append(f"{user.name}: стойка парирования (40%).")

def _parry_2(user, targets, ctx):
    apply_status(user, _make_parry_ready(duration=2, chance=0.60,
                                         energy_gain=_PARRY_ENERGY_GAIN + 10))
    if ctx:
        ctx.log.append(f"{user.name}: усиленная стойка парирования (60%).")

def _parry_3(user, targets, ctx):
    effect = _make_parry_ready(duration=2, chance=0.60,
                                energy_gain=_PARRY_ENERGY_GAIN + 10)
    orig_apply  = effect.on_apply
    orig_remove = effect.on_remove
    def on_apply_ext(owner, eff):
        orig_apply(owner, eff)
        owner._parry_auto_counter = True
    def on_remove_ext(owner, eff):
        orig_remove(owner, eff)
        owner._parry_auto_counter = False
    effect.on_apply  = on_apply_ext
    effect.on_remove = on_remove_ext
    apply_status(user, effect)
    if ctx:
        ctx.log.append(f"{user.name}: парирование с автоконтратакой (60%).")


def _riposte_1(user, targets, ctx):
    apply_status(user, _make_counter_ready(duration=2))
    user._counter_mult = 0.7
    user._counter_stun = False
    if ctx:
        ctx.log.append(f"{user.name}: готовность к встречному удару.")

def _riposte_2(user, targets, ctx):
    apply_status(user, _make_counter_ready(duration=2))
    user._counter_mult        = 1.0
    user._counter_stun        = True
    user._counter_stun_chance = 0.40
    if ctx:
        ctx.log.append(f"{user.name}: встречный удар (усил., шанс Оглушения 40%).")

def _riposte_3(user, targets, ctx):
    apply_status(user, _make_counter_ready(duration=3))
    user._counter_mult           = 1.0
    user._counter_stun           = True
    user._counter_stun_chance    = 0.40
    user._counter_heavy_pushback = True
    if ctx:
        ctx.log.append(f"{user.name}: встречный удар (макс., Откат после тяжёлой атаки).")


def _iron_stance_1(user, targets, ctx):
    apply_status(user, _make_iron_stance(duration=2))
    if ctx:
        ctx.log.append(f"{user.name}: Железная стойка — снижение урона 20%.")

def _iron_stance_2(user, targets, ctx):
    effect = _make_iron_stance(duration=2)
    orig_apply = effect.on_apply
    def on_apply_2(owner, eff):
        orig_apply(owner, eff)
        owner._iron_dr           = _IRON_STANCE_DR + 0.10
        owner._iron_energy_bonus = 4
    effect.on_apply = on_apply_2
    apply_status(user, effect)
    if ctx:
        ctx.log.append(f"{user.name}: Железная стойка (усил.) — снижение урона 30%.")

def _iron_stance_3(user, targets, ctx):
    apply_status(user, _make_iron_stance(duration=3, cc_immune=True))
    if ctx:
        ctx.log.append(f"{user.name}: несокрушимая Железная стойка — иммунитет к Откату.")


# ===========================================================================
# СБОРКА SKILLSET
# ===========================================================================

def build_graham_skills() -> SkillSet:
    ss = SkillSet()

    # -----------------------------------------------------------------------
    # Режущее оружие
    # Одна цепочка = один chain_id. Все ступени делят кулдаун.
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="bloodletting_1", name="Кровопускание I",
        tier=1, chain_id="bloodletting", branch_name=BRANCH_CUTTING,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_bloodletting_1,
        description="Удар с умеренным шансом наложить Кровотечение (40%).",
    ))
    ss.register(Skill(
        skill_id="bloodletting_2", name="Кровопускание II",
        tier=2, chain_id="bloodletting", branch_name=BRANCH_CUTTING,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_bloodletting_2,
        description="Повышенный шанс (65%). Накладывает Сильное кровотечение.",
    ))
    ss.register(Skill(
        skill_id="bloodletting_3", name="Кровопускание III",
        tier=3, chain_id="bloodletting", branch_name=BRANCH_CUTTING,
        resource_cost=35, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_AREA_FOE, execute=_bloodletting_3,
        description="Высокий шанс (85%). Удар по всем врагам в зоне.",
    ))

    ss.register(Skill(
        skill_id="cleave_1", name="Рубящий удар I",
        tier=1, chain_id="cleave", branch_name=BRANCH_CUTTING,
        resource_cost=40, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_1,
        description="Тяжёлый удар с высоким уроном.",
    ))
    ss.register(Skill(
        skill_id="cleave_2", name="Рубящий удар II",
        tier=2, chain_id="cleave", branch_name=BRANCH_CUTTING,
        resource_cost=50, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_2,
        description="Урон повышен. Бонус по цели с Кровотечением (+25%).",
    ))
    ss.register(Skill(
        skill_id="cleave_3", name="Рубящий удар III",
        tier=3, chain_id="cleave", branch_name=BRANCH_CUTTING,
        resource_cost=65, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_3,
        description="Максимальный урон. Откат при Прорыве стойки.",
    ))

    ss.register(Skill(
        skill_id="rush_1", name="Натиск I",
        tier=1, chain_id="rush", branch_name=BRANCH_CUTTING,
        resource_cost=25, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_1,
        description="Удар с движением. Лёгкий Откат.",
    ))
    ss.register(Skill(
        skill_id="rush_2", name="Натиск II",
        tier=2, chain_id="rush", branch_name=BRANCH_CUTTING,
        resource_cost=35, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_2,
        description="Откат усилен. Бонус если цель следующая в очереди.",
    ))
    ss.register(Skill(
        skill_id="rush_3", name="Натиск III",
        tier=3, chain_id="rush", branch_name=BRANCH_CUTTING,
        resource_cost=45, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_3,
        description="Откат + Оглушение.",
    ))

    # -----------------------------------------------------------------------
    # Кулачный бой
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="jab_1", name="Прямой I",
        tier=1, chain_id="jab", branch_name=BRANCH_BRAWL,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_jab_1,
        description="Два удара. Каждый заполняет шкалу стойки.",
    ))
    ss.register(Skill(
        skill_id="jab_2", name="Прямой II",
        tier=2, chain_id="jab", branch_name=BRANCH_BRAWL,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_jab_2,
        description="Три удара. Последний с шансом Оглушения (45%).",
    ))
    ss.register(Skill(
        skill_id="jab_3", name="Прямой III",
        tier=3, chain_id="jab", branch_name=BRANCH_BRAWL,
        resource_cost=35, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_jab_3,
        description="Четыре удара. По оглушённой цели последний гарантирует Откат.",
    ))

    ss.register(Skill(
        skill_id="grab_1", name="Захват I",
        tier=1, chain_id="grab", branch_name=BRANCH_BRAWL,
        resource_cost=30, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_grab_1,
        description="Удерживает цель на 1 ход.",
    ))
    ss.register(Skill(
        skill_id="grab_2", name="Захват II",
        tier=2, chain_id="grab", branch_name=BRANCH_BRAWL,
        resource_cost=40, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_grab_2,
        description="Удержание на 2 хода + Уязвимость.",
    ))
    ss.register(Skill(
        skill_id="grab_3", name="Захват III",
        tier=3, chain_id="grab", branch_name=BRANCH_BRAWL,
        resource_cost=50, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_grab_3,
        description="Захват с броском. Урон + Откат.",
    ))

    ss.register(Skill(
        skill_id="body_blow_1", name="Удар в корпус I",
        tier=1, chain_id="body_blow", branch_name=BRANCH_BRAWL,
        resource_cost=25, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_body_blow_1,
        description="Прицельный удар. Шанс Истощения тела (45%).",
    ))
    ss.register(Skill(
        skill_id="body_blow_2", name="Удар в корпус II",
        tier=2, chain_id="body_blow", branch_name=BRANCH_BRAWL,
        resource_cost=30, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_body_blow_2,
        description="Повышенный шанс (65%) + Уязвимость.",
    ))
    ss.register(Skill(
        skill_id="body_blow_3", name="Удар в корпус III",
        tier=3, chain_id="body_blow", branch_name=BRANCH_BRAWL,
        resource_cost=40, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_body_blow_3,
        description="Высокий шанс (80%). По Истощённой цели накладывает Слабость.",
    ))

    # -----------------------------------------------------------------------
    # Парирование
    # -----------------------------------------------------------------------

    ss.register(Skill(
        skill_id="parry_1", name="Парирование I",
        tier=1, chain_id="parry", branch_name=BRANCH_PARRY,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_parry_1,
        description="Бафф 2 хода. Следующий удар с 40% шансом парируется — урон снижен, Энергия восстановлена.",
    ))
    ss.register(Skill(
        skill_id="parry_2", name="Парирование II",
        tier=2, chain_id="parry", branch_name=BRANCH_PARRY,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_parry_2,
        description="Шанс парирования 60%. Больше Энергии при успехе.",
    ))
    ss.register(Skill(
        skill_id="parry_3", name="Парирование III",
        tier=3, chain_id="parry", branch_name=BRANCH_PARRY,
        resource_cost=30, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_parry_3,
        description="Успешное парирование автоматически запускает контратаку.",
    ))

    ss.register(Skill(
        skill_id="riposte_1", name="Встречный удар I",
        tier=1, chain_id="riposte", branch_name=BRANCH_PARRY,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_riposte_1,
        description="Бафф 2 хода. Ответный удар вне очереди при атаке врага.",
    ))
    ss.register(Skill(
        skill_id="riposte_2", name="Встречный удар II",
        tier=2, chain_id="riposte", branch_name=BRANCH_PARRY,
        resource_cost=30, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_riposte_2,
        description="Урон ответного удара повышен. Шанс Оглушения 40%.",
    ))
    ss.register(Skill(
        skill_id="riposte_3", name="Встречный удар III",
        tier=3, chain_id="riposte", branch_name=BRANCH_PARRY,
        resource_cost=40, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_riposte_3,
        description="Бафф 3 хода. После тяжёлой атаки врага ответный удар гарантирует Откат.",
    ))

    ss.register(Skill(
        skill_id="iron_stance_1", name="Железная стойка I",
        tier=1, chain_id="iron_stance", branch_name=BRANCH_PARRY,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_iron_stance_1,
        description="Бафф 2 хода. Входящий урон снижен на 20%. Каждый удар генерирует Энергию.",
    ))
    ss.register(Skill(
        skill_id="iron_stance_2", name="Железная стойка II",
        tier=2, chain_id="iron_stance", branch_name=BRANCH_PARRY,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_iron_stance_2,
        description="Снижение урона 30%. Больше Энергии за удар.",
    ))
    ss.register(Skill(
        skill_id="iron_stance_3", name="Железная стойка III",
        tier=3, chain_id="iron_stance", branch_name=BRANCH_PARRY,
        resource_cost=35, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SELF, execute=_iron_stance_3,
        description="Бафф 3 хода. Иммунитет к Откату и лёгким Прорывам стойки.",
    ))

    return ss
