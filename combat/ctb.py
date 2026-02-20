"""
CTB-очередь (Conditional Turn Battle).

Логика: каждый участник хранит ctb_timer.
Тот у кого таймер наименьший — ходит следующим.
После действия участник получает задержку и уходит назад в очередь.
"""

# --- Веса действий ---

class ActionWeight:
    QUICK   = 0      # быстрое действие — без штрафа
    LIGHT   = 1.0    # лёгкая атака
    GUARD   = 0.8    # защита
    MEDIUM  = 1.5    # средний скилл
    HEAVY   = 2.0    # тяжёлый скилл


def _base_delay(combatant):
    """Базовая задержка (единица отсчёта) для данного участника."""
    return 100.0 / combatant.ctb_speed


def init_timers(combatants):
    """
    Устанавливает стартовые таймеры перед боем.
    Быстрые участники получают меньший таймер и ходят раньше.
    """
    for c in combatants:
        c.ctb_timer = _base_delay(c)


def get_next(combatants):
    """Возвращает участника с наименьшим таймером (следующий ход)."""
    alive = [c for c in combatants if c.is_alive()]
    if not alive:
        return None
    return min(alive, key=lambda c: c.ctb_timer)


def advance_to_next(combatants):
    """
    Сдвигает время вперёд: вычитает таймер текущего участника у всех.
    Вызывается перед тем как текущий участник совершает действие.
    """
    nxt = get_next(combatants)
    if nxt is None:
        return None
    delta = nxt.ctb_timer
    for c in combatants:
        if c.is_alive():
            c.ctb_timer -= delta
    return nxt


def apply_delay(combatant, weight):
    """Добавляет задержку после действия."""
    combatant.ctb_timer += _base_delay(combatant) * weight


def push_back(combatant, flat_amount):
    """
    Откат / Замедление — прямое прибавление к таймеру.
    flat_amount задаётся в абсолютных единицах (не зависит от скорости цели).
    """
    combatant.ctb_timer += flat_amount


def queue_snapshot(combatants, slots=8):
    """
    Возвращает список следующих slots участников в порядке очереди.
    Не изменяет реальные таймеры — работает на копии.
    Используется для отображения очереди в UI.
    """
    alive = [c for c in combatants if c.is_alive()]
    if not alive:
        return []

    # Рабочая копия таймеров
    timers = {c: c.ctb_timer for c in alive}
    result = []

    for _ in range(slots):
        if not timers:
            break
        nxt = min(timers, key=lambda c: timers[c])
        result.append(nxt)
        delta = timers[nxt]
        for c in timers:
            timers[c] -= delta
        # Добавляем задержку лёгкой атаки как дефолт для снэпшота
        timers[nxt] += _base_delay(nxt) * ActionWeight.LIGHT

    return result
