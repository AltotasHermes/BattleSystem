"""
Слой 6 — скилловая система.

Skill — контейнер с метаданными и callback-функцией эффекта.
Cooldown измеряется в ходах самого персонажа (как и статусы).
Кулдаун ступени = номер ступени (I=1, II=2, III=3).
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from combat.ctb import ActionWeight


# ---------------------------------------------------------------------------
# Типы целей
# ---------------------------------------------------------------------------

TARGET_SINGLE   = "single"    # одна цель
TARGET_SELF     = "self"      # только пользователь
TARGET_ALL_FOE  = "all_foe"   # все враги
TARGET_ALL_ALLY = "all_ally"  # все союзники
TARGET_AREA_FOE = "area_foe"  # враги в ближней зоне (определяется контекстом боя)


# ---------------------------------------------------------------------------
# Класс скилла
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """
    skill_id        — уникальный строковый идентификатор
    name            — отображаемое имя
    tier            — ступень цепочки (1/2/3); пассивы = 0
    chain_id        — идентификатор цепочки (все ступени одной цепочки имеют одинаковый)
    resource_cost   — стоимость в ресурсе персонажа
    action_weight   — вес для CTB (ActionWeight.LIGHT / MEDIUM / HEAVY)
    target_type     — тип цели
    execute         — callable(user, targets, ctx) — основная логика скилла
    is_passive      — пассивный скилл (не используется активно)
    description     — текст для UI
    """
    skill_id:       str
    name:           str
    tier:           int
    chain_id:       str
    resource_cost:  float
    action_weight:  float
    target_type:    str
    execute:        Optional[Callable] = None
    is_passive:     bool = False
    description:    str  = ""

    @property
    def cooldown_length(self):
        """Длина кулдауна равна номеру ступени. Пассивы и tier=0 — без кулдауна."""
        return self.tier if self.tier > 0 else 0


# ---------------------------------------------------------------------------
# Трекер кулдаунов
# ---------------------------------------------------------------------------

class CooldownTracker:
    """
    Хранит текущие кулдауны цепочек для одного персонажа.
    Кулдаун отсчитывается в ходах самого персонажа.
    """

    def __init__(self):
        self._cd: dict[str, int] = {}   # chain_id -> оставшиеся ходы

    def is_ready(self, skill: Skill) -> bool:
        if skill.is_passive:
            return True
        return self._cd.get(skill.chain_id, 0) == 0

    def put_on_cooldown(self, skill: Skill):
        if skill.cooldown_length > 0:
            self._cd[skill.chain_id] = skill.cooldown_length

    def tick(self):
        """Вызывается в начале хода персонажа — уменьшает все кулдауны на 1."""
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
    """
    Набор скиллов одного персонажа.
    Хранит все известные скиллы и трекер кулдаунов.
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self.cooldowns = CooldownTracker()

    def register(self, skill: Skill):
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def all_active(self):
        """Все неп пассивные скиллы."""
        return [s for s in self._skills.values() if not s.is_passive]

    def all_passive(self):
        return [s for s in self._skills.values() if s.is_passive]

    def available(self):
        """Скиллы готовые к использованию (не на кулдауне)."""
        return [s for s in self.all_active()
                if self.cooldowns.is_ready(s)]

    def use(self, skill_id: str, user, targets, ctx=None) -> bool:
        """
        Попытка использовать скилл.
        Проверяет ресурс и кулдаун, выполняет callback, ставит на кулдаун.
        Возвращает True при успехе.
        ctx — объект контекста боя (передаётся в execute, может быть None в тестах).
        """
        skill = self.get(skill_id)
        if skill is None:
            return False
        if not self.cooldowns.is_ready(skill):
            return False
        if not user.spend_resource(skill.resource_cost):
            return False
        if skill.execute:
            skill.execute(user, targets, ctx)
        self.cooldowns.put_on_cooldown(skill)
        return True

    def tick_cooldowns(self):
        """Вызывается в начале хода персонажа."""
        self.cooldowns.tick()
