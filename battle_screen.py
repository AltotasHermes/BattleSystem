## battle.rpy
## Разрешение: 1920x1080

init python:
    import sys, os
    _base = os.path.join(renpy.config.gamedir, "scripts", "new_combat")
    if _base not in sys.path:
        sys.path.insert(0, _base)

    from combat.battle_context import BattleContext, RESULT_WIN, RESULT_LOSE
    from combat.ctb import ActionWeight
    from data.characters import make_graham, make_dummy_grunt, make_dummy_mage
    from data.graham_skills import build_graham_skills

define COL_BG       = "#0d0d0d"
define COL_PANEL    = "#141414"
define COL_PANEL2   = "#1c1c1c"
define COL_BORDER   = "#2e2e2e"
define COL_TEXT     = "#bbbbbb"
define COL_ACTIVE   = "#ffdd88"
define COL_HP_GOOD  = "#44bb66"
define COL_HP_LOW   = "#cc3333"
define COL_RES      = "#4477dd"
define COL_ENEMY    = "#dd5544"
define COL_DEAD     = "#444444"
define COL_BTN      = "#1e1e1e"
define COL_BTN_HVR  = "#2e2e2e"
define COL_BTN_SEL  = "#2a2a1a"
define COL_QUEUE    = "#1a1a2a"
define COL_DEBUG    = "#0a1a0a"
define COL_DEBUG_B  = "#1a2a1a"
define COL_LOCKED   = "#2a1a1a"
define COL_ON       = "#44aa44"
define COL_OFF      = "#aa3333"
define COL_CD       = "#886633"


