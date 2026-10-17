"""Drive cases for what 0.2.0 added, run through CleriaCore's own harness without touching its tree: a
scratch copy of the mock server with a patched slot_data fixture, and this mod packed as APLUA_MOD_ZIP.

    python <CleriaCore>/tools/pack_mod.py . -o <tmp>           # then copy the .cleriamod to <tmp>/mod.zip
    APLUA_MOD_ZIP=<tmp>/mod.zip python .dev/port_cases.py      # CLERIACORE=<checkout> if not ../YsOrigin-CleriaCore

These belong in CleriaCore's tools/aplua_regress.py once its bundled copy of the mod is synced (they need
roo_flags / random_start in the fixture and extra lines in the mod's settings section)."""
import json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
CC = os.environ.get("CLERIACORE") or os.path.join(os.path.dirname(MOD), "YsOrigin-CleriaCore")
SCR = os.path.join(tempfile.gettempdir(), "apport_cc_scratch")
sys.path.insert(0, os.path.join(CC, "tools"))
import aplua_regress, drive_regress   # noqa: E402

P = aplua_regress.P


def fixture(patch):
    shutil.rmtree(SCR, ignore_errors=True)
    os.makedirs(os.path.join(SCR, "tools"))
    os.makedirs(os.path.join(SCR, "tests", "ap"))
    shutil.copy(os.path.join(CC, "tools", "ap_mock_server.py"), os.path.join(SCR, "tools"))
    sd = json.load(open(os.path.join(CC, "tests", "ap", "test_slot_data.json"), encoding="utf-8"))
    sd.update(patch)
    json.dump(sd, open(os.path.join(SCR, "tests", "ap", "test_slot_data.json"), "w", encoding="utf-8"))
    d = os.path.join(SCR, "samples", "mods", "archipelago_lua", "data")
    os.makedirs(d)
    shutil.copy(os.path.join(MOD, "data", "ys_origin.json"), d)
    aplua_regress.ROOT = SCR          # only the server path uses it once APLUA_MOD_ZIP is set


def boss_on_flag():      # apworld 2.2: a boss check arrives as its fight's win flag (Velagunder: 220)
    sd = json.load(open(os.path.join(CC, "tests", "ap", "test_slot_data.json"), encoding="utf-8"))
    det = dict(sd["location_detect"])
    det["Boss: 5F Velagunder (S_1099)"] = {"method": "flag", "offset": "0x%X" % (0x36B91C + 4 * 220)}
    return dict(location_detect=det)


