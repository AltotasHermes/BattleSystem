"""
Скиллы Грэма Воса — ветвь «Режущее оружие» (стартовая).
Остальные ветви добавляются по ходу нарратива.
"""

from combat.skills import Skill, SkillSet, TARGET_SINGLE, TARGET_AREA_FOE
from combat.ctb import ActionWeight
from combat.damage import resolve_damage, AttackData, DMG_SLASH
from combat.stagger import add_stagger
from combat.status import (
    apply_status,
    make_bleed, make_bleed_heavy, make_stun,
    has_status, S_STAGGER_BREAK,
)

BRANCH_CUTTING = "Режущее оружие"


# ---------------------------------------------------------------------------
# Вспомогательная функция применения результата урона
# ---------------------------------------------------------------------------

def _apply_result(target, result):
    if result.hit and not result.evaded:
        if result.damage > 0:
            target.take_damage(result.damage)
        elif result.damage < 0:
            target.heal(-result.damage)
        add_stagger(target, result.stagger_fill * target.stagger_max)


# ---------------------------------------------------------------------------
# Ветвь: Режущее оружие
# ---------------------------------------------------------------------------

# --- Кровопускание ---

def _bloodletting_1(user, targets, ctx):
    import random
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit and random.random() < 0.40:
            apply_status(t, make_bleed(duration=3, power=8.0))

def _bloodletting_2(user, targets, ctx):
    import random
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit and random.random() < 0.65:
            apply_status(t, make_bleed_heavy(duration=3, power=14.0))

def _bloodletting_3(user, targets, ctx):
    import random
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=0.9, stagger_fill=0.10)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit and random.random() < 0.85:
            apply_status(t, make_bleed(duration=3, power=8.0))


# --- Рубящий удар ---

def _cleave_1(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.5, stagger_fill=0.30)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)

def _cleave_2(user, targets, ctx):
    for t in targets:
        has_bleed = has_status(t, "bleed") or has_status(t, "bleed_heavy")
        bonus_mult = 1.25 if has_bleed else 1.0
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.7 * bonus_mult, stagger_fill=0.35)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)

def _cleave_3(user, targets, ctx):
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=2.0, stagger_fill=0.40)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit and has_status(t, S_STAGGER_BREAK):
            from combat.ctb import push_back
            push_back(t, 15.0)


# --- Натиск ---

def _rush_1(user, targets, ctx):
    from combat.ctb import push_back
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit:
            push_back(t, 5.0)

def _rush_2(user, targets, ctx):
    from combat.ctb import push_back
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.15)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit:
            bonus = (ctx is not None and ctx.peek_next() is t)
            push_back(t, 12.0 if bonus else 7.0)

def _rush_3(user, targets, ctx):
    from combat.ctb import push_back
    for t in targets:
        atk = AttackData(DMG_SLASH, scaling_stat=user.mettle,
                         weapon_mult=1.0, stagger_fill=0.20)
        res = resolve_damage(user, t, atk)
        _apply_result(t, res)
        if res.hit:
            push_back(t, 10.0)
            apply_status(t, make_stun(duration=1))


# ---------------------------------------------------------------------------
# Сборка SkillSet Грэма
# ---------------------------------------------------------------------------

def build_graham_skills() -> SkillSet:
    ss = SkillSet()

    ss.register(Skill(
        skill_id="bloodletting_1", name="Кровопускание I",
        tier=1, chain_id="bloodletting_1", branch_name=BRANCH_CUTTING,
        resource_cost=20, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_bloodletting_1,
        description="Удар с умеренным шансом наложить Кровотечение.",
    ))
    ss.register(Skill(
        skill_id="bloodletting_2", name="Кровопускание II",
        tier=2, chain_id="bloodletting_2", branch_name=BRANCH_CUTTING,
        resource_cost=25, action_weight=ActionWeight.LIGHT,
        target_type=TARGET_SINGLE, execute=_bloodletting_2,
        description="Повышенный шанс. Накладывает Сильное кровотечение.",
    ))
    ss.register(Skill(
        skill_id="bloodletting_3", name="Кровопускание III",
        tier=3, chain_id="bloodletting_3", branch_name=BRANCH_CUTTING,
        resource_cost=35, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_AREA_FOE, execute=_bloodletting_3,
        description="Высокий шанс. Удар по всем врагам в ближней зоне.",
    ))

    ss.register(Skill(
        skill_id="cleave_1", name="Рубящий удар I",
        tier=1, chain_id="cleave_1", branch_name=BRANCH_CUTTING,
        resource_cost=40, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_1,
        description="Тяжёлый удар с высоким уроном.",
    ))
    ss.register(Skill(
        skill_id="cleave_2", name="Рубящий удар II",
        tier=2, chain_id="cleave_2", branch_name=BRANCH_CUTTING,
        resource_cost=50, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_2,
        description="Урон повышен. Бонус по цели с Кровотечением.",
    ))
    ss.register(Skill(
        skill_id="cleave_3", name="Рубящий удар III",
        tier=3, chain_id="cleave_3", branch_name=BRANCH_CUTTING,
        resource_cost=65, action_weight=ActionWeight.HEAVY,
        target_type=TARGET_SINGLE, execute=_cleave_3,
        description="Максимальный урон. Гарантированный Откат при Прорыве стойки.",
    ))

    ss.register(Skill(
        skill_id="rush_1", name="Натиск I",
        tier=1, chain_id="rush_1", branch_name=BRANCH_CUTTING,
        resource_cost=25, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_1,
        description="Удар с движением. Лёгкий Откат.",
    ))
    ss.register(Skill(
        skill_id="rush_2", name="Натиск II",
        tier=2, chain_id="rush_2", branch_name=BRANCH_CUTTING,
        resource_cost=35, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_2,
        description="Откат усилен. Бонус если цель стояла следующей в очереди.",
    ))
    ss.register(Skill(
        skill_id="rush_3", name="Натиск III",
        tier=3, chain_id="rush_3", branch_name=BRANCH_CUTTING,
        resource_cost=45, action_weight=ActionWeight.MEDIUM,
        target_type=TARGET_SINGLE, execute=_rush_3,
        description="Сбивает с ног. Накладывает Оглушение.",
    ))

    return ss
