## battle_screen.rpy (улучшенная версия)
## Разрешение: 1920x1080
##
## Визуальные улучшения (программные, без внешних ассетов):
##   - Анимированные HP-бары с пульсацией при низком здоровье
##   - Пульсирующие рамки свечения для активного юнита
##   - Фоновые плывущие частицы в зоне врагов
##   - Скан-линия по панелям (CRT/голограмма)
##   - Градиентные разделители
##   - Анимированная CTB-очередь с плавным маркером
##   - Hover-подсветка при выборе целей
##   - Цветовая маркировка типов ресурсов
##   - Визуальные индикаторы статусов с цветовым кодированием
##   - Программные рамки с тонкими границами

init python:
    import sys, os
    _base = os.path.join(renpy.config.gamedir, "scripts", "new_combat")
    if _base not in sys.path:
        sys.path.insert(0, _base)

    from combat.battle_context import BattleContext, RESULT_WIN, RESULT_LOSE
    from combat.ctb import ActionWeight
    from data.characters import make_graham, make_vespergrave, make_dummy_grunt, make_dummy_mage
    from data.graham_skills import build_graham_skills
    from data.vespergrave_skills import build_vespergrave_skills

    # --- Цветовая маркировка статусов ---

    _STATUS_COLORS = {
        "chill":          "#64b4ff",
        "frostbite":      "#3090ff",
        "burn":           "#ff7832",
        "bleed":          "#cc4444",
        "bleed_heavy":    "#ff3333",
        "poison":         "#78c850",
        "poison_heavy":   "#50a030",
        "stun":           "#ffee66",
        "sleep":          "#aa88cc",
        "paralyze":       "#ddcc44",
        "silence":        "#8888aa",
        "slow":           "#7788aa",
        "slow_light":     "#8899aa",
        "weakness":       "#aa7755",
        "weakness_heavy": "#885533",
        "stagger_break":  "#ff6644",
        "wet":            "#44aadd",
        "wither":         "#88aa44",
        "terror":         "#9944aa",
        "regen":          "#44dd66",
        "cc_immune":      "#eedd88",
        "stalwart":       "#bbaa66",
        "vulnerable":     "#dd8844",
        "defense_break":  "#ee6633",
        "curse":          "#9955bb",
    }

    def _status_col(status_name_ru):
        """Возвращает цвет для русского названия статуса, ищем по id."""
        # Обратный маппинг из русского названия в id
        from combat.status import STATUS_NAMES_RU
        for sid, name_ru in STATUS_NAMES_RU.items():
            if name_ru == status_name_ru:
                return _STATUS_COLORS.get(sid, "#cc9944")
        return "#cc9944"

    # --- Цвет ресурса по типу ---

    def _res_color(res_type):
        mapping = {
            "energy":   "#ddaa33",
            "mp":       "#4477dd",
            "supplies": "#55aa55",
            "nous":     "#aa55cc",
        }
        return mapping.get(res_type, "#4477dd")

    def _res_rgba(res_type):
        mapping = {
            "energy":   PAL_RES_ENERGY,
            "mp":       PAL_RES,
            "supplies": (85, 170, 85, 255),
            "nous":     (170, 85, 204, 255),
        }
        return mapping.get(res_type, PAL_RES)


## -----------------------------------------------------------------------
## ЦВЕТОВЫЕ КОНСТАНТЫ (для Ren'Py screen language)
## -----------------------------------------------------------------------