CASES = {
    # A 2.2 seed, "Boss checks on defeat" off: nothing at the door all the same, the check when 220 is set.
    "port_boss_flag_seed": (boss_on_flag(), dict(
        room="S_10/S_1099/S_1099", aplua={},
        drive="120:lua=apstate;130:flag=220,1;200:lua=apstate;220:quit",
        expect=["goal 0 active 1", "Boss: 5F Velagunder (S_1099) (", "goal 0 active 1"],
        absent=["Boss: 5F Velagunder (S_1099) (room)"])),
    # Roda Fruit derived from roo_flags: 2 received -> 2; the first Roo fed -> 1; a Roo beyond the count
    # fed (flag 414, the 5th) costs nothing: the script's -1 is refunded.
    "port_roda": (dict(roo_flags=[312, 339, 362, 388, 414, 458]), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:lua=apsay !give Roda Fruit;100:lua=apsay !give Roda Fruit;160:lua=apflag 0x57;"
              "170:flag=312,1;200:lua=apflag 0x57;210:flag=87,0;215:flag=414,1;240:lua=apflag 0x57;260:quit",
        expect=["Roda Fruit: Roda Fruit #1", "Roda Fruit: Roda Fruit #2", P + "flag 0x57 = 2",
                P + "flag 0x57 = 1", P + "flag 0x57 = 1"])),
    # A gem Roo (8F, S_2011): its two boxes (the Topaz, then "Lightning power increased!") come before its check, in
    # AGERU itself, and both name the seed's item; the gem's level is withheld and the check follows.
    "port_roo_box": (dict(roo_flags=[312, 339, 362, 388, 414, 458]), dict(
        room="S_20/S_2011/S_2011", aplua={},
        drive="60:lua=apsay !give Roda Fruit;150:run=AGERU;" + ";".join("%d:ok" % t for t in range(300, 1500, 100)) +
              ";1500:lua=apflag 339;1510:quit",
        expect=["Roda Fruit: Roda Fruit #1", P + "box S_2011/AGERU: Received\\nSP: 50.",
                P + "box S_2011/AGERU: Received\\nSP: 50.", P + "check 5857533 Flooded Prison: 8F Path 2 ", "Roo Trade (store)",
                P + "suppressed g_flags[0xB7] 0 -> 1 (S_2011/AGERU)", P + "flag 0x153 = 1"],
        absent=["power increased"])),
    # An elemental altar (S_2009) whose skill the seed moved: the skill withheld and the check sent. Where the engine
    # has cleria.script.stop (mod API 7) the event ends right there and the HUD it hid (flag 185) comes back; neither
    # CleriaCore nor CleriaOre has it yet (2026-10-17), and on CleriaCore the event plays out with nothing broken.
    # Either way the world runs again, no script left, the skill not held.
    "port_altar": (dict(), dict(
        room="S_20/S_2009/S_2009", aplua={},
        drive="10:killall;150:run=TalkC940;" + ";".join("%d:ok" % t for t in range(300, 1560, 60)) +
              ";1600:scripts;1610:lua=apflag 0x75;1620:lua=apflag 185;1630:quit",
        expect=[P + "suppressed g_flags[0x75] -1 -> 1 (S_2009/TALKC940)",
                P + "check 5857538 Flooded Prison: Skill Room ", "Levinstrike Warhammer (store)", "t1600 scripts",
                "frozen 0", P + "flag 0x75 = -1", P + "flag 0xB9 = 1"],
        absent=["script TalkC940 pc"])),
    # The EXP base / catch-up sliders: the fixture's seed multiplies a kill's EXP by 20 (level_scaling 2); with both
    # set to 2 the same five kills give 102, not 1029. The kills wait for the login (the factor is 1 before it).
    "port_exp_override": (dict(), dict(
        room="S_10/S_1002/S_1002", aplua={}, ini_extra="""ExpBase=2
ExpCatchup=2
""",
        drive="8:opt=DamageDealt=10;10:opt=DamageTaken=0;300:lua=apstate;314:stats;" +
              ";".join("%d:near=17;%d:atk" % (t, t + 1) for t in range(340, 441, 25)) + ";450:stats;460:quit",
        expect=["active 1", "stats exp 0 lv 1", "stats exp 102 lv 1"])),
    # Random start: a new game in S_1001 is warped to the seed's start statue once.
    "port_random_start": (dict(random_start=True, start_statue_scene=1009), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="300:lua=apstate;320:quit",
        expect=[P + "random start: warp to S_1009 (warp 1)", ">> entering S_1009"],
        absent=["not supported: Random start"])),
    # A vanilla weapon upgrade with no item behind it is clamped to what the seed granted; an ore raises it.
    "port_weapon_clamp": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:flag=148,4;120:lua=apflag 148;130:lua=apsay !give Cleria Ore;200:lua=apflag 148;"
              "210:flag=148,8;260:lua=apflag 148;280:quit",
        expect=[P + "flag 0x94 = 0", "Cleria Ore #1: weapon tier 1", P + "flag 0x94 = 1", P + "flag 0x94 = 1"])),
    # Boss checks on defeat: nothing at the door, the check when the fight's flag is set.
    "port_boss_on_kill": (dict(), dict(
        room="S_10/S_1099/S_1099", aplua={}, ini_extra="""BossOnKill=1
ShowRoom=1
RoomSpoilers=1
ShowTracker=1
TrackerMode=2
""",
        drive="120:lua=apstate;130:flag=220,1;200:lua=apstate;220:quit",
        expect=["goal 0 active 1", "Boss: 5F Velagunder (S_1099) (", "goal 0 active 1"],   # (sweep), or (boss defeated) with API 4
        absent=["Boss: 5F Velagunder (S_1099) (room)"])),
    # The same room with the option off: the check at the door (and the overlays drawn every frame).
    "port_boss_on_entry": (dict(), dict(
        room="S_10/S_1099/S_1099", aplua={}, ini_extra="""ShowRoom=1
ShowTracker=1
""",
        drive="120:lua=apstate;140:quit",
        expect=["Boss: 5F Velagunder (S_1099) (room)", "goal 0 active 1"],
        absent=["script stopped", "Mod stopped"])),
    # The mod's page drawn (every section, connected and in game) without a script error.
    "port_page": (dict(goal=1), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="120:shell=Mods:ysorigin.archipelago;200:lua=apstate;220:quit",
        expect=["goal 0 active 1"],
        absent=["script stopped", "Mod stopped", "attempt to"])),
    # An SP chest that is a location: the script's AddPlayerSP (not a grant the filter sees) is taken back.
    "port_sp_chest": (dict(), dict(
        room="S_40/S_4015/S_4015", aplua={},
        drive="10:kill1;300:lua=apsp;420:obj=box_01;430:act;740:ok;760:lua=apsp;780:quit",
        expect=[P + "sp = ", P + "SP chest: took back the vanilla 5000 SP (S_4015/S_BOX01)",
                "Silent Sands: 15F Room (store)", P + "sp = "],
        absent=["sp = 5", "sp = 6"])),          # the wallet never shows the chest's 5000
    # Toal and Rado's Annex: his story flags 269 / 289 start the stoppers of S_4014 and S_4104 (and keep the Shion
    # chain from ending). They are held at 0 in those rooms, so S_4104 never starts Kadena_Stopper...
    "port_toal_annex": (dict(), dict(
        room="S_40/S_4014/S_4014", char="3", aplua={},
        drive="60:flag=289,1;61:flag=269,1;120:lua=apflag 289;150:exit=2;400:scripts;420:lua=apflag 269;440:quit",
        expect=[P + "repair: Rado's Annex: Toal's story flag 289 held at 0", P + "flag 0x121 = 0", ">> entering S_4104",
                P + "flag 0x10D = 0"],
        absent=["script Kadena_Stopper"])),
    # ...and put back on the way out (S_4019).
    "port_toal_annex_out": (dict(), dict(
        room="S_40/S_4014/S_4014", char="3", aplua={},
        drive="60:flag=289,1;120:lua=apflag 289;150:exit=0;400:lua=apflag 289;420:quit",
        expect=[P + "flag 0x121 = 0", ">> entering S_4019", P + "repair: Rado's Annex: Toal's story flag 289 put back",
                P + "flag 0x121 = 1"])),
    # ...and the Shion fight's chain ends with 289 set: S_4104 runs EV_4104_Thor (not the stopper branch), on to
    # S_4017 and S_4021, where 232 = 1 stops S_3080 from starting the fight again; back in S_3006, 289 is back.
    "port_toal_shion_chain": (dict(), dict(
        room="S_30/S_3080/S_3080", char="3", aplua={}, env=dict(drive_regress._LOCK, CLERIA_LEVEL="32"),
        drive="5:flag=289,1;" + drive_regress._S3080.format(end=30000, cast=170) +
              "29990:lua=apflag 232;29995:lua=apflag 289;30001:quit",
        expect=[P + "repair: Rado's Annex: Toal's story flag 289 held at 0", ">> entering S_4104", ">> entering S_4017",
                ">> entering S_4021", ">> entering S_3006", P + "repair: Rado's Annex: Toal's story flag 289 put back",
                P + "flag 0xE8 = 1", P + "flag 0x121 = 1"],
        absent=["script Kadena_Stopper"])),
    # Yunica after Zava (225): S_4104's root would start s_Evt4104_stop_Yunica. 225 is held at 0 from S_4014 on, so
    # the root takes the annex intro instead (260 == 0: EV_4104_Yunica)...
    "port_yunica_annex": (dict(), dict(
        room="S_40/S_4014/S_4014", char="1", aplua={},
        drive="300:flag=225,1;360:lua=apflag 225;390:exit=2;640:scripts;660:lua=apflag 225;680:quit",
        expect=[P + "repair: Rado's Annex: Yunica's story flag 225 held at 0", P + "flag 0xE1 = 0", ">> entering S_4104",
                P + "flag 0xE1 = 0"],
        absent=["s_Evt4104_stop_Yunica"])),
    # ...and put back on the way out (S_4019).
    "port_yunica_annex_out": (dict(), dict(
        room="S_40/S_4014/S_4014", char="1", aplua={},
        drive="300:flag=225,1;360:lua=apflag 225;390:exit=0;640:lua=apflag 225;660:quit",
        expect=[P + "flag 0xE1 = 0", ">> entering S_4019", P + "repair: Rado's Annex: Yunica's story flag 225 put back",
                P + "flag 0xE1 = 1"])),
    # Hugo between his 21F scene (272) and Pictimos (273): s_Evt4104_stop_Hugo. The flag is set on the tick of the
    # exit, so the hold made on room_enter (before the room's root runs) is the one that keeps the stopper off.
    "port_hugo_annex": (dict(), dict(
        room="S_40/S_4014/S_4014", char="2", aplua={},
        drive="300:lua=apstate;390:flag=272,1;390:exit=2;640:scripts;660:lua=apflag 272;680:quit",
        expect=["active 1", ">> entering S_4104", P + "repair: Rado's Annex: Hugo's story flag 272 held at 0", P + "flag 0x110 = 0"],
        absent=["s_Evt4104_stop_Hugo"])),
    # The 3F barrier before the first teleport: Yunica with the Blue Necklace on (a seed's early necklace) can stay in it,
    # beat its four guardians and break it for good (444 = 1), leaving the 4F rooms behind S_1009 out of reach. The necklace
    # comes off in S_1013, the event sends her to S_1009, and it goes back on there.
    "port_barrier_necklace": (dict(), dict(
        room="S_10/S_1013/S_1013", char="1", aplua={}, env=drive_regress._LOCK,
        drive="300:flag=55,1;301:acc=55;360:move=0,1,200;440:every=20,1000,ok;1100:lua=apflag 444;1120:quit",
        expect=[P + "repair: 3F barrier: the Blue Necklace taken off", ">> entering S_1009",
                P + "repair: 3F barrier: the Blue Necklace put back on", P + "flag 0x1BC = 0"])),
    # A save that already broke it that way (444 = 1, 310 = 0): the barrier is put back in S_1005, and S_1013 sends
    # her to S_1009 again.
    "port_barrier_repair": (dict(), dict(
        room="S_10/S_1005/S_1005", char="1", aplua={}, env=drive_regress._LOCK,
        drive="300:flag=444,1;360:lua=apflag 444;380:exit=2;440:move=0,1,200;520:every=20,1100,ok;1140:quit",
        expect=[P + "repair: 3F barrier: broken before the first teleport to 4F (S_1009): put back (444 = 0)",
                P + "flag 0x1BC = 0", ">> entering S_1013", ">> entering S_1009"])),
    # Mod API 4. Autosave: a chest check, then the save to the book's No.08 (file 7) at the next safe tick.
    "port_autosave": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive=aplua_regress.CHEST + ";740:ok;1000:lua=apstate;1020:quit",
        expect=[P + "check 5857605 Wailing Blue: 2F Path 1 (store)", "sidecar yso_07.cleria written",
                P + "autosave: wrote No.08"])),
    # Mod API 4. A level-up alone asks for the autosave.
    "port_autosave_level": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="300:level=5;700:lua=apstate;720:quit",
        expect=[P + "autosave: wrote No.08"])),
    # Mod API 6. A kill gives at least half the EXP multiplier: Hard, level 13 against a level-3 monster at x100
    # is 14 by the game's own rule (CleriaCore's lua_exp_floor), 50 here.
    "port_exp_floor": (dict(), dict(
        room="S_10/S_1002/S_1002", aplua={}, ini_extra="""ExpMultiplier=100
""",
        drive="5:diff=3;6:level=13;8:opt=DamageDealt=10;10:opt=DamageTaken=0;14:stats;" +
              ";".join("%d:near=17;%d:atk" % (t, t + 1) for t in range(40, 140, 25)) + ";150:stats;160:quit",
        expect=["stats exp 21936 lv 13", "stats exp 21986 lv 13"])),
    # Mod API 4. The boss_defeated event sends the boss check when "Boss checks on defeat" is on.
    "port_boss_event": (dict(), dict(
        room="S_10/S_1099/S_1099", aplua={}, ini_extra="""BossOnKill=1
""",
        drive="130:flag=220,1;200:lua=apstate;220:quit",
        expect=["Boss: 5F Velagunder (S_1099) (boss defeated)"],
        absent=["Boss: 5F Velagunder (S_1099) (room)"])),
    # The 20F room's fight is its ward, flag 423.
    "port_ward_5080": (dict(), dict(
        room="S_50/S_5080/S_5080", aplua={}, ini_extra="""BossOnKill=1
""",
        drive="130:flag=423,1;200:lua=apstate;220:quit",
        expect=["(S_5080) (sweep)"],
        absent=["Boss: Boss Room (S_5080) (room)"])),
    # The key-item clamp and the skill-level cap.
    # The statue shop (mod API 5): "Increase stationary heal rate" (@Grow00, 1000 SP in vanilla) is sold at the
    # seed's price for its location, on the row, at the wallet test and at the deduction, and the purchase is its check.
    "port_shop_price": (dict(blessing_costs={"5857332": 70}), dict(
        room="S_10/S_1009/S_1009", aplua={},
        drive=drive_regress.CLEANSE + ";200:sp=250;220:act;290:down;300:ok;390:down;400:ok;480:ok;570:ok;650:ok;"
              "730:ok;820:esc;835:stats;840:quit",
        expect=["[content] blessing_bought 0 for 70 SP", "check 5857332 Divine Blessing: Increase stationary heal rate"],
        absent=["not supported: Shuffled blessing prices"])),
    # one_per_floor: on the first floor visited only the cheapest slot is on sale. The heal rate (70) is the
    # second cheapest here, so the same purchase as port_shop_price is refused (the wallet test at 1000000).
    "port_shop_pacing": (dict(blessing_costs={"5857332": 70, "5857339": 60}, blessing_shop_unlock=1), dict(
        room="S_10/S_1009/S_1009", aplua={},
        drive=drive_regress.CLEANSE + ";200:sp=250;210:lua=apflag 152;220:act;290:down;300:ok;390:down;400:ok;480:ok;"
              "570:ok;650:ok;730:ok;820:esc;835:stats;840:quit",
        expect=["sp 250"], absent=["blessing_bought", "not supported: Blessing shop pacing"])),
    # blessing_items: the same purchase is the check and nothing else; the heal rate's bit (0 of flag 217) stays
    # unset, its effect being an item of the pool. (Not run yet: written without a CleriaCore build at hand.)
    "port_shop_blessing_items": (dict(blessing_items=True, blessing_costs={"5857332": 70}), dict(
        room="S_10/S_1009/S_1009", aplua={},
        drive=drive_regress.CLEANSE + ";200:sp=250;220:act;290:down;300:ok;390:down;400:ok;480:ok;570:ok;650:ok;"
              "730:ok;820:esc;835:stats;836:lua=apflag 217;840:quit",
        expect=[P + "blessing 0 bought for 70 SP: its effect is an item of the seed",
                "check 5857332 Divine Blessing: Increase stationary heal rate", P + "flag 0xD9 = 0"],
        absent=["not supported: Blessing items"])),
    # The "in logic" count from slot_data.logic: two checks made on entry (region 1), a blessing in region 1
    # that needs an item those checks send (SP: 50), and the statue in a region behind an item never received.
    "port_in_logic": (dict(logic=dict(regions=["Menu", "A", "B"],
                                      entrances=[[0, 1, True], [1, 2, ["has", "Nope", 1]]],
                                      locations={"5857429": [1, True], "5857558": [1, True], "5857587": [2, True],
                                                 "5857332": [1, ["all", ["reach", 1], ["has", "SP: 50", 2]]]})), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="300:lua=apstate;320:quit",
        expect=["checks 2 goal 0 active 1 deathlink 0 in logic 3 left 3"])),
    # A server that went back (restarted from an older save): it forgets the Roda Fruit, so its list is as long
    # as `applied` again once the next Panacea arrives. That Panacea is new to the save and is granted; the count
    # alone had skipped it. (Needs CleriaCore's mock server with !rollback.)
    "port_rollback": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:lua=apsay !give Celcetan Panacea;100:lua=apsay !give Roda Fruit;160:lua=apflag 0x59;"
              "200:lua=apsay !rollback 1;900:lua=apsay !give Celcetan Panacea;1000:lua=apflag 0x59;1010:lua=apstate;1020:quit",
        expect=[P + "flag 0x59 = 1", P + "connected as Yunica", "Celcetan Panacea: g_flags[0x59] 1 -> 2 (from Clicker)",
                P + "flag 0x59 = 2", "applied 4/4"])),
    "port_invariants": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:flag=99,3;70:flag=184,5;120:lua=apflag 99;130:lua=apflag 184;150:quit",
        expect=[P + "flag 0x63 = 1", P + "flag 0xB8 = 3"])),
}

