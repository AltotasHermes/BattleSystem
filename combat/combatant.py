import math

# --- Константы ---

RESOURCE_MP      = "mp"
RESOURCE_ENERGY  = "energy"
RESOURCE_SUPPLIES = "supplies"
RESOURCE_NOUS    = "nous"

CRIT_BASE        = 1.5
CRIT_CAP         = 2.5
EVADE_CAP        = 0.425   # ~40-45%, берём середину
LOG_DENOM        = math.log(51)  # log(stat_max + 1)


# --- Вспомогательные функции ---

def _log_curve(stat, cap):
    """Логарифмическая кривая: 0 при stat=0, cap при stat=50."""
    if stat <= 0:
        return 0.0
    return math.log(stat + 1) / LOG_DENOM * cap


# --- Основной класс ---

class Combatant:
    """
    Базовый класс для всех участников боя — союзников и врагов.
    Хранит статы, производные характеристики и текущее состояние.
    """

    def __init__(
        self,
        name,
        mettle, sense, finesse, glamour, luck,
        resource_type,
        resource_max,
        armor=0,
        magic_armor=0,
        is_enemy=False,
    ):
        self.name = name
        self.is_enemy = is_enemy

        # Базовые статы
        self.mettle  = mettle
        self.sense   = sense
        self.finesse = finesse
        self.glamour = glamour
        self.luck    = luck

        # Ресурс
        self.resource_type = resource_type
        self.resource_max  = resource_max
        # Энергия стартует пустой, остальные — полными
        if resource_type == RESOURCE_ENERGY:
            self.resource_current = 0
        else:
            self.resource_current = resource_max

        # Броня (добавляется снаряжением)
        self.armor       = armor
        self.magic_armor = magic_armor

        # Производные — считаются сразу
        self._recalc()

        # Текущее HP
        self.hp_current = self.hp_max

        # CTB-таймер (финальное значение устанавливается через init_timers)
        self.ctb_timer = 0.0

        # Stagger-шкала (финальные значения задаются через init_stagger)
        self.stagger_max     = 100.0
        self.stagger_current = 0.0
        self._in_stagger_break = False

        # Служебные флаги статусов
        self._stunned  = False
        self._slow_mod = 1.0

    # ------------------------------------------------------------------
    # Производные характеристики
    # ------------------------------------------------------------------

    def _recalc(self):
        """Пересчитывает все производные из текущих базовых статов."""
        self.hp_max      = self.mettle * 12
        self.ctb_speed   = self.finesse * 1.5

        self.phys_def_stat = (self.mettle + self.finesse) / 2
        self.mag_def_stat  = (self.sense + self.glamour) / 2

        self.evade_pct   = _log_curve(self.finesse, EVADE_CAP)
        self.accuracy_pct = _log_curve(self.sense, EVADE_CAP)

        self.crit_chance = _log_curve(self.luck, 0.40)   # потолок крит-шанса 40%
        self.crit_mult   = CRIT_BASE + _log_curve(self.luck, CRIT_CAP - CRIT_BASE)

    # ------------------------------------------------------------------
    # Удобные методы
    # ------------------------------------------------------------------

    def is_alive(self):
        return self.hp_current > 0

    def take_damage(self, amount):
        self.hp_current = max(0, self.hp_current - amount)

    def heal(self, amount):
        self.hp_current = min(self.hp_max, self.hp_current + amount)

    def spend_resource(self, amount):
        """Возвращает True если хватило ресурса."""
        if self.resource_current >= amount:
            self.resource_current -= amount
            return True
        return False

    def restore_resource(self, amount):
        self.resource_current = min(self.resource_max, self.resource_current + amount)

    # ------------------------------------------------------------------
    # Отладочный вывод
    # ------------------------------------------------------------------

    def debug_print(self):
        print(f"=== {self.name} {'[враг]' if self.is_enemy else '[союзник]'} ===")
        print(f"  Статы    mettle={self.mettle} sense={self.sense} "
              f"finesse={self.finesse} glamour={self.glamour} luck={self.luck}")
        print(f"  HP       {self.hp_current}/{self.hp_max}")
        print(f"  Ресурс   [{self.resource_type}] {self.resource_current}/{self.resource_max}")
        print(f"  Скорость CTB  {self.ctb_speed:.1f}")
        print(f"  Физ.защита(стат) {self.phys_def_stat:.1f}  "
              f"Маг.защита(стат) {self.mag_def_stat:.1f}")
        print(f"  Уклонение {self.evade_pct*100:.1f}%  "
              f"Меткость {self.accuracy_pct*100:.1f}%")
        print(f"  Крит-шанс {self.crit_chance*100:.1f}%  "
              f"Крит-множитель x{self.crit_mult:.2f}")
        print()