screen battle_screen(ctx):

    default submenu      = None
    default skill_branch = None
    default pick_mode    = None
    default pick_action  = None
    default debug_open   = False

    add Solid(COL_BG)

    ## -----------------------------------------------------------------------
    ## CTB-ОЧЕРЕДЬ — по центру над врагами, y:20
    ## -----------------------------------------------------------------------
    frame:
        xalign 0.5
        ypos 20
        xsize 900
        ysize 46
        background Solid(COL_QUEUE)

        hbox:
            xalign 0.5
            yalign 0.5
            spacing 0

            for i, name in enumerate(ctx.ui_queue(10)):
                $ is_first = (i == 0)
                $ q_col  = COL_ACTIVE if is_first else COL_TEXT
                $ q_size = 16 if is_first else 13
                $ sep    = " > " if i < 9 else ""
                text ((">> " if is_first else "") + name + sep):
                    size q_size
                    color q_col

    ## -----------------------------------------------------------------------
    ## ЗОНА ВРАГОВ — x:0..1560, y:0..740
    ## -----------------------------------------------------------------------
    frame:
        xpos 0
        ypos 0
        xsize 1560
        ysize 740
        background Solid("#00000000")

        hbox:
            xalign 0.5
            yalign 0.5
            spacing 100

            for e in ctx.ui_enemy_data():
                $ e_col        = COL_DEAD if not e["alive"] else (COL_ACTIVE if e["active"] else COL_ENEMY)
                $ e_hp_c       = COL_HP_LOW if e["hp"] < e["hp_max"] * 0.3 else COL_HP_GOOD
                $ e_selectable = pick_mode == "enemy" and e["alive"]
                $ e_frame_bg   = "#2a2a0a" if e_selectable else "#181818"

                vbox:
                    xsize 220
                    spacing 8
                    xalign 0.5

                    if e_selectable:
                        button:
                            xsize 180
                            ysize 300
                            xalign 0.5
                            background Solid(e_frame_bg)
                            hover_background Solid("#3a3a1a")
                            action Return((pick_action[0], pick_action[1], e["name"]))
                            text e["name"][0]:
                                size 90
                                color COL_ACTIVE
                                xalign 0.5
                                yalign 0.5
                    else:
                        frame:
                            xsize 180
                            ysize 300
                            xalign 0.5
                            background Solid(e_frame_bg)
                            text e["name"][0]:
                                size 90
                                xalign 0.5
                                yalign 0.5
                                color e_col

                    if e_selectable:
                        text "[[выбрать]]" size 13 xalign 0.5 color COL_ACTIVE
                    else:
                        text e["name"] size 15 xalign 0.5 color e_col

                    bar:
                        xsize 200
                        ysize 10
                        xalign 0.5
                        value e["hp"]
                        range e["hp_max"]
                        left_bar Solid(e_hp_c)
                        right_bar Solid("#2a2a2a")

                    text (str(e["hp"]) + " / " + str(e["hp_max"])):
                        size 13
                        xalign 0.5
                        color COL_TEXT

    ## -----------------------------------------------------------------------
    ## ГЛАВНОЕ МЕНЮ — x:0..200, y:740..1080
    ## -----------------------------------------------------------------------
    frame:
        xpos 0
        ypos 740
        xsize 200
        ysize 340
        background Solid(COL_PANEL)

        vbox:
            xpos 0
            ypos 0
            spacing 0

            if ctx.current_actor is not None and not ctx.current_actor.is_enemy:

                textbutton "АТАКА":
                    xsize 200
                    ysize 68
                    background Solid(COL_BTN)
                    hover_background Solid(COL_BTN_HVR)
                    action [SetScreenVariable("submenu", None),
                            SetScreenVariable("skill_branch", None),
                            SetScreenVariable("pick_mode", "enemy"),
                            SetScreenVariable("pick_action", ("attack", None))]
                    text_size 17
                    text_color COL_TEXT
                    text_xalign 0.5

                textbutton "ЗАЩИТА":
                    xsize 200
                    ysize 68
                    background Solid(COL_BTN)
                    hover_background Solid(COL_BTN_HVR)
                    action [SetScreenVariable("submenu", None),
                            SetScreenVariable("skill_branch", None),
                            SetScreenVariable("pick_mode", None),
                            SetScreenVariable("pick_action", None),
                            Return(("guard", None, None))]
                    text_size 17
                    text_color COL_TEXT
                    text_xalign 0.5

                textbutton ("НАВЫКИ" + (" <<" if submenu == "skills" else " >>")):
                    xsize 200
                    ysize 68
                    background (Solid(COL_BTN_SEL) if submenu == "skills" else Solid(COL_BTN))
                    hover_background Solid(COL_BTN_HVR)
                    action [ToggleScreenVariable("submenu", "skills", None),
                            SetScreenVariable("skill_branch", None)]
                    text_size 17
                    text_color (COL_ACTIVE if submenu == "skills" else COL_TEXT)
                    text_xalign 0.5

                textbutton ("ПРЕДМЕТЫ" + (" <<" if submenu == "items" else " >>")):
                    xsize 200
                    ysize 68
                    background (Solid(COL_BTN_SEL) if submenu == "items" else Solid(COL_BTN))
                    hover_background Solid(COL_BTN_HVR)
                    action [ToggleScreenVariable("submenu", "items", None),
                            SetScreenVariable("skill_branch", None)]
                    text_size 17
                    text_color (COL_ACTIVE if submenu == "items" else COL_TEXT)
                    text_xalign 0.5

            else:
                frame:
                    xsize 200
                    ysize 340
                    background Solid(COL_PANEL)
                    text "Ожидание..." size 15 color COL_DEAD xalign 0.5 yalign 0.5

    ## -----------------------------------------------------------------------
    ## ПАНЕЛЬ ПАРТИИ — x:200..1560, y:740..1080
    ## -----------------------------------------------------------------------
    frame:
        xpos 200
        ypos 740
        xsize 1360
        ysize 340
        background Solid(COL_PANEL)

        hbox:
            xalign 0.5
            yalign 0.5
            spacing 30

            for p in ctx.ui_party_data():
                $ p_col  = COL_DEAD if not p["alive"] else (COL_ACTIVE if p["active"] else COL_TEXT)
                $ p_hp_c = COL_HP_LOW if p["hp"] < p["hp_max"] * 0.3 else COL_HP_GOOD
                $ p_res  = p["res_type"].upper()

                frame:
                    xsize 300
                    ysize 290
                    background Solid("#1a1a1a")

                    vbox:
                        xpos 16
                        ypos 14
                        spacing 10

                        text p["name"] size 18 color p_col

                        vbox:
                            spacing 3
                            text "HP" size 12 color COL_TEXT
                            bar:
                                xsize 265
                                ysize 9
                                value p["hp"]
                                range p["hp_max"]
                                left_bar Solid(p_hp_c)
                                right_bar Solid("#2a2a2a")
                            text (str(p["hp"]) + " / " + str(p["hp_max"])) size 12 color COL_TEXT

                        vbox:
                            spacing 3
                            text p_res size 12 color COL_RES
                            bar:
                                xsize 265
                                ysize 9
                                value p["resource"]
                                range p["res_max"]
                                left_bar Solid(COL_RES)
                                right_bar Solid("#2a2a2a")
                            text (str(p["resource"]) + " / " + str(p["res_max"])) size 12 color COL_TEXT

    ## -----------------------------------------------------------------------
    ## ПРАВАЯ ПАНЕЛЬ — ЛОГ — x:1560..1920
    ## -----------------------------------------------------------------------
    frame:
        xpos 1560
        ypos 0
        xsize 360
        ysize 1080
        background Solid(COL_PANEL)

        vbox:
            xpos 14
            ypos 20
            spacing 6

            text "ЛОГ" size 20 color COL_ACTIVE
            add Solid(COL_BORDER) xsize 332 ysize 1

            for line in ctx.recent_log(20):
                text line size 15 color COL_TEXT

    ## -----------------------------------------------------------------------
    ## ПОДМЕНЮ НАВЫКИ — x:200..440, y:740..1080
    ## Объявлено позже панели партии — рисуется поверх неё
    ## -----------------------------------------------------------------------
    if submenu == "skills" and ctx.current_actor is not None and not ctx.current_actor.is_enemy:
        frame:
            xpos 200
            ypos 740
            xsize 240
            ysize 340
            background Solid(COL_PANEL2)

            if skill_branch is None:
                ## Уровень 1 — список ветвей со статусом блокировки
                viewport:
                    xpos 0
                    ypos 0
                    xsize 240
                    ysize 340
                    mousewheel True
                    draggable True
                    vbox:
                        spacing 0
                        if hasattr(ctx.current_actor, "skillset"):
                            for branch_id, branch_name in ctx.current_actor.skillset.branches():
                                $ b_locked  = not ctx.current_actor.skillset.is_branch_unlocked(branch_name)
                                $ b_bg      = Solid(COL_LOCKED) if b_locked else Solid(COL_BTN)
                                $ b_col     = COL_DEAD if b_locked else COL_TEXT
                                $ b_suffix  = " [[заблок.]]" if b_locked else ""
                                if b_locked:
                                    frame:
                                        xsize 240
                                        ysize 68
                                        background b_bg
                                        text (branch_name + b_suffix):
                                            size 13
                                            color b_col
                                            xalign 0.1
                                            yalign 0.5
                                else:
                                    textbutton (branch_name + b_suffix):
                                        xsize 240
                                        ysize 68
                                        background b_bg
                                        hover_background Solid(COL_BTN_HVR)
                                        action SetScreenVariable("skill_branch", branch_id)
                                        text_size 13
                                        text_color b_col
                                        text_xalign 0.1

            else:
                ## Уровень 2 — скиллы выбранной ветви с кулдаунами
                vbox:
                    xpos 0
                    ypos 0
                    xsize 240
                    spacing 0

                    textbutton "< Назад":
                        xsize 240
                        ysize 40
                        background Solid(COL_BTN)
                        hover_background Solid(COL_BTN_HVR)
                        action SetScreenVariable("skill_branch", None)
                        text_size 13
                        text_color COL_ACTIVE
                        text_xalign 0.1

                    viewport:
                        xsize 240
                        ysize 300
                        mousewheel True
                        draggable True
                        vbox:
                            spacing 0
                            if hasattr(ctx.current_actor, "skillset"):
                                for sk in ctx.current_actor.skillset.all_in_branch(skill_branch):
                                    $ sk_ready   = ctx.current_actor.skillset.ui_skill_available(sk)
                                    $ sk_label   = ctx.current_actor.skillset.ui_skill_label(sk)
                                    $ sk_all     = sk.target_type in ("all_foe", "all_ally")
                                    $ sk_bg      = Solid(COL_CD) if not sk_ready else Solid(COL_BTN)
                                    $ sk_col     = COL_DEAD if not sk_ready else COL_TEXT
                                    if sk_ready:
                                        textbutton sk_label:
                                            xsize 240
                                            ysize 52
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
                                            xsize 240
                                            ysize 52
                                            background sk_bg
                                            text sk_label:
                                                size 13
                                                color sk_col
                                                xalign 0.05
                                                yalign 0.5

    ## -----------------------------------------------------------------------
    ## ДЕБАГ-МЕНЮ — левый верхний угол, x:0..280, y:0..высота
    ## Открывается кнопкой [DBG] в левом углу
    ## -----------------------------------------------------------------------
    frame:
        xpos 0
        ypos 0
        xsize 60
        ysize 36
        background Solid("#1a0a0a")

        textbutton ("[[DBG]]" if not debug_open else "[[X]]"):
            xsize 60
            ysize 36
            background Solid("#1a0a0a")
            hover_background Solid("#2a1a1a")
            action ToggleScreenVariable("debug_open", True, False)
            text_size 13
            text_color "#cc6644"
            text_xalign 0.5

    if debug_open and ctx.current_actor is not None and hasattr(ctx.current_actor, "skillset"):
        frame:
            xpos 0
            ypos 36
            xsize 280
            background Solid(COL_DEBUG)

            vbox:
                xpos 0
                ypos 0
                spacing 0

                ## Заголовок
                frame:
                    xsize 280
                    ysize 30
                    background Solid(COL_DEBUG_B)
                    text "ДЕБАГ — ВЕТВИ НАВЫКОВ":
                        size 12
                        color COL_ACTIVE
                        xalign 0.5
                        yalign 0.5

                ## Список всех ветвей с переключателем
                for branch_id, branch_name in ctx.current_actor.skillset.branches():
                    $ db_on  = ctx.current_actor.skillset.is_branch_unlocked(branch_name)
                    $ db_bg  = Solid("#0a1f0a") if db_on else Solid("#1f0a0a")
                    $ db_col = COL_ON if db_on else COL_OFF
                    $ db_lbl = "[[ВКЛ]]" if db_on else "[[ВЫКЛ]]"

                    frame:
                        xsize 280
                        ysize 42
                        background db_bg

                        hbox:
                            xpos 8
                            yalign 0.5
                            spacing 8

                            text branch_name:
                                size 12
                                color COL_TEXT
                                yalign 0.5
                                xsize 190

                            if db_on:
                                textbutton db_lbl:
                                    xsize 70
                                    ysize 36
                                    background Solid("#154015")
                                    hover_background Solid("#1a5a1a")
                                    action Function(ctx.current_actor.skillset.lock_branch, branch_name)
                                    text_size 12
                                    text_color COL_ON
                                    text_xalign 0.5
                            else:
                                textbutton db_lbl:
                                    xsize 70
                                    ysize 36
                                    background Solid("#401515")
                                    hover_background Solid("#5a1a1a")
                                    action Function(ctx.current_actor.skillset.unlock_branch, branch_name)
                                    text_size 12
                                    text_color COL_OFF
                                    text_xalign 0.5

                ## Разделитель
                frame:
                    xsize 280
                    ysize 1
                    background Solid(COL_BORDER)

                ## Пассивные скиллы
                frame:
                    xsize 280
                    ysize 30
                    background Solid(COL_DEBUG_B)
                    text "ПАССИВНЫЕ НАВЫКИ":
                        size 12
                        color COL_ACTIVE
                        xalign 0.5
                        yalign 0.5

                python:
                    _passives = ctx.current_actor.skillset.all_passive()

                if len(_passives) == 0:
                    frame:
                        xsize 280
                        ysize 36
                        background Solid(COL_DEBUG)
                        text "нет пассивных навыков":
                            size 12
                            color COL_DEAD
                            xalign 0.5
                            yalign 0.5
                else:
                    for ps in _passives:
                        $ ps_on  = ps.unlocked
                        $ ps_bg  = Solid("#0a1f0a") if ps_on else Solid("#1f0a0a")
                        $ ps_lbl = "[[ВКЛ]]" if ps_on else "[[ВЫКЛ]]"
                        $ ps_col = COL_ON if ps_on else COL_OFF

                        frame:
                            xsize 280
                            ysize 42
                            background ps_bg

                            hbox:
                                xpos 8
                                yalign 0.5
                                spacing 8

                                text ps.name:
                                    size 12
                                    color COL_TEXT
                                    yalign 0.5
                                    xsize 190

                                if ps_on:
                                    textbutton ps_lbl:
                                        xsize 70
                                        ysize 36
                                        background Solid("#154015")
                                        hover_background Solid("#1a5a1a")
                                        action SetField(ps, "unlocked", False)
                                        text_size 12
                                        text_color COL_ON
                                        text_xalign 0.5
                                else:
                                    textbutton ps_lbl:
                                        xsize 70
                                        ysize 36
                                        background Solid("#401515")
                                        hover_background Solid("#5a1a1a")
                                        action SetField(ps, "unlocked", True)
                                        text_size 12
                                        text_color COL_OFF
                                        text_xalign 0.5


## ---------------------------------------------------------------------------
## Labels
## ---------------------------------------------------------------------------

label test_battle:

    python:
        graham = make_graham()
        graham.skillset = build_graham_skills()
        ## Стартовая ветвь открыта, остальные заблокированы для демонстрации
        graham.skillset.unlock_branch("Режущее оружие")
        graham.resource_current = graham.resource_max
        enemies = [make_dummy_grunt(), make_dummy_mage()]
        ctx = BattleContext([graham], enemies)

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
