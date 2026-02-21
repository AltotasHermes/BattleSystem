"""
Фабрики персонажей и врагов.

Каждый Combatant получает поле resistances — словарь типа урона -> множитель.
1.0   = нет ни уязвимости ни сопротивления
> 1.0 = уязвимость (урон выше нормы)
< 1.0 = сопротивление (урон ниже нормы)
0.0   = иммунитет (урон нулевой)
"absorb" = поглощение (урон становится лечением)

Доступные типы урона:
    slash, blunt, ballistic   — физические
    fire, frost, thunder, wither — стихийные
"""

from combat.combatant import Combatant, RESOURCE_ENERGY, RESOURCE_MP
from combat.stagger import init_stagger

_NEUTRAL = {
    "slash":     1.0,
    "blunt":     1.0,
    "ballistic": 1.0,
    "fire":      1.0,
    "frost":     1.0,
    "thunder":   1.0,
    "wither":    1.0,
}


def _set_resistances(c, overrides: dict):
    c.resistances = dict(_NEUTRAL)
    c.resistances.update(overrides)


# ---------------------------------------------------------------------------
# СОЮЗНИКИ
# ---------------------------------------------------------------------------

def make_graham(level=1):
    c = Combatant(
        name="Грэм Вос",
        mettle=18, sense=10, finesse=12, glamour=6, luck=4,
        resource_type=RESOURCE_ENERGY,
        resource_max=120,
        armor=2,
    )
    init_stagger(c, stagger_max=80)
    _set_resistances(c, {
        "fire":   1.2,
        "frost":  0.85,
    })
    return c


def make_vespergrave(level=1):
    c = Combatant(
        name="Леди Веспергрейв",
        mettle=5, sense=17, finesse=8, glamour=14, luck=6,
        resource_type=RESOURCE_MP,
        resource_max=120,
        magic_armor=3,
    )
    init_stagger(c, stagger_max=55)
    _set_resistances(c, {
        "frost":  0.0,
        "fire":   1.35,
        "wither": 1.25,
        "thunder": 0.80,
    })
    c._staff_chill_bonus = 0.15
    return c


# ---------------------------------------------------------------------------
# ВРАГИ
# ---------------------------------------------------------------------------

def make_grunt(name="Разбойник"):
    """Рядовой физический боец. Слаб к Морозу и Увяданию."""
    c = Combatant(
        name=name,
        mettle=12, sense=7, finesse=9, glamour=4, luck=3,
        resource_type=RESOURCE_ENERGY,
        resource_max=60,
        armor=1,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=65)
    _set_resistances(c, {
        "frost":  1.2,
        "wither": 1.15,
    })
    return c


def make_armored_soldier(name="Бронированный солдат"):
    """
    Тяжёлый боец в броне. Сопротивление рубящему.
    Уязвим к дробящему и Грозе.
    """
    c = Combatant(
        name=name,
        mettle=16, sense=6, finesse=7, glamour=4, luck=2,
        resource_type=RESOURCE_ENERGY,
        resource_max=80,
        armor=5,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=100)
    _set_resistances(c, {
        "slash":   0.70,
        "blunt":   1.30,
        "thunder": 1.40,
        "frost":   0.80,
    })
    return c


def make_swamp_witch(name="Болотная ведьма"):
    """
    Маг Увядания и яда. Иммунна к своей стихии.
    Уязвима к Огню и дробящему.
    """
    c = Combatant(
        name=name,
        mettle=6, sense=14, finesse=8, glamour=12, luck=5,
        resource_type=RESOURCE_MP,
        resource_max=90,
        magic_armor=2,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=50)
    _set_resistances(c, {
        "wither":    0.0,
        "fire":      1.40,
        "blunt":     1.20,
        "ballistic": 1.15,
        "frost":     0.85,
    })
    c._ai_style = "wither_poison"
    return c


def make_frost_revenant(name="Морозный ревенант"):
    """
    Нежить Мороза. Поглощает Мороз — атаки Веспергрейв его лечат.
    Уязвим к Огню, Увяданию и дробящему.
    """
    c = Combatant(
        name=name,
        mettle=10, sense=10, finesse=6, glamour=8, luck=3,
        resource_type=RESOURCE_MP,
        resource_max=70,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=55)
    _set_resistances(c, {
        "frost":   "absorb",
        "fire":    1.50,
        "wither":  1.30,
        "blunt":   1.20,
        "slash":   0.80,
        "thunder": 0.90,
    })
    c._ai_style = "frost_caster"
    return c


def make_bandit_archer(name="Арбалетчик"):
    """
    Дальний боец. Высокая сноровка, быстрый.
    Уязвим к Грозе. Низкая stagger-шкала.
    """
    c = Combatant(
        name=name,
        mettle=7, sense=13, finesse=15, glamour=5, luck=6,
        resource_type=RESOURCE_ENERGY,
        resource_max=55,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=45)
    _set_resistances(c, {
        "thunder": 1.35,
        "slash":   1.10,
        "blunt":   0.90,
    })
    c._ai_style = "ranged"
    return c


# ---------------------------------------------------------------------------
# Алиасы для обратной совместимости
# ---------------------------------------------------------------------------

make_dummy_grunt = make_grunt
make_dummy_mage  = make_swamp_witch
