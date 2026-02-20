"""
Слой 6 — скилловая система.

Skill — контейнер с метаданными и callback-функцией эффекта.
Кулдаун измеряется в ходах самого персонажа.
Кулдаун ступени = номер ступени (I=1, II=2, III=3).
Все ступени одной цепочки делят один кулдаун через общий chain_id.
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
    """
    skill_id        — уникальный строковый идентификатор
    name            — отображаемое имя
    tier            — ступень цепочки (1/2/3); пассивы = 0
    chain_id        — идентификатор цепочки; все ступени одной цепочки
                      должны иметь одинаковый chain_id
    branch_name     — название ветви для UI
    resource_cost   — стоимость в ресурсе персонажа
    action_weight   — вес для CTB
    target_type     — тип цели
    execute         — callable(user, targets, ctx)
    is_passive      — пассивный скилл
    description     — текст для UI
    unlocked        — разблокирован ли скилл (ветвь открыта)
    """
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

    @property
    def cooldown_length(self):
        """Длина кулдауна в ходах равна номеру ступени."""
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
            self._cd[skill.chain_id] = skill.cooldown_length

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
        # Множество разблокированных ветвей. Если пусто — все ветви доступны.
        self._unlocked_branches: set = set()

    # ------------------------------------------------------------------
    # Управление ветвями
    # ------------------------------------------------------------------

    def unlock_branch(self, branch_name: str):
        self._unlocked_branches.add(branch_name)

    def lock_branch(self, branch_name: str):
        self._unlocked_branches.discard(branch_name)

    def is_branch_unlocked(self, branch_name: str) -> bool:
        if not self._unlocked_branches:
            return True   # если ограничений нет — все доступны
        return branch_name in self._unlocked_branches

    # ------------------------------------------------------------------
    # Регистрация
    # ------------------------------------------------------------------

    def register(self, skill: Skill):
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    # ------------------------------------------------------------------
    # Списки скиллов
    # ------------------------------------------------------------------

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
        """
        Возвращает список (branch_id, branch_name) всех известных ветвей.
        Используется UI для отображения — включает заблокированные ветви.
        """
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
        """Все скиллы ветви включая недоступные по кулдауну."""
        return [s for s in self.all_active() if s.branch_name == branch_name]

    # ------------------------------------------------------------------
    # Использование
    # ------------------------------------------------------------------

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

        # Имя скилла пишется в лог первым — до эффектов
        # ВАЖНО: [[ ]] — экранирование для Ren'Py text-виджета
        if ctx is not None:
            cd = skill.cooldown_length
            cd_note = f" [[КД {cd}]]" if cd > 0 else ""
            ctx.log.append(f">> {user.name}: {skill.name}{cd_note}")

        if skill.execute:
            skill.execute(user, targets, ctx)

        self.cooldowns.put_on_cooldown(skill)
        return True

    def tick_cooldowns(self):
        self.cooldowns.tick()

    # ------------------------------------------------------------------
    # UI-данные для скиллов
    # ------------------------------------------------------------------

    def ui_skill_label(self, skill: Skill) -> str:
        """Строка для кнопки навыка в боевом меню."""
        cost  = str(int(skill.resource_cost))
        cd    = self.cooldowns.remaining(skill.chain_id)
        ready = self.cooldowns.is_ready(skill)
        if ready:
            return f"{skill.name}  [{cost}]"
        return f"{skill.name}  [КД {cd}]"

    def ui_skill_available(self, skill: Skill) -> bool:
        return self.cooldowns.is_ready(skill) and self.is_branch_unlocked(skill.branch_name)
