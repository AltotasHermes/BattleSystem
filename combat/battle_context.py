"""
BattleContext — состояние одного боя.
Управляет циклом ходов, передаёт контекст в скиллы,
возвращает результат (победа / поражение / побег).
"""

from combat.ctb import (
    init_timers, advance_to_next, apply_delay,
    queue_snapshot, ActionWeight,
)
from combat.stagger import decay_stagger
from combat.status import tick_statuses


RESULT_WIN    = "win"
RESULT_LOSE   = "lose"
RESULT_ESCAPE = "escape"


class BattleContext:

    def __init__(self, party, enemies):
        """
        party   — список Combatant союзников (до 4)
        enemies — список Combatant врагов
        """
        self.party   = list(party)
        self.enemies = list(enemies)
        self.all     = self.party + self.enemies

        self.result  = None       # заполняется при завершении боя
        self.log     = []         # строки лог-сообщений для UI
        self.current_actor = None # кто сейчас ходит
        self._pending_delay = None  # вес действия, применяется после хода

        init_timers(self.all)

    # ------------------------------------------------------------------
    # Запросы состояния
    # ------------------------------------------------------------------

    def alive_party(self):
        return [c for c in self.party if c.is_alive()]

    def alive_enemies(self):
        return [c for c in self.enemies if c.is_alive()]

    def is_over(self):
        return not self.alive_party() or not self.alive_enemies()

    def peek_next(self):
        """Кто ходит следующим после текущего актора. Используется скиллами."""
        snap = queue_snapshot(self.all, slots=2)
        if len(snap) >= 2:
            return snap[1]
        return None

    def get_queue(self, slots=8):
        return queue_snapshot(self.all, slots=slots)

    # ------------------------------------------------------------------
    # Продвижение цикла
    # ------------------------------------------------------------------

    def advance(self):
        """
        Выбирает следующего актора и выполняет начало его хода:
        убывание stagger, тик статусов.
        Возвращает актора или None если бой завершён.
        """
        if self.is_over():
            self._resolve_result()
            return None

        actor = advance_to_next(self.all)
        if actor is None:
            return None

        self.current_actor = actor

        # Начало хода: stagger убывает, затем тикают статусы
        decay_stagger(actor)
        tick_statuses(actor)

        return actor

    def commit_action(self, weight):
        """
        Фиксирует вес совершённого действия и сдвигает актора в очереди.
        Кулдауны тикают здесь — после действия, один раз за ход актора.
        Вызывается после того как действие полностью разрешено.
        """
        if self.current_actor:
            if hasattr(self.current_actor, "skillset"):
                self.current_actor.skillset.tick_cooldowns()
            apply_delay(self.current_actor, weight)
            self._resolve_result()

    # ------------------------------------------------------------------
    # Базовая атака (без скилла)
    # ------------------------------------------------------------------

    def execute_basic_attack(self, actor, target):
        from combat.damage import resolve_damage, AttackData, DMG_SLASH
        from combat.stagger import add_stagger
        from combat.elemental_reactions import check_elemental_reaction

        atk = AttackData(
            damage_type=DMG_SLASH,
            scaling_stat=actor.mettle,
            weapon_mult=1.0,
            stagger_fill=0.15,
        )
        res = resolve_damage(actor, target, atk)
        if res.hit and not res.evaded:
            # Стихийные реакции до применения урона к HP
            check_elemental_reaction(actor, target, DMG_SLASH, self.log)

            target.take_damage(res.damage)
            add_stagger(target, res.stagger_fill * target.stagger_max)

            from combat.combatant import RESOURCE_ENERGY
            if actor.resource_type == RESOURCE_ENERGY:
                actor.restore_resource(15)
            label = "КРИТ" if res.crit else "удар"
            self.log.append(f"{actor.name} -> {target.name}: {label} {res.damage} урона")
        else:
            self.log.append(f"{actor.name} -> {target.name}: уклонение")
        return res

    # ------------------------------------------------------------------
    # Простой ИИ для врагов
    # ------------------------------------------------------------------

    def enemy_take_turn(self, enemy):
        """Враг атакует случайного живого союзника."""
        import random
        targets = self.alive_party()
        if not targets:
            return
        target = random.choice(targets)
        self.execute_basic_attack(enemy, target)
        self.commit_action(ActionWeight.LIGHT)

    # ------------------------------------------------------------------
    # Завершение боя
    # ------------------------------------------------------------------

    def _resolve_result(self):
        if not self.alive_party():
            self.result = RESULT_LOSE
        elif not self.alive_enemies():
            self.result = RESULT_WIN

    # ------------------------------------------------------------------
    # Данные для UI
    # ------------------------------------------------------------------

    def ui_combatant_statuses(self, combatant):
        """Список (name, duration) активных статусов для отображения в UI."""
        from combat.status import get_statuses, status_name_ru
        result = []
        for s in get_statuses(combatant):
            result.append((status_name_ru(s.status_id), s.duration))
        return result

    def ui_party_data(self):
        return [
            {
                "name":     c.name,
                "hp":       c.hp_current,
                "hp_max":   c.hp_max,
                "resource": c.resource_current,
                "res_max":  c.resource_max,
                "res_type": c.resource_type,
                "alive":    c.is_alive(),
                "active":   c is self.current_actor,
                "statuses": self.ui_combatant_statuses(c),
            }
            for c in self.party
        ]

    def ui_enemy_data(self):
        return [
            {
                "name":     c.name,
                "hp":       c.hp_current,
                "hp_max":   c.hp_max,
                "alive":    c.is_alive(),
                "active":   c is self.current_actor,
                "statuses": self.ui_combatant_statuses(c),
            }
            for c in self.enemies
        ]

    def ui_queue(self, slots=6):
        return [c.name for c in self.get_queue(slots)]

    def recent_log(self, n=6):
        return self.log[-n:]