exe = os.environ.get("CLERIA_EXE") or os.path.join(CC, "build_diff", "Release", "cleria-view.exe")
assets = os.environ.get("CLERIA_ASSETS") or os.path.join(CC, "assets")
_start = aplua_regress.start


def start(case, env, settings_dir):          # extra lines for the mod's settings section
    srv = _start(case, env, settings_dir)
    if case.get("ini_extra"):
        with open(os.path.join(settings_dir, "cleria.ini"), "a") as f:
            f.write(case["ini_extra"])
    return srv


aplua_regress.start = start
API4 = b"boss_defeated" in open(exe, "rb").read()      # an engine with mod API 4 (game.save, boss_defeated)
if not API4:
    for n in ("port_autosave", "port_autosave_level", "port_boss_event"):
        CASES.pop(n)
    print("mod API 3 engine: the API 4 cases are skipped")
if b"pickup_collected" not in open(exe, "rb").read():      # an engine with mod API 6 (cleria.combat)
    CASES.pop("port_exp_floor")
    print("no mod API 6: port_exp_floor is skipped")
names = sys.argv[1:] or list(CASES)
fails = 0
for n in names:
    patch, case = CASES[n]
    fixture(patch)
    r = drive_regress.run(n, case, exe, assets)
    if isinstance(r, tuple):                 # (passed, its report lines, seconds) since CleriaCore's --jobs
        for line in r[1]:
            print(line)
        r = r[0]
    fails += not r
print(f"{len(names) - fails}/{len(names)} passed")
sys.exit(1 if fails else 0)
