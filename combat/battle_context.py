"""
BattleContext — состояние одного боя.
Управляет циклом ходов, передаёт контекст в скиллы,
возвращает результат (победа / поражение / побег).

КОНТРАКТ CTB:
    commit_action() ОБЯЗАН быть вызван ровно один раз после каждого хода
    персонажа, независимо от того какое действие было выбрано. Именно там
    тикают кулдауны skillset и применяется CTB-задержка. Пропуск вызова
    заморозит кулдауны и нарушит порядок очереди.
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

        self.result  = None
        self.log     = []
        self.current_actor = None
        self._action_committed = False  # контроль: commit_action вызван в этом ходу

        init_timers(self.all)

        # Запускаем on_battle_start для всех участников с SkillSet
        for c in self.all:
            if hasattr(c, "skillset"):
                c.skillset.fire_battle_start(c, self)

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
        self._action_committed = False

        decay_stagger(actor)
        tick_statuses(actor)

        return actor

    def commit_action(self, weight):
        """
        Фиксирует вес совершённого действия и сдвигает актора в очереди.
        Кулдауны тикают здесь — после действия, один раз за ход актора.

        Вызывать ровно один раз за ход. Повторный вызов в одном ходу
        вызовет AssertionError — это защита от случайного двойного применения
        задержки или двойного тика кулдаунов.
        """
        assert not self._action_committed, (
            f"commit_action вызван дважды за один ход "
            f"(актор: {self.current_actor.name if self.current_actor else 'None'}). "
            "Проверь battle_loop — commit_action должен вызываться ровно один раз."
        )
        self._action_committed = True

        if self.current_actor:
            if hasattr(self.current_actor, "skillset"):
                self.current_actor.skillset.tick_cooldowns()
            apply_delay(self.current_actor, weight)
            self._resolve_result()

    # ------------------------------------------------------------------
    # Базовая атака (без скилла)
    # ------------------------------------------------------------------

    def execute_basic_attack(self, actor, target):
        """
        Разрешает базовую атаку актора по цели.

        Порядок обработки реактивных механик:
          1. Если цель — союзник с активным Парированием (_parry_active),
             бросается шанс парирования. При успехе урон снижен вдвое,
             актор получает Энергию, флаг _parry_active снимается.
          2. Если цель — союзник с активной Железной стойкой (_iron_stance_active),
             входящий урон снижается на _iron_dr (20-30%), актор получает
             бонусную Энергию за каждый удар.
          3. Если цель — союзник с активным Встречным ударом (_counter_active),
             после получения урона выполняется контратака по атакующему.
          4. Если парирование выставило флаг _parry_auto_counter (Парирование III),
             при успешном парировании дополнительно выполняется контратака.
        """
        from combat.damage import resolve_damage, AttackData, DMG_SLASH
        from combat.stagger import add_stagger
        from combat.elemental_reactions import check_elemental_reaction
        from combat.combatant import RESOURCE_ENERGY
        import random

        atk = AttackData(
            damage_type=DMG_SLASH,
            scaling_stat=actor.mettle,
            weapon_mult=1.0,
            stagger_fill=0.15,
        )
        res = resolve_damage(actor, target, atk)

        if not res.hit or res.evaded:
            self.log.append(f"{actor.name} -> {target.name}: уклонение")
            return res

        # --- Парирование ---
        parry_succeeded = False
        if getattr(target, "_parry_active", False):
            parry_chance = getattr(target, "_parry_chance", 0.0)
            if random.random() < parry_chance:
                parry_succeeded = True
                # Урон снижен вдвое при парировании
                res.damage = max(1, res.damage // 2)
                energy_gain = getattr(target, "_parry_energy", 20)
                if target.resource_type == RESOURCE_ENERGY:
                    target.restore_resource(energy_gain)
                target._parry_active = False
                self.log.append(
                    f"{target.name}: парирование! Урон снижен, +{energy_gain} Энергии."
                )
                # Автоконтратака (Парирование III)
                if getattr(target, "_parry_auto_counter", False):
                    self._execute_counter(target, actor, mult=1.0, stun=False)

        # --- Железная стойка ---
        if getattr(target, "_iron_stance_active", False) and not parry_succeeded:
            dr = getattr(target, "_iron_dr", 0.20)
            res.damage = max(1, int(res.damage * (1.0 - dr)))
            energy_bonus = getattr(target, "_iron_energy_bonus", 0)
            if target.resource_type == RESOURCE_ENERGY:
                target.restore_resource(_IRON_STANCE_ENERGY_PER_HIT + energy_bonus)

        check_elemental_reaction(actor, target, DMG_SLASH, self.log)

        target.take_damage(res.damage)
        add_stagger(target, res.stagger_fill * target.stagger_max)

        # Хук on_hit_received — пассивы цели реагируют на полученный удар
        if hasattr(target, "skillset"):
            target.skillset.fire_hit_received(target, actor, res, self)

        # Хук on_ally_damaged — пассивы союзников реагируют на урон по товарищу
        allies = self.party if target in self.party else self.enemies
        for ally in allies:
            if ally is target:
                continue
            if hasattr(ally, "skillset"):
                ally.skillset.fire_ally_damaged(ally, target, actor, res, self)

        if actor.resource_type == RESOURCE_ENERGY:
            actor.restore_resource(15)

        label = "КРИТ" if res.crit else "удар"
        self.log.append(f"{actor.name} -> {target.name}: {label} {res.damage} урона")

        # --- Встречный удар ---
        if getattr(target, "_counter_active", False) and not parry_succeeded:
            counter_mult  = getattr(target, "_counter_mult", 0.7)
            counter_stun  = getattr(target, "_counter_stun", False)
            stun_chance   = getattr(target, "_counter_stun_chance", 0.0)
            heavy_pushback = getattr(target, "_counter_heavy_pushback", False)
            self._execute_counter(
                target, actor,
                mult=counter_mult,
                stun=counter_stun,
                stun_chance=stun_chance,
                heavy_pushback=heavy_pushback,
            )

        return res

    def _execute_counter(self, attacker, target, mult=1.0, stun=False,
                         stun_chance=0.0, heavy_pushback=False):
        """
        Внутренняя вспомогательная функция для контратаки и автоконтратаки.
        Выполняет удар вне очереди без CTB-задержки.
        """
        from combat.damage import resolve_damage, AttackData, DMG_SLASH
        from combat.stagger import add_stagger
        from combat.status import apply_status, make_stun
        from combat.ctb import push_back
        import random

        atk = AttackData(
            damage_type=DMG_SLASH,
            scaling_stat=attacker.mettle,
            weapon_mult=mult,
            stagger_fill=0.10,
        )
        res = resolve_damage(attacker, target, atk)

        if res.hit and not res.evaded:
            target.take_damage(res.damage)
            add_stagger(target, res.stagger_fill * target.stagger_max)

            label = "КРИТ" if res.crit else "контратака"
            self.log.append(
                f"{attacker.name} -> {target.name}: {label} {res.damage} урона"
            )

            if stun and random.random() < stun_chance:
                apply_status(target, make_stun(duration=1))
                self.log.append(f"{target.name}: Оглушение от контратаки.")

            if heavy_pushback:
                push_back(target, 10.0)
                self.log.append(f"{target.name}: Откат от тяжёлой контратаки.")
        else:
            self.log.append(f"{attacker.name}: контратака — уклонение.")

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

    def apply_debuff_with_passives(self, actor, target, effect):
        """
        Накладывает дебафф на цель и уведомляет пассивы актора через
        fire_debuff_applied_by. Использовать вместо прямого apply_status
        в скиллах которые хотят взаимодействовать с Регентской волей
        и Холодным расчётом.

        Возвращает True если статус был наложен.
        """
        from combat.status import apply_status
        applied = apply_status(target, effect)
        if applied and hasattr(actor, "skillset"):
            actor.skillset.fire_debuff_applied_by(actor, target, effect, self)
        return applied

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


# ---------------------------------------------------------------------------
# Константа для Железной стойки (используется в execute_basic_attack)
# ---------------------------------------------------------------------------

_IRON_STANCE_ENERGY_PER_HIT = 8
