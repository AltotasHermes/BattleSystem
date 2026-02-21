"""
Слой 6 — скилловая система.

Skill — контейнер с метаданными и callback-функцией эффекта.
Кулдаун измеряется в ходах самого персонажа.
Кулдаун ступени = номер ступени (I=1, II=2, III=3).
Все ступени одной цепочки делят один кулдаун через общий chain_id.

ПАССИВНЫЕ СКИЛЛЫ:
    Пассив регистрируется с is_passive=True и набором хуков вместо execute.
    Хуки вызываются из BattleContext в определённые моменты боя.
    Все хуки опциональны — пассив реализует только те что ему нужны.

    Доступные хуки:
        on_battle_start(owner, ctx)
            Вызывается один раз при инициализации боя для каждого
            участника с разблокированным пассивом.

        on_hit_received(owner, attacker, result, ctx)
            Вызывается когда owner получает удар (hit=True, evaded=False).
            result — DamageResult после применения урона.

        on_status_applied(owner, effect, ctx)
            Вызывается после успешного наложения статуса на owner.
            effect — StatusEffect который был наложен.

        on_ally_damaged(owner, ally, attacker, result, ctx)
            Вызывается когда союзник (не сам owner) получает урон.
            Используется для реакций поддержки типа Ледяной реакции.

        on_debuff_applied_by(owner, target, effect, ctx)
            Вызывается когда owner сам успешно накладывает дебафф на цель.
            Используется для пассивов типа Регентской воли и Холодного расчёта.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from combat.ctb import ActionWeight


# ---------------------------------------------------------------------------
# Типы целей
# ---------------------------------------------------------------------------

TARGET_SINGLE   = "single"
TARGET_SELF     = "self"
TARGET_ALL_FOE  = "all_foe"
TARGET_ALL_ALLY = "all_ally"
TARGET_AREA_FOE = "area_foe"


# ---------------------------------------------------------------------------
# Класс скилла
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    skill_id:       str
    name:           str
    tier:           int
    chain_id:       str
    branch_name:    str
    resource_cost:  float
    action_weight:  float
    target_type:    str
    execute:        Optional[Callable] = None
    is_passive:     bool  = False
    description:    str   = ""
    unlocked:       bool  = True

    # Хуки пассивных скиллов — заполняются только для is_passive=True
    on_battle_start:      Optional[Callable] = None  # (owner, ctx)
    on_hit_received:      Optional[Callable] = None  # (owner, attacker, result, ctx)
    on_status_applied:    Optional[Callable] = None  # (owner, effect, ctx)
    on_ally_damaged:      Optional[Callable] = None  # (owner, ally, attacker, result, ctx)
    on_debuff_applied_by: Optional[Callable] = None  # (owner, target, effect, ctx)

    @property
    def cooldown_length(self):
        return self.tier if self.tier > 0 else 0


# ---------------------------------------------------------------------------
# Трекер кулдаунов
# ---------------------------------------------------------------------------

class CooldownTracker:

    def __init__(self):
        self._cd: dict[str, int] = {}

    def is_ready(self, skill: Skill) -> bool:
        if skill.is_passive:
            return True
        return self._cd.get(skill.chain_id, 0) == 0

    def put_on_cooldown(self, skill: Skill):
        if skill.cooldown_length > 0:
            self._cd[skill.chain_id] = skill.cooldown_length + 1

    def tick(self):
        for chain_id in list(self._cd):
            self._cd[chain_id] -= 1
            if self._cd[chain_id] <= 0:
                del self._cd[chain_id]

    def remaining(self, chain_id: str) -> int:
        return self._cd.get(chain_id, 0)


# ---------------------------------------------------------------------------
# Реестр скиллов персонажа
# ---------------------------------------------------------------------------

class SkillSet:

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self.cooldowns = CooldownTracker()
        self._unlocked_branches: set = set()

    def unlock_branch(self, branch_name: str):
        self._unlocked_branches.add(branch_name)

    def lock_branch(self, branch_name: str):
        self._unlocked_branches.discard(branch_name)

    def is_branch_unlocked(self, branch_name: str) -> bool:
        if not self._unlocked_branches:
            return True
        return branch_name in self._unlocked_branches

    def register(self, skill: Skill):
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def all_active(self):
        return [s for s in self._skills.values() if not s.is_passive]

    def all_passive(self):
        return [s for s in self._skills.values() if s.is_passive]

    def available(self, owner=None):
        from combat.status import skills_blocked
        if owner is not None and skills_blocked(owner):
            return []
        return [
            s for s in self.all_active()
            if self.cooldowns.is_ready(s)
            and self.is_branch_unlocked(s.branch_name)
        ]

    def branches(self):
        seen = {}
        for s in self._skills.values():
            if not s.is_passive and s.branch_name not in seen:
                seen[s.branch_name] = s.branch_name
        return list(seen.items())

    def available_in_branch(self, branch_name, owner=None):
        from combat.status import skills_blocked
        if owner is not None and skills_blocked(owner):
            return []
        if not self.is_branch_unlocked(branch_name):
            return []
        return [
            s for s in self.all_active()
            if s.branch_name == branch_name
            and self.cooldowns.is_ready(s)
        ]

    def all_in_branch(self, branch_name):
        return [s for s in self.all_active() if s.branch_name == branch_name]

    def use(self, skill_id: str, user, targets, ctx=None) -> bool:
        from combat.status import skills_blocked
        skill = self.get(skill_id)
        if skill is None:
            return False
        if not self.is_branch_unlocked(skill.branch_name):
            return False
        if skills_blocked(user):
            return False
        if not self.cooldowns.is_ready(skill):
            return False
        if not user.spend_resource(skill.resource_cost):
            return False

        if ctx is not None:
            cd = skill.cooldown_length
            cd_note = " [[КД " + str(cd) + "]]" if cd > 0 else ""
            ctx.log.append(">> " + user.name + ": " + skill.name + cd_note)

        if skill.execute:
            skill.execute(user, targets, ctx)

        self.cooldowns.put_on_cooldown(skill)
        return True

    def tick_cooldowns(self):
        self.cooldowns.tick()

    # ------------------------------------------------------------------
    # Диспетчеры хуков пассивных скиллов
    # Вызываются из BattleContext в нужные моменты боя.
    # Каждый метод итерирует только разблокированные пассивы с нужным хуком.
    # ------------------------------------------------------------------

    def _active_passives(self):
        return [
            s for s in self.all_passive()
            if self.is_branch_unlocked(s.branch_name)
        ]

    def fire_battle_start(self, owner, ctx):
        for s in self._active_passives():
            if s.on_battle_start:
                s.on_battle_start(owner, ctx)

    def fire_hit_received(self, owner, attacker, result, ctx):
        for s in self._active_passives():
            if s.on_hit_received:
                s.on_hit_received(owner, attacker, result, ctx)

    def fire_status_applied(self, owner, effect, ctx):
        for s in self._active_passives():
            if s.on_status_applied:
                s.on_status_applied(owner, effect, ctx)

    def fire_ally_damaged(self, owner, ally, attacker, result, ctx):
        for s in self._active_passives():
            if s.on_ally_damaged:
                s.on_ally_damaged(owner, ally, attacker, result, ctx)

    def fire_debuff_applied_by(self, owner, target, effect, ctx):
        for s in self._active_passives():
            if s.on_debuff_applied_by:
                s.on_debuff_applied_by(owner, target, effect, ctx)

    def ui_skill_label(self, skill: Skill) -> str:
        cost  = str(int(skill.resource_cost))
        cd    = max(0, self.cooldowns.remaining(skill.chain_id) - 1)
        ready = self.cooldowns.is_ready(skill)
        if ready:
            return skill.name + "  [[" + cost + "]]"
        return skill.name + "  [[КД " + str(cd) + "]]"

    def ui_skill_available(self, skill: Skill) -> bool:
        return self.cooldowns.is_ready(skill) and self.is_branch_unlocked(skill.branch_name)
