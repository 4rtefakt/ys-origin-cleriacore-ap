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


CASES = {
    # Roda Fruit derived from roo_flags: 2 received -> 2; the first Roo fed -> 1; a Roo beyond the count
    # fed (flag 414, the 5th) costs nothing: the script's -1 is refunded.
    "port_roda": (dict(roo_flags=[312, 339, 362, 388, 414, 458]), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:lua=apsay !give Roda Fruit;100:lua=apsay !give Roda Fruit;160:lua=apflag 0x57;"
              "170:flag=312,1;200:lua=apflag 0x57;210:flag=87,0;215:flag=414,1;240:lua=apflag 0x57;260:quit",
        expect=["Roda Fruit: Roda Fruit #1", "Roda Fruit: Roda Fruit #2", P + "flag 0x57 = 2",
                P + "flag 0x57 = 1", P + "flag 0x57 = 1"])),
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
    # Mod API 4. Autosave: a chest check, then the save to the book's No.08 (file 7) at the next safe tick.
    "port_autosave": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive=aplua_regress.CHEST + ";740:ok;1000:lua=apstate;1020:quit",
        expect=[P + "check 5857605 Wailing Blue: 2F Path 1 (store)", "sidecar yso_07.cleria written",
                P + "autosave: wrote No.08"])),
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
    # The "in logic" count from slot_data.logic: two checks made on entry (region 1), a blessing in region 1
    # that needs an item those checks send (SP: 50), and the statue in a region behind an item never received.
    "port_in_logic": (dict(logic=dict(regions=["Menu", "A", "B"],
                                      entrances=[[0, 1, True], [1, 2, ["has", "Nope", 1]]],
                                      locations={"5857429": [1, True], "5857558": [1, True], "5857587": [2, True],
                                                 "5857332": [1, ["all", ["reach", 1], ["has", "SP: 50", 2]]]})), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="300:lua=apstate;320:quit",
        expect=["checks 2 goal 0 active 1 deathlink 0 in logic 3 left 3"])),
    "port_invariants": (dict(), dict(
        room="S_10/S_1001/S_1001", aplua={},
        drive="60:flag=99,3;70:flag=184,5;120:lua=apflag 99;130:lua=apflag 184;150:quit",
        expect=[P + "flag 0x63 = 1", P + "flag 0xB8 = 3"])),
}

exe = os.environ.get("CLERIA_EXE") or os.path.join(CC, "build_diff", "Release", "cleria-view.exe")
assets = os.path.join(CC, "assets")
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
    for n in ("port_autosave", "port_boss_event"):
        CASES.pop(n)
    print("mod API 3 engine: the API 4 cases are skipped")
names = sys.argv[1:] or list(CASES)
fails = 0
for n in names:
    patch, case = CASES[n]
    fixture(patch)
    fails += not drive_regress.run(n, case, exe, assets)
print(f"{len(names) - fails}/{len(names)} passed")
sys.exit(1 if fails else 0)
