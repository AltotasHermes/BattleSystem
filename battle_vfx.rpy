## battle_vfx.rpy
## Программные визуальные компоненты для боевого экрана.
## Кастомные Displayable — градиенты, анимированные бары, рамки, частицы.
## Никаких внешних ассетов — всё рисуется через Canvas.

init -10 python:
    import math
    import random as _rng

    # ===================================================================
    # GradientRect — прямоугольник с вертикальным или горизонтальным
    # градиентом между двумя цветами.
    # ===================================================================

    class GradientRect(renpy.Displayable):
        """
        Рисует прямоугольник с линейным градиентом.

        direction: "horizontal" | "vertical"
        color_a, color_b: кортежи (r, g, b, a) в диапазоне 0..255
        """

        def __init__(self, width, height, color_a, color_b,
                     direction="horizontal", **kwargs):
            super(GradientRect, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.ca = color_a
            self.cb = color_b
            self.dir = direction

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)
            canvas = rv.canvas()
            steps = self.w if self.dir == "horizontal" else self.h

            for i in range(steps):
                t = i / max(1, steps - 1)
                r = int(self.ca[0] + (self.cb[0] - self.ca[0]) * t)
                g = int(self.ca[1] + (self.cb[1] - self.ca[1]) * t)
                b = int(self.ca[2] + (self.cb[2] - self.ca[2]) * t)
                a = int(self.ca[3] + (self.cb[3] - self.ca[3]) * t)
                col = (r, g, b, a)

                if self.dir == "horizontal":
                    canvas.line(col, (i, 0), (i, self.h - 1))
                else:
                    canvas.line(col, (0, i), (self.w - 1, i))

            return rv

        def visit(self):
            return []


    # ===================================================================
    # PulseBar — HP / ресурсный бар с пульсацией при низком значении.
    # Рисуется как заполненный прямоугольник с опциональной анимацией.
    # ===================================================================

    class PulseBar(renpy.Displayable):
        """
        Анимированный бар с пульсацией.
        При value < threshold * max_val — бар мигает между col и pulse_col.
        """

        def __init__(self, width, height, value, max_val,
                     col, bg_col, pulse_col=None, threshold=0.3,
                     border_col=None, **kwargs):
            super(PulseBar, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.value = value
            self.max_val = max(1, max_val)
            self.col = col
            self.bg_col = bg_col
            self.pulse_col = pulse_col or col
            self.threshold = threshold
            self.border_col = border_col

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)
            canvas = rv.canvas()

            # Фон бара
            canvas.rect(self.bg_col, (0, 0, self.w, self.h))

            # Заполнение
            fill_pct = max(0.0, min(1.0, self.value / self.max_val))
            fill_w = int(self.w * fill_pct)

            if fill_w > 0:
                low = self.value < self.max_val * self.threshold
                if low and self.pulse_col != self.col:
                    # Пульсация через синус
                    pulse = (math.sin(st * 5.0) + 1.0) / 2.0
                    r = int(self.col[0] + (self.pulse_col[0] - self.col[0]) * pulse)
                    g = int(self.col[1] + (self.pulse_col[1] - self.col[1]) * pulse)
                    b = int(self.col[2] + (self.pulse_col[2] - self.col[2]) * pulse)
                    a = int(self.col[3] + (self.pulse_col[3] - self.col[3]) * pulse)
                    bar_col = (r, g, b, a)
                else:
                    bar_col = self.col

                canvas.rect(bar_col, (0, 0, fill_w, self.h))

                # Блик на верхней части бара (1px светлее)
                highlight = (
                    min(255, bar_col[0] + 40),
                    min(255, bar_col[1] + 40),
                    min(255, bar_col[2] + 40),
                    bar_col[3],
                )
                if self.h > 3:
                    canvas.rect(highlight, (0, 0, fill_w, max(1, self.h // 4)))

            # Рамка
            if self.border_col:
                canvas.rect(self.border_col, (0, 0, self.w, 1))
                canvas.rect(self.border_col, (0, self.h - 1, self.w, 1))
                canvas.rect(self.border_col, (0, 0, 1, self.h))
                canvas.rect(self.border_col, (self.w - 1, 0, 1, self.h))

            # Перерисовка каждый кадр если идёт пульсация
            if self.value < self.max_val * self.threshold:
                renpy.redraw(self, 0.033)

            return rv

        def visit(self):
            return []


    # ===================================================================
    # BorderedFrame — программная рамка с тонкой границей
    # и опциональным свечением.
    # ===================================================================

    class BorderedFrame(renpy.Displayable):
        """
        Прямоугольная рамка с заливкой, тонкой границей
        и опциональным свечением (glow).
        """

        def __init__(self, width, height, bg_col, border_col,
                     glow_col=None, border_w=1, corner=0, **kwargs):
            super(BorderedFrame, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.bg_col = bg_col
            self.border_col = border_col
            self.glow_col = glow_col
            self.border_w = border_w

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)
            canvas = rv.canvas()

            # Свечение (внешнее, 2px)
            if self.glow_col:
                gw = 2
                for i in range(gw):
                    alpha = int(60 * (1.0 - i / gw))
                    gc = (self.glow_col[0], self.glow_col[1],
                          self.glow_col[2], alpha)
                    canvas.rect(gc, (i, i, self.w - i * 2, 1))
                    canvas.rect(gc, (i, self.h - 1 - i, self.w - i * 2, 1))
                    canvas.rect(gc, (i, i, 1, self.h - i * 2))
                    canvas.rect(gc, (self.w - 1 - i, i, 1, self.h - i * 2))

            # Фон
            bw = self.border_w
            canvas.rect(self.bg_col,
                        (bw, bw, self.w - bw * 2, self.h - bw * 2))

            # Граница
            for i in range(bw):
                canvas.rect(self.border_col,
                            (i, i, self.w - i * 2, 1))
                canvas.rect(self.border_col,
                            (i, self.h - 1 - i, self.w - i * 2, 1))
                canvas.rect(self.border_col,
                            (i, i, 1, self.h - i * 2))
                canvas.rect(self.border_col,
                            (self.w - 1 - i, i, 1, self.h - i * 2))

            return rv

        def visit(self):
            return []


    # ===================================================================
    # FloatingParticles — медленно плывущие частицы на фоне.
    # Создаёт атмосферу без внешних ассетов.
    # ===================================================================

    class FloatingParticles(renpy.Displayable):
        """
        Рисует медленно дрейфующие светящиеся точки.
        count  — количество частиц
        area   — (width, height) области рисования
        col    — базовый цвет (r, g, b)
        speed  — скорость движения
        """

        def __init__(self, area_w, area_h, count=30, col=(80, 120, 160),
                     speed=12.0, **kwargs):
            super(FloatingParticles, self).__init__(**kwargs)
            self.aw = area_w
            self.ah = area_h
            self.col = col
            self.speed = speed
            self.particles = []
            for _ in range(count):
                self.particles.append({
                    "x": _rng.uniform(0, area_w),
                    "y": _rng.uniform(0, area_h),
                    "vx": _rng.uniform(-1, 1) * speed,
                    "vy": _rng.uniform(-0.5, -0.1) * speed,
                    "size": _rng.randint(1, 3),
                    "alpha_base": _rng.uniform(0.2, 0.6),
                    "phase": _rng.uniform(0, 6.28),
                })

        def render(self, width, height, st, at):
            rv = renpy.Render(self.aw, self.ah)
            canvas = rv.canvas()

            for p in self.particles:
                # Позиция с оборачиванием
                x = (p["x"] + p["vx"] * st) % self.aw
                y = (p["y"] + p["vy"] * st) % self.ah

                # Мерцание
                alpha = p["alpha_base"] + 0.3 * math.sin(st * 1.5 + p["phase"])
                alpha = max(0.05, min(0.8, alpha))
                a = int(alpha * 255)

                col = (self.col[0], self.col[1], self.col[2], a)
                sz = p["size"]

                canvas.rect(col, (int(x), int(y), sz, sz))

            renpy.redraw(self, 0.05)
            return rv

        def visit(self):
            return []


    # ===================================================================
    # ScanLine — горизонтальная бегущая полоса-сканер.
    # Накладывается поверх панелей для sci-fi атмосферы.
    # ===================================================================

    class ScanLine(renpy.Displayable):
        """
        Анимированная горизонтальная полоса, медленно проходящая
        сверху вниз по области. Создаёт эффект CRT/голограммы.
        """

        def __init__(self, width, height, col=(100, 140, 180, 30),
                     speed=40.0, line_h=2, **kwargs):
            super(ScanLine, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.col = col
            self.speed = speed
            self.line_h = line_h

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)
            canvas = rv.canvas()

            y = int((st * self.speed) % self.h)

            # Основная линия
            canvas.rect(self.col, (0, y, self.w, self.line_h))

            # Размытие вверх/вниз
            for i in range(1, 4):
                fade_a = max(0, self.col[3] - i * 8)
                fade_col = (self.col[0], self.col[1], self.col[2], fade_a)
                if y - i >= 0:
                    canvas.rect(fade_col, (0, y - i, self.w, 1))
                if y + self.line_h + i < self.h:
                    canvas.rect(fade_col, (0, y + self.line_h + i, self.w, 1))

            renpy.redraw(self, 0.033)
            return rv

        def visit(self):
            return []


    # ===================================================================
    # ActiveGlow — анимированная рамка свечения вокруг активного юнита.
    # ===================================================================

    class ActiveGlow(renpy.Displayable):
        """
        Пульсирующая рамка свечения. Используется для выделения
        текущего активного персонажа или выбираемого врага.
        """

        def __init__(self, width, height, col=(255, 221, 136),
                     intensity=0.6, speed=3.0, border=2, **kwargs):
            super(ActiveGlow, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.col = col
            self.intensity = intensity
            self.speed = speed
            self.border = border

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)
            canvas = rv.canvas()

            pulse = (math.sin(st * self.speed) + 1.0) / 2.0
            alpha = int(self.intensity * 255 * (0.4 + 0.6 * pulse))

            for i in range(self.border):
                layer_a = max(0, alpha - i * 30)
                gc = (self.col[0], self.col[1], self.col[2], layer_a)
                # Верх
                canvas.rect(gc, (i, i, self.w - i * 2, 1))
                # Низ
                canvas.rect(gc, (i, self.h - 1 - i, self.w - i * 2, 1))
                # Лево
                canvas.rect(gc, (i, i, 1, self.h - i * 2))
                # Право
                canvas.rect(gc, (self.w - 1 - i, i, 1, self.h - i * 2))

            # Угловые акценты (3x3 яркие точки)
            corner_a = min(255, alpha + 40)
            cc = (self.col[0], self.col[1], self.col[2], corner_a)
            for cx, cy in [(0,0), (self.w-3,0), (0,self.h-3), (self.w-3,self.h-3)]:
                canvas.rect(cc, (cx, cy, 3, 3))

            renpy.redraw(self, 0.033)
            return rv

        def visit(self):
            return []


    # ===================================================================
    # DamageFlash — быстрая вспышка цвета для feedback при ударе.
    # ===================================================================

    class DamageFlash(renpy.Displayable):
        """
        Полупрозрачная вспышка, затухающая за flash_time секунд.
        Используется для визуального feedback при получении урона.
        """

        def __init__(self, width, height, col=(200, 50, 50, 80),
                     flash_time=0.3, **kwargs):
            super(DamageFlash, self).__init__(**kwargs)
            self.w = width
            self.h = height
            self.col = col
            self.flash_time = flash_time

        def render(self, width, height, st, at):
            rv = renpy.Render(self.w, self.h)

            if st < self.flash_time:
                canvas = rv.canvas()
                fade = 1.0 - (st / self.flash_time)
                a = int(self.col[3] * fade)
                col = (self.col[0], self.col[1], self.col[2], a)
                canvas.rect(col, (0, 0, self.w, self.h))
                renpy.redraw(self, 0.016)

            return rv

        def visit(self):
            return []


    # ===================================================================
    # Вспомогательные функции для палитры
    # ===================================================================

    def hex_to_rgba(hex_str, alpha=255):
        """Конвертирует #RRGGBB в (r, g, b, a)."""
        h = hex_str.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)

    def lerp_color(ca, cb, t):
        """Линейная интерполяция между двумя (r,g,b,a) цветами."""
        return tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(4))


    # ===================================================================
    # Палитра — RGBA-версии цветов для кастомных Displayable
    # ===================================================================

    PAL_BG          = (13, 13, 13, 255)
    PAL_PANEL       = (20, 20, 20, 255)
    PAL_PANEL2      = (28, 28, 28, 255)
    PAL_BORDER      = (46, 46, 46, 255)
    PAL_TEXT         = (187, 187, 187, 255)
    PAL_ACTIVE      = (255, 221, 136, 255)
    PAL_HP_GOOD     = (68, 187, 102, 255)
    PAL_HP_LOW      = (204, 51, 51, 255)
    PAL_HP_PULSE    = (255, 80, 80, 255)
    PAL_RES         = (68, 119, 221, 255)
    PAL_RES_ENERGY  = (221, 170, 51, 255)
    PAL_ENEMY       = (221, 85, 68, 255)
    PAL_DEAD        = (68, 68, 68, 255)
    PAL_QUEUE       = (26, 26, 42, 255)
    PAL_BAR_BG      = (42, 42, 42, 255)
    PAL_STATUS      = (204, 153, 68, 255)
    PAL_CHILL       = (100, 180, 255, 255)
    PAL_BURN        = (255, 120, 50, 255)
    PAL_POISON      = (120, 200, 80, 255)
