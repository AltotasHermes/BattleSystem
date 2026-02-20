import math

RESOURCE_MP      = "mp"
RESOURCE_ENERGY  = "energy"
RESOURCE_SUPPLIES = "supplies"
RESOURCE_NOUS    = "nous"

CRIT_BASE        = 1.5
CRIT_CAP         = 2.5
EVADE_CAP        = 0.425
LOG_DENOM        = math.log(51)


def _log_curve(stat, cap):
    if stat <= 0:
        return 0.0
    return math.log(stat + 1) / LOG_DENOM * cap


class Combatant:

    def __init__(self, name, mettle, sense, finesse, glamour, luck,
                 resource_type, resource_max, armor=0, magic_armor=0, is_enemy=False):
        self.name = name
        self.is_enemy = is_enemy
        self.mettle  = mettle
        self.sense   = sense
        self.finesse = finesse
        self.glamour = glamour
        self.luck    = luck
        self.resource_type = resource_type
        self.resource_max  = resource_max
        if resource_type == RESOURCE_ENERGY:
            self.resource_current = 0
        else:
            self.resource_current = resource_max
        self.armor       = armor
        self.magic_armor = magic_armor
        self._recalc()
        self.hp_current = self.hp_max
        self.ctb_timer = 0.0
        self.stagger_max     = 100.0
        self.stagger_current = 0.0
        self._in_stagger_break = False
        self._stunned  = False
        self._asleep   = False
        self._paralyzed = False
        self._terrified = False
        self._slow_mod = 1.0
        self._weakness_mult = 1.0
        self._burn_heal_mod = 1.0
        self._wet_active = False
        self._chill_frost_bonus = 0.0

    def _recalc(self):
        self.hp_max      = self.mettle * 12
        self.ctb_speed   = self.finesse * 1.5
        self.phys_def_stat = (self.mettle + self.finesse) / 2
        self.mag_def_stat  = (self.sense + self.glamour) / 2
        self.evade_pct   = _log_curve(self.finesse, EVADE_CAP)
        self.accuracy_pct = _log_curve(self.sense, EVADE_CAP)
        self.crit_chance = _log_curve(self.luck, 0.40)
        self.crit_mult   = CRIT_BASE + _log_curve(self.luck, CRIT_CAP - CRIT_BASE)

    def is_alive(self):
        return self.hp_current > 0

    def take_damage(self, amount):
        self.hp_current = max(0, self.hp_current - amount)

    def heal(self, amount):
        from combat.damage import resolve_heal
        actual = resolve_heal(self, amount)
        self.hp_current = min(self.hp_max, self.hp_current + actual)

    def spend_resource(self, amount):
        if self.resource_current >= amount:
            self.resource_current -= amount
            return True
        return False

    def restore_resource(self, amount):
        self.resource_current = min(self.resource_max, self.resource_current + amount)