define COL_BG       = "#0d0d0d"
define COL_PANEL    = "#141414"
define COL_PANEL2   = "#1c1c1c"
define COL_BORDER   = "#2e2e2e"
define COL_TEXT      = "#bbbbbb"
define COL_TEXT_DIM  = "#777777"
define COL_ACTIVE   = "#ffdd88"
define COL_HP_GOOD  = "#44bb66"
define COL_HP_LOW   = "#cc3333"
define COL_RES      = "#4477dd"
define COL_ENEMY    = "#dd5544"
define COL_DEAD     = "#444444"
define COL_BTN      = "#1e1e1e"
define COL_BTN_HVR  = "#2a2a2a"
define COL_BTN_SEL  = "#2a2a1a"
define COL_QUEUE    = "#12121e"
define COL_DEBUG    = "#0a1a0a"
define COL_DEBUG_B  = "#1a2a1a"
define COL_LOCKED   = "#2a1a1a"
define COL_ON       = "#44aa44"
define COL_OFF      = "#aa3333"
define COL_CD       = "#886633"
define COL_STATUS   = "#cc9944"
define COL_SEPARATOR = "#222222"
define COL_MENU_ACTIVE = "#332b15"


## -----------------------------------------------------------------------
## ATL TRANSFORMS
## -----------------------------------------------------------------------

## Мягкое появление элемента
transform fade_in_soft:
    alpha 0.0
    linear 0.3 alpha 1.0

## Пульсация для активного юнита
transform pulse_active:
    alpha 0.7
    linear 0.8 alpha 1.0
    linear 0.8 alpha 0.7
    repeat

## Мигание для критически низкого HP
transform pulse_danger:
    alpha 0.6
    linear 0.4 alpha 1.0
    linear 0.4 alpha 0.6
    repeat

## Плавный сдвиг для выделения выбираемого врага
transform enemy_selectable_pulse:
    alpha 0.85
    linear 0.5 alpha 1.0
    linear 0.5 alpha 0.85
    repeat

## Появление строки лога (снизу вверх)
transform log_line_appear:
    alpha 0.0 xoffset -8
    linear 0.15 alpha 1.0 xoffset 0

## Подсветка кнопки при наведении
transform btn_hover_glow:
    on hover:
        linear 0.1 zoom 1.02
    on idle:
        linear 0.1 zoom 1.0

## Мерцание иконки-маркера в очереди
transform queue_marker_pulse:
    alpha 0.8
    linear 0.3 alpha 1.0
    linear 0.3 alpha 0.8
    repeat


## -----------------------------------------------------------------------
## ОСНОВНОЙ ЭКРАН
## -----------------------------------------------------------------------

