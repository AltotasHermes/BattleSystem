from combat.combatant import Combatant, RESOURCE_ENERGY, RESOURCE_MP, RESOURCE_SUPPLIES, RESOURCE_NOUS
from combat.stagger import init_stagger


def make_graham(level=1):
    """Грэм Вос — стартовые статы (1 уровень)."""
    c = Combatant(
        name="Graham Vos",
        mettle=18, sense=10, finesse=12, glamour=6, luck=4,
        resource_type=RESOURCE_ENERGY,
        resource_max=120,
        armor=2,
    )
    init_stagger(c, stagger_max=80)
    return c


# --- Тестовые болванчики-враги ---

def make_dummy_grunt():
    """Рядовой противник. Усреднённые статы, без особенностей."""
    c = Combatant(
        name="Grunt",
        mettle=10, sense=8, finesse=8, glamour=4, luck=2,
        resource_type=RESOURCE_ENERGY,
        resource_max=60,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=60)
    return c


def make_dummy_mage():
    """Вражеский маг. Высокое sense, низкое mettle."""
    c = Combatant(
        name="Mage Drone",
        mettle=5, sense=15, finesse=8, glamour=10, luck=3,
        resource_type=RESOURCE_MP,
        resource_max=80,
        magic_armor=2,
        is_enemy=True,
    )
    init_stagger(c, stagger_max=50)
    return c