screen battle_screen(ctx):

    default submenu      = None
    default skill_branch = None
    default pick_mode    = None
    default pick_action  = None
    default debug_open   = False

    ## Фон
    add Solid(COL_BG)

    ## Фоновые частицы в зоне врагов
    add FloatingParticles(1560, 740, count=25, col=(50, 70, 100), speed=8.0)

    ## ===================================================================
    ## CTB-ОЧЕРЕДЬ — по центру над врагами
    ## ===================================================================
    frame:
        xalign 0.5
        ypos 12
        xsize 920
        ysize 52
        background Solid("#00000000")

        ## Рамка очереди
        add BorderedFrame(920, 52, PAL_QUEUE, (40, 40, 60, 255),
                          glow_col=(80, 80, 140))

        ## Скан-линия
        add ScanLine(920, 52, col=(60, 80, 120, 18), speed=25.0, line_h=1)

        hbox:
            xalign 0.5
            yalign 0.5
            spacing 0

            for i, name in enumerate(ctx.ui_queue(10)):
                $ is_first = (i == 0)
                $ q_col  = COL_ACTIVE if is_first else ("#8888aa" if i < 4 else "#555566")
                $ q_size = 16 if is_first else (14 if i < 4 else 12)
                $ sep    = "  \u203a  " if i < 9 else ""

                if is_first:
                    text ("\u25b6 " + name + sep):
                        size q_size
                        color q_col
                        at queue_marker_pulse
                else:
                    text (name + sep):
                        size q_size
                        color q_col

    ## ===================================================================
    ## ЗОНА ВРАГОВ
    ## ===================================================================
    frame:
        xpos 0
        ypos 0
        xsize 1560
        ysize 740
        background Solid("#00000000")

        hbox:
            xalign 0.5
            yalign 0.55
            spacing 80

            for e in ctx.ui_enemy_data():
                $ e_alive      = e["alive"]
                $ e_active     = e["active"]
                $ e_col        = COL_DEAD if not e_alive else (COL_ACTIVE if e_active else COL_ENEMY)
                $ e_hp_c       = COL_HP_LOW if e["hp"] < e["hp_max"] * 0.3 else COL_HP_GOOD
                $ e_selectable = pick_mode == "enemy" and e_alive
                $ e_low_hp     = e["hp"] < e["hp_max"] * 0.3

                $ e_hp_rgba     = PAL_HP_LOW if e_low_hp else PAL_HP_GOOD
                $ e_pulse_rgba  = PAL_HP_PULSE if e_low_hp else PAL_HP_GOOD

                vbox:
                    xsize 230
                    spacing 6
                    xalign 0.5

                    ## Аватар врага (буква + рамка)
                    fixed:
                        xsize 190
                        ysize 280
                        xalign 0.5

                        if e_selectable:
                            ## Пульсирующая рамка выбора
                            add ActiveGlow(190, 280, col=(255, 221, 100),
                                           intensity=0.8, speed=4.0, border=3) at enemy_selectable_pulse

                        elif e_active and e_alive:
                            ## Рамка активного врага
                            add ActiveGlow(190, 280, col=(221, 85, 68),
                                           intensity=0.5, speed=2.5, border=2)

                        if e_selectable:
                            button:
                                xsize 190
                                ysize 280
                                background Solid("#1a1a12")
                                hover_background Solid("#2a2a18")
                                action Return((pick_action[0], pick_action[1], e["name"]))
                                text e["name"][0]:
                                    size 80
                                    color COL_ACTIVE
                                    xalign 0.5
                                    yalign 0.45
                                text "[[выбрать]]":
                                    size 12
                                    color COL_ACTIVE
                                    xalign 0.5
                                    yalign 0.85
                                    at pulse_active
                        else:
                            frame:
                                xsize 190
                                ysize 280
                                background Solid("#151515")
                                text e["name"][0]:
                                    size 80
                                    xalign 0.5
                                    yalign 0.45
                                    color (COL_DEAD if not e_alive else ("#dd8866" if e_active else "#aa6655"))

                    ## Имя врага
                    text e["name"]:
                        size 14
                        xalign 0.5
                        color e_col

                    ## HP бар (анимированный)
                    fixed:
                        xsize 210
                        ysize 12
                        xalign 0.5
                        add PulseBar(210, 12, e["hp"], e["hp_max"],
                                     col=e_hp_rgba, bg_col=PAL_BAR_BG,
                                     pulse_col=e_pulse_rgba, threshold=0.3,
                                     border_col=(60, 60, 60, 255))

                    text (str(e["hp"]) + " / " + str(e["hp_max"])):
                        size 12
                        xalign 0.5
                        color (COL_TEXT if e_alive else COL_DEAD)

                    ## Статусы с цветовым кодированием
                    if e["statuses"]:
                        hbox:
                            spacing 6
                            xalign 0.5
                            for st_name, st_dur in e["statuses"]:
                                $ st_col = _status_col(st_name)
                                text (st_name + " " + str(st_dur)):
                                    size 11
                                    color st_col

    ## ===================================================================
    ## ГОРИЗОНТАЛЬНЫЙ РАЗДЕЛИТЕЛЬ — между зоной врагов и нижними панелями
    ## ===================================================================
    fixed:
        xpos 0
        ypos 737
        xsize 1560
        ysize 3
        add GradientRect(1560, 3,
                         (30, 30, 30, 0), (60, 60, 80, 255),
                         direction="horizontal")

    ## ===================================================================
    ## ГЛАВНОЕ МЕНЮ ДЕЙСТВИЙ
    ## ===================================================================
    frame:
        xpos 0
        ypos 740
        xsize 200
        ysize 340
        background Solid(COL_PANEL)

        ## Скан-линия по панели меню
        add ScanLine(200, 340, col=(40, 50, 70, 12), speed=20.0, line_h=1)

        ## Тонкая правая граница
        add Solid("#222233") xpos 198 ypos 0 xsize 2 ysize 340

        vbox:
            xpos 0
            ypos 0
            spacing 0

            if ctx.current_actor is not None and not ctx.current_actor.is_enemy:

                ## Индикатор чей ход (имя персонажа над кнопками)
                frame:
                    xsize 200
                    ysize 32
                    background Solid("#181818")
                    text ctx.current_actor.name:
                        size 13
                        color COL_ACTIVE
                        xalign 0.5
                        yalign 0.5
                        at pulse_active

                ## Тонкий разделитель
                add Solid(COL_SEPARATOR) xsize 200 ysize 1

                ## АТАКА
                $ _atk_sel = (pick_mode == "enemy" and pick_action == ("attack", None))
                textbutton "АТАКА":
                    xsize 200
                    ysize 66
                    background (Solid(COL_MENU_ACTIVE) if _atk_sel else Solid(COL_BTN))
                    hover_background Solid(COL_BTN_HVR)
                    action [SetScreenVariable("submenu", None),
                            SetScreenVariable("skill_branch", None),
                            SetScreenVariable("pick_mode", "enemy"),
                            SetScreenVariable("pick_action", ("attack", None))]
                    text_size 16
                    text_color (COL_ACTIVE if _atk_sel else COL_TEXT)
                    text_xalign 0.5

                add Solid(COL_SEPARATOR) xsize 200 ysize 1

                ## ЗАЩИТА
                textbutton "ЗАЩИТА":
                    xsize 200
                    ysize 66
                    background Solid(COL_BTN)
                    hover_background Solid(COL_BTN_HVR)
                    action [SetScreenVariable("submenu", None),
                            SetScreenVariable("skill_branch", None),
                            SetScreenVariable("pick_mode", None),
                            SetScreenVariable("pick_action", None),
                            Return(("guard", None, None))]
                    text_size 16
                    text_color COL_TEXT
                    text_xalign 0.5

                add Solid(COL_SEPARATOR) xsize 200 ysize 1

                ## НАВЫКИ
                $ _sk_open = (submenu == "skills")
                textbutton ("НАВЫКИ" + ("  \u25c0" if _sk_open else "  \u25b6")):
                    xsize 200
                    ysize 66
                    background (Solid(COL_MENU_ACTIVE) if _sk_open else Solid(COL_BTN))
                    hover_background Solid(COL_BTN_HVR)
                    action [ToggleScreenVariable("submenu", "skills", None),
                            SetScreenVariable("skill_branch", None)]
                    text_size 16
                    text_color (COL_ACTIVE if _sk_open else COL_TEXT)
                    text_xalign 0.5

                add Solid(COL_SEPARATOR) xsize 200 ysize 1

                ## ПРЕДМЕТЫ
                $ _it_open = (submenu == "items")
                textbutton ("ПРЕДМЕТЫ" + ("  \u25c0" if _it_open else "  \u25b6")):
                    xsize 200
                    ysize 66
                    background (Solid(COL_MENU_ACTIVE) if _it_open else Solid(COL_BTN))
                    hover_background Solid(COL_BTN_HVR)
                    action [ToggleScreenVariable("submenu", "items", None),
                            SetScreenVariable("skill_branch", None)]
                    text_size 16
                    text_color (COL_ACTIVE if _it_open else COL_TEXT)
                    text_xalign 0.5

            else:
                frame:
                    xsize 200
                    ysize 340
                    background Solid(COL_PANEL)
                    text "\u23f3 Ожидание...":
                        size 14
                        color COL_DEAD
                        xalign 0.5
                        yalign 0.5

    ## ===================================================================
    ## ПАНЕЛЬ ПАРТИИ
    ## ===================================================================
    frame:
        xpos 200
        ypos 740
        xsize 1360
        ysize 340
        background Solid(COL_PANEL)

        ## Скан-линия по панели партии
        add ScanLine(1360, 340, col=(40, 60, 80, 10), speed=30.0, line_h=1)

        hbox:
            xalign 0.5
            yalign 0.5
            spacing 20

            for p in ctx.ui_party_data():
                $ p_alive   = p["alive"]
                $ p_active  = p["active"]
                $ p_col     = COL_DEAD if not p_alive else (COL_ACTIVE if p_active else COL_TEXT)
                $ p_low_hp  = p["hp"] < p["hp_max"] * 0.3
                $ p_res_t   = p["res_type"]
                $ p_res_col = _res_color(p_res_t)
                $ p_res_lbl = p_res_t.upper()

                $ p_hp_rgba    = PAL_HP_LOW if p_low_hp else PAL_HP_GOOD
                $ p_pulse_rgba = PAL_HP_PULSE if p_low_hp else PAL_HP_GOOD
                $ p_rs_rgba    = _res_rgba(p_res_t)

                fixed:
                    xsize 310
                    ysize 300

                    ## Рамка с программной границей
                    add BorderedFrame(310, 300,
                                      (22, 22, 22, 255) if p_alive else (18, 18, 18, 255),
                                      (50, 50, 50, 255) if p_alive else (35, 35, 35, 255))

                    ## Свечение для активного персонажа
                    if p_active and p_alive:
                        add ActiveGlow(310, 300,
                                       col=(255, 221, 136),
                                       intensity=0.6, speed=2.0, border=2)

                    vbox:
                        xpos 16
                        ypos 14
                        spacing 10

                        ## Имя с индикатором активности
                        hbox:
                            spacing 8
                            yalign 0.5
                            if p_active and p_alive:
                                text "\u25b6":
                                    size 14
                                    color COL_ACTIVE
                                    yalign 0.5
                                    at pulse_active
                            text p["name"]:
                                size 17
                                color p_col
                                bold p_active

                        ## HP
                        vbox:
                            spacing 4
                            text "HP":
                                size 11
                                color (COL_HP_LOW if p_low_hp else "#888888")
                                at (pulse_danger if (p_low_hp and p_alive) else fade_in_soft)

                            fixed:
                                xsize 275
                                ysize 12
                                add PulseBar(275, 12, p["hp"], p["hp_max"],
                                             col=p_hp_rgba, bg_col=PAL_BAR_BG,
                                             pulse_col=p_pulse_rgba, threshold=0.3,
                                             border_col=(50, 50, 50, 255))

                            text (str(p["hp"]) + " / " + str(p["hp_max"])):
                                size 12
                                color COL_TEXT

                        ## Ресурс
                        vbox:
                            spacing 4
                            text p_res_lbl:
                                size 11
                                color p_res_col

                            fixed:
                                xsize 275
                                ysize 12
                                add PulseBar(275, 12, p["resource"], p["res_max"],
                                             col=p_rs_rgba, bg_col=PAL_BAR_BG,
                                             threshold=0.0,
                                             border_col=(50, 50, 50, 255))

                            text (str(p["resource"]) + " / " + str(p["res_max"])):
                                size 12
                                color COL_TEXT

                        ## Статусы
                        if p["statuses"]:
                            hbox:
                                spacing 6
                                xsize 275
                                for st_name, st_dur in p["statuses"]:
                                    $ st_col = _status_col(st_name)
                                    text (st_name + " " + str(st_dur)):
                                        size 11
                                        color st_col

    ## ===================================================================
    ## ПРАВАЯ ПАНЕЛЬ — ЛОГ
    ## ===================================================================
    frame:
        xpos 1560
        ypos 0
        xsize 360
        ysize 1080
        background Solid(COL_PANEL)

        ## Вертикальная левая граница
        add Solid("#1a1a2a") xpos 0 ypos 0 xsize 2 ysize 1080

        ## Скан-линия
        add ScanLine(360, 1080, col=(40, 50, 70, 8), speed=35.0, line_h=1)

        vbox:
            xpos 16
            ypos 16
            spacing 4

            ## Заголовок
            hbox:
                spacing 8
                text "\u2630":
                    size 18
                    color COL_ACTIVE
                text "ЛОГ":
                    size 18
                    color COL_ACTIVE

            ## Разделитель (градиентная линия)
            fixed:
                xsize 332
                ysize 2
                add GradientRect(332, 2,
                                 (255, 221, 136, 180), (255, 221, 136, 0),
                                 direction="horizontal")

            null height 8

            ## Строки лога
            for i, line in enumerate(ctx.recent_log(22)):
                $ log_alpha = 1.0 if i >= len(ctx.recent_log(22)) - 5 else 0.6
                $ log_col = COL_TEXT if log_alpha > 0.8 else COL_TEXT_DIM
                text line:
                    size 13
                    color log_col
                    at log_line_appear

    ## ===================================================================
    ## ПОДМЕНЮ НАВЫКИ
    ## ===================================================================
    if submenu == "skills" and ctx.current_actor is not None and not ctx.current_actor.is_enemy:
        frame:
            xpos 200
            ypos 740
            xsize 250
            ysize 340
            background Solid("#00000000")

            ## Рамка
            add BorderedFrame(250, 340, PAL_PANEL2, (50, 50, 60, 255))

            if skill_branch is None:
                ## Уровень 1 — список ветвей
                viewport:
                    xpos 2
                    ypos 2
                    xsize 246
                    ysize 336
                    mousewheel True
                    draggable True
                    vbox:
                        spacing 0
                        if hasattr(ctx.current_actor, "skillset"):
                            for branch_id, branch_name in ctx.current_actor.skillset.branches():
                                $ b_locked = not ctx.current_actor.skillset.is_branch_unlocked(branch_name)
                                $ b_bg     = Solid(COL_LOCKED) if b_locked else Solid(COL_BTN)
                                $ b_col    = COL_DEAD if b_locked else COL_TEXT
                                $ b_suffix = "  \U0001f512" if b_locked else ""
                                if b_locked:
                                    frame:
                                        xsize 246
                                        ysize 62
                                        background b_bg
                                        text (branch_name + b_suffix):
                                            size 13
                                            color b_col
                                            xalign 0.08
                                            yalign 0.5
                                else:
                                    textbutton (branch_name + "  \u25b6"):
                                        xsize 246
                                        ysize 62
                                        background b_bg
                                        hover_background Solid(COL_BTN_HVR)
                                        action SetScreenVariable("skill_branch", branch_id)
                                        text_size 13
                                        text_color b_col
                                        text_xalign 0.08
                                    add Solid(COL_SEPARATOR) xsize 246 ysize 1

            else:
                ## Уровень 2 — скиллы ветви
                vbox:
                    xpos 2
                    ypos 2
                    xsize 246
                    spacing 0

                    textbutton "\u25c0  Назад":
                        xsize 246
                        ysize 38
                        background Solid("#1a1a22")
                        hover_background Solid(COL_BTN_HVR)
                        action SetScreenVariable("skill_branch", None)
                        text_size 13
                        text_color COL_ACTIVE
                        text_xalign 0.08

                    add Solid(COL_SEPARATOR) xsize 246 ysize 1

                    viewport:
                        xsize 246
                        ysize 298
                        mousewheel True
                        draggable True
                        vbox:
                            spacing 0
                            if hasattr(ctx.current_actor, "skillset"):
                                for sk in ctx.current_actor.skillset.all_in_branch(skill_branch):
                                    $ sk_ready = ctx.current_actor.skillset.ui_skill_available(sk)
                                    $ sk_label = ctx.current_actor.skillset.ui_skill_label(sk)
                                    $ sk_all   = sk.target_type in ("all_foe", "all_ally")
                                    $ sk_bg    = Solid("#2a2210") if not sk_ready else Solid(COL_BTN)
                                    $ sk_col   = COL_DEAD if not sk_ready else COL_TEXT
                                    $ sk_cd_col = COL_CD if not sk_ready else COL_TEXT
                                    if sk_ready:
                                        textbutton sk_label:
                                            xsize 246
                                            ysize 50
                                            background sk_bg
                                            hover_background Solid(COL_BTN_HVR)
                                            action If(sk_all,
                                                true  = [SetScreenVariable("submenu", None),
                                                         SetScreenVariable("skill_branch", None),
                                                         SetScreenVariable("pick_mode", None),
                                                         SetScreenVariable("pick_action", None),
                                                         Return(("skill", sk.skill_id, None))],
                                                false = [SetScreenVariable("submenu", None),
                                                         SetScreenVariable("skill_branch", None),
                                                         SetScreenVariable("pick_mode", "enemy"),
                                                         SetScreenVariable("pick_action", ("skill", sk.skill_id))])
                                            text_size 13
                                            text_color sk_col
                                            text_xalign 0.05
                                    else:
                                        frame:
                                            xsize 246
                                            ysize 50
                                            background sk_bg
                                            text sk_label:
                                                size 13
                                                color sk_cd_col
                                                xalign 0.05
                                                yalign 0.5
                                    add Solid(COL_SEPARATOR) xsize 246 ysize 1

    ## ===================================================================
    ## ДЕБАГ-МЕНЮ
    ## ===================================================================
    frame:
        xpos 0
        ypos 0
        xsize 56
        ysize 32
        background Solid("#1a0a0a80")

        textbutton ("[[X]]" if debug_open else "[[DBG]]"):
            xsize 56
            ysize 32
            background Solid("#1a0a0a00")
            hover_background Solid("#2a1a1a")
            action ToggleScreenVariable("debug_open", True, False)
            text_size 11
            text_color "#cc6644"
            text_xalign 0.5

    if debug_open and ctx.current_actor is not None and hasattr(ctx.current_actor, "skillset"):
        frame:
            xpos 0
            ypos 32
            xsize 280
            background Solid(COL_DEBUG)

            vbox:
                xpos 0
                ypos 0
                spacing 0

                frame:
                    xsize 280
                    ysize 28
                    background Solid(COL_DEBUG_B)
                    text "ВЕТВИ НАВЫКОВ":
                        size 11
                        color COL_ACTIVE
                        xalign 0.5
                        yalign 0.5

                for branch_id, branch_name in ctx.current_actor.skillset.branches():
                    $ db_on  = ctx.current_actor.skillset.is_branch_unlocked(branch_name)
                    $ db_bg  = Solid("#0a1f0a") if db_on else Solid("#1f0a0a")
                    $ db_col = COL_ON if db_on else COL_OFF
                    $ db_lbl = "[[ON]]" if db_on else "[[OFF]]"

                    frame:
                        xsize 280
                        ysize 38
                        background db_bg

                        hbox:
                            xpos 8
                            yalign 0.5
                            spacing 8

                            text branch_name:
                                size 11
                                color COL_TEXT
                                yalign 0.5
                                xsize 190

                            if db_on:
                                textbutton db_lbl:
                                    xsize 65
                                    ysize 32
                                    background Solid("#154015")
                                    hover_background Solid("#1a5a1a")
                                    action Function(ctx.current_actor.skillset.lock_branch, branch_name)
                                    text_size 11
                                    text_color COL_ON
                                    text_xalign 0.5
                            else:
                                textbutton db_lbl:
                                    xsize 65
                                    ysize 32
                                    background Solid("#401515")
                                    hover_background Solid("#5a1a1a")
                                    action Function(ctx.current_actor.skillset.unlock_branch, branch_name)
                                    text_size 11
                                    text_color COL_OFF
                                    text_xalign 0.5

                frame:
                    xsize 280
                    ysize 1
                    background Solid(COL_BORDER)

                frame:
                    xsize 280
                    ysize 28
                    background Solid(COL_DEBUG_B)
                    text "ПАССИВНЫЕ НАВЫКИ":
                        size 11
                        color COL_ACTIVE
                        xalign 0.5
                        yalign 0.5

                python:
                    _passives = ctx.current_actor.skillset.all_passive()

                if len(_passives) == 0:
                    frame:
                        xsize 280
                        ysize 32
                        background Solid(COL_DEBUG)
                        text "нет пассивных навыков":
                            size 11
                            color COL_DEAD
                            xalign 0.5
                            yalign 0.5
                else:
                    for ps in _passives:
                        $ ps_on  = ps.unlocked
                        $ ps_bg  = Solid("#0a1f0a") if ps_on else Solid("#1f0a0a")
                        $ ps_lbl = "[[ON]]" if ps_on else "[[OFF]]"
                        $ ps_col = COL_ON if ps_on else COL_OFF

                        frame:
                            xsize 280
                            ysize 38
                            background ps_bg

                            hbox:
                                xpos 8
                                yalign 0.5
                                spacing 8

                                text ps.name:
                                    size 11
                                    color COL_TEXT
                                    yalign 0.5
                                    xsize 190

                                if ps_on:
                                    textbutton ps_lbl:
                                        xsize 65
                                        ysize 32
                                        background Solid("#154015")
                                        hover_background Solid("#1a5a1a")
                                        action SetField(ps, "unlocked", False)
                                        text_size 11
                                        text_color COL_ON
                                        text_xalign 0.5
                                else:
                                    textbutton ps_lbl:
                                        xsize 65
                                        ysize 32
                                        background Solid("#401515")
                                        hover_background Solid("#5a1a1a")
                                        action SetField(ps, "unlocked", True)
                                        text_size 11
                                        text_color COL_OFF
                                        text_xalign 0.5


## ---------------------------------------------------------------------------
## Labels (без изменений в логике)
## ---------------------------------------------------------------------------

label test_battle:

    python:
        graham = make_graham()
        graham.skillset = build_graham_skills()
        graham.skillset.unlock_branch("Режущее оружие")
        graham.resource_current = graham.resource_max

        vesp = make_vespergrave()
        vesp.skillset = build_vespergrave_skills()
        vesp.skillset.unlock_branch("Озноб")
        vesp.resource_current = vesp.resource_max

        enemies = [make_dummy_grunt(), make_dummy_mage()]
        ctx = BattleContext([graham, vesp], enemies)

    jump battle_loop


label battle_loop:

    python:
        actor = ctx.advance()

    if ctx.result == RESULT_WIN:
        jump battle_win
    if ctx.result == RESULT_LOSE:
        jump battle_lose

    if actor is not None and actor.is_enemy:
        python:
            ctx.enemy_take_turn(actor)
        jump battle_loop

    python:
        choice = renpy.call_screen("battle_screen", ctx=ctx)

    python:
        action, skill_id, target_name = choice

        if action == "attack":
            target = next((e for e in ctx.alive_enemies() if e.name == target_name), None)
            if target:
                ctx.execute_basic_attack(actor, target)
            ctx.commit_action(ActionWeight.LIGHT)

        elif action == "skill":
            if target_name is not None:
                targets = [e for e in ctx.alive_enemies() if e.name == target_name]
            else:
                targets = ctx.alive_enemies()
            if targets and hasattr(actor, "skillset"):
                actor.skillset.use(skill_id, actor, targets, ctx)
            ctx.commit_action(ActionWeight.MEDIUM)

        elif action == "guard":
            ctx.log.append(actor.name + " принимает защитную стойку.")
            ctx.commit_action(ActionWeight.GUARD)

    jump battle_loop


label battle_win:
    "Победа! Все враги повержены."
    return

label battle_lose:
    "Поражение. Партия уничтожена."
    return
