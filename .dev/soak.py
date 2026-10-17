"""Archipelago soak test: a real MultiServer on a generated seed, a scripted second player (Frisk, Undertale) and one long
CleriaCore boot of the Lua mod (Yunica), with server restarts, a host rollback, client reconnects, saves and loads,
deaths and DeathLinks along the way. At the end the mod's state is checked against the server's save.

    <AP venv python> soak.py --ap <Archipelago checkout> --seed <AP_x.zip> --spoiler <..._Spoiler.txt> --exe <cleria-view>
        --assets <dir> --mod <mod dir> [--minutes 60] [--port 38331] [--rollback] [--outage] [--reboot] [--out <dir>]

Linux (nice, venv/bin/python; SDL_VIDEODRIVER=offscreen). The seed: Frisk (Undertale) and Yunica (Ys Origin), as the
e2e seeds are. Run with Archipelago's own venv (websockets, and the .apsave reader). Exit 0 when every check holds.
A Roo fed by one of the drive's flag checks (roo_flags) takes one Roda Fruit off the count: that is by design.
"""
import argparse, asyncio, json, os, re, shutil, subprocess, sys, time, zlib

ap = argparse.ArgumentParser()
ap.add_argument("--seed", required=True)
ap.add_argument("--spoiler", required=True)
ap.add_argument("--exe", required=True)
ap.add_argument("--assets", required=True)
ap.add_argument("--mod", required=True)
ap.add_argument("--ap", required=True, help="an Archipelago checkout with its venv")
ap.add_argument("--minutes", type=float, default=60)
ap.add_argument("--port", type=int, default=38331)
ap.add_argument("--rollback", action="store_true", help="snapshot the server's save, later restart it from that snapshot")
ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "run"))
ap.add_argument("--nice", type=int, default=10)
ap.add_argument("--outage", action="store_true", help="the server down 90 s at 70%%, checks made meanwhile")
ap.add_argument("--reboot", action="store_true", help="the game quits at 50%% and a second boot loads its save")
a = ap.parse_args()

SLOT, SLOT_NO, MODID = "Yunica", 2, "ysorigin.archipelago"
OUT = os.path.abspath(a.out)
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
SEED = os.path.join(OUT, os.path.basename(a.seed))    # a fresh copy: no .apsave beside it, a new room
shutil.copy(a.seed, SEED)
APSAVE = SEED[:-4] + ".apsave"
T0 = time.time()
events = open(os.path.join(OUT, "events.log"), "w", encoding="utf-8", buffering=1)


def ev(*x):
    events.write("%7.1f %s\n" % (time.time() - T0, " ".join(str(v) for v in x)))


# ---- the server ----
env_ap = dict(os.environ, SKIP_REQUIREMENTS_UPDATE="1", PYTHONUNBUFFERED="1")
srvlog = open(os.path.join(OUT, "server.log"), "w", encoding="utf-8", buffering=1)
srv = None


def spawn():
    global srv
    srv = subprocess.Popen(["nice", "-n", str(a.nice), os.path.join(a.ap, "venv", "bin", "python"), "MultiServer.py", SEED,
                            "--port", str(a.port)],
                           cwd=a.ap, env=env_ap, stdin=subprocess.PIPE, stdout=srvlog, stderr=subprocess.STDOUT, text=True)
    ev("server up pid", srv.pid)


def server_say(line):
    if srv.poll() is not None:
        ev("server is down (exit %s): '%s' not sent" % (srv.returncode, line))
        return
    srv.stdin.write(line + "\n")
    srv.stdin.flush()


async def server_restart(restore=False, down=4):
    server_say("/save")
    await asyncio.sleep(2)
    srv.kill()
    srv.wait()
    if restore:
        shutil.copy(os.path.join(OUT, "snapshot.apsave"), APSAVE)
    ev("server", "restored from snapshot" if restore else "restarted", "after", down, "s down")
    await asyncio.sleep(down)
    spawn()


# ---- Frisk, the second player ----
import websockets   # noqa: E402  (Archipelago's venv)

bot = dict(ws=None, locs=[], next=0, received=0)


async def frisk():
    while True:
        try:
            async with websockets.connect("ws://127.0.0.1:%d" % a.port, max_size=None, ping_interval=None) as ws:
                await ws.send(json.dumps([{"cmd": "GetDataPackage", "games": ["Undertale"]}]))
                async for raw in ws:
                    for p in json.loads(raw):
                        c = p.get("cmd")
                        if c == "DataPackage":
                            ids = p["data"]["games"]["Undertale"]["location_name_to_id"]
                            await ws.send(json.dumps([{"cmd": "Connect", "game": "Undertale", "name": "Frisk", "password": "",
                                                       "uuid": "soakbot", "version": {"major": 0, "minor": 6, "build": 0,
                                                                                      "class": "Version"},
                                                       "items_handling": 7, "tags": ["DeathLink"], "slot_data": False}]))
                            bot["all"] = ids
                        elif c == "Connected":
                            mine = set(p["missing_locations"]) | set(p["checked_locations"])
                            bot["locs"] = sorted(mine)
                            bot["ws"] = ws
                            ev("frisk connected,", len(p["checked_locations"]), "of", len(mine), "checked")
                        elif c == "ReceivedItems":
                            bot["received"] = p["index"] + len(p["items"])
        except Exception as e:   # the server went down: try again
            bot["ws"] = None
            await asyncio.sleep(1.5)


async def frisk_check():
    if bot["ws"] and bot["next"] < len(bot["locs"]):
        loc = bot["locs"][bot["next"]]
        bot["next"] += 1
        try:
            await bot["ws"].send(json.dumps([{"cmd": "LocationChecks", "locations": [loc]}]))
            ev("frisk checks", loc)
        except Exception:
            bot["next"] -= 1


async def frisk_deathlink():
    if bot["ws"]:
        await bot["ws"].send(json.dumps([{"cmd": "Bounce", "tags": ["DeathLink"],
                                          "data": {"time": time.time(), "source": "Frisk", "cause": "soak"}}]))
        ev("frisk deathlink")


# ---- the game's drive: one long boot, real time (60 ticks a second) ----
tbl = json.load(open(os.path.join(a.mod, "data", "ys_origin.json"), encoding="utf-8"))
spoiled = set(re.findall(r"^(.+) \(%s\): " % SLOT, open(a.spoiler, encoding="utf-8").read(), re.M))
flag_locs = [l for l in tbl["locations"] if l["detect"].get("method") == "flag" and l["name"] in spoiled]
ev("Ys flag locations in this seed:", len(flag_locs))
S = lambda m: int(m * 60 * 60)              # minutes -> ticks
end = S(a.minutes)
steps = ["1:waitlog=hints:", "30:csave=1"]
for i, l in enumerate(flag_locs):           # a Ys check every ~minute (as if a chest were opened)
    t = S(0.5 + i * (a.minutes - 2) / max(1, len(flag_locs)))
    steps.append("%d:flag=%d,1" % (t, l["detect"]["flag"]))
for m in range(5, int(a.minutes) - 1, 5):   # a save every 5 minutes
    steps.append("%d:csave=2" % S(m))
for m in (a.minutes * 0.45, a.minutes * 0.8):   # back to an older save twice
    steps.append("%d:cload=1;%d:apstate" % (S(m), S(m) + 600))
for m, off in ((a.minutes * 0.2, 5), (a.minutes * 0.55, 60), (a.minutes * 0.87, 5)):   # the client drops, comes back
    steps.append("%d:lua=apdisconnect;%d:lua=apconnect" % (S(m), S(m) + off * 60))
for m in (a.minutes * 0.33,):                # a death in the game (a DeathLink sent), then Retry
    steps.append("%d:hp=0;%d:ok;%d:ok" % (S(m), S(m) + 200, S(m) + 260))
for m in range(1, int(a.minutes)):
    steps.append("%d:lua=apstate" % S(m))
steps += ["%d:lua=apflag 0x57" % (end - 300), "%d:lua=apflag 0x59" % (end - 290), "%d:lua=apstate" % (end - 200),
          "%d:quit" % end]
steps = [x.replace(":apstate", ":lua=apstate") for x in ";".join(steps).split(";")]
tick = lambda x: int(x.split(":", 1)[0])
if a.reboot:   # boot 1 saves and quits halfway; boot 2 loads that save and goes on
    cut = S(a.minutes * 0.5)
    drives = [[x for x in steps if tick(x) < cut - 120] + ["%d:csave=2" % (cut - 100), "%d:quit" % cut],
              ["1:waitlog=hints:", "300:cload=2"] + ["%d:%s" % (tick(x) - cut + 600, x.split(":", 1)[1])
                                                     for x in steps if tick(x) >= cut and not x.startswith("1:")]]
else:
    drives = [steps]
drives = [";".join(sorted(d, key=tick)) for d in drives]

game = os.path.join(OUT, "game")
mods = os.path.join(game, "mods")
os.makedirs(mods)
shutil.copytree(a.mod, os.path.join(mods, "archipelago_lua"), ignore=shutil.ignore_patterns(".git", ".dev", ".github"))
ini = os.path.join(game, "yso_win.ini")
open(ini, "w").close()
with open(os.path.join(game, "cleria.ini"), "w") as f:
    f.write('[cleria.mods]\nUseMods=1\nOrder="%s"\nActive="%s"\n\n' % (MODID, MODID))
    f.write('[cleria.mod.%s]\nServer="127.0.0.1:%d"\nSlot="%s"\nAutoConnect=1\nDeathLink=1\nUuid="soak"\n' % (MODID, a.port, SLOT))
genv = dict(os.environ, CLERIA_MUTE="1", CLERIA_CHAR="1", CLERIA_DRIVE_REALTIME="1", CLERIA_INI=ini,
            CLERIA_SAVE_DIR=os.path.join(game, "saves"), SDL_VIDEODRIVER=os.environ.get("SDL_VIDEODRIVER", "offscreen"))
os.makedirs(genv["CLERIA_SAVE_DIR"])


async def run_game():
    rc = 0
    for n, d in enumerate(drives):
        rc = rc or await boot(n, d)
    return rc


async def boot(n, d):
    out = open(os.path.join(OUT, "game.log"), "a", encoding="utf-8")
    out.write("==== boot %d\n" % (n + 1))
    out.flush()
    genv["CLERIA_DRIVE"] = d
    p = await asyncio.create_subprocess_exec("nice", "-n", str(a.nice), a.exe, a.assets,
                                             os.path.join(a.assets, "MAP", "S_10/S_1001/S_1001.SOB"),
                                             env=genv, cwd=game, stdout=out, stderr=subprocess.STDOUT)
    ev("game up pid", p.pid)
    await p.wait()
    ev("game exit", p.returncode)
    return p.returncode


async def timeline():
    m = a.minutes
    plan = [(m * 0.15, "restart"), (m * 0.6, "restart"), (m * 0.4, "deathlink"), (m * 0.75, "deathlink")]
    if a.rollback:
        plan += [(m * 0.25, "snapshot"), (m * 0.35, "restore")]
    if a.outage:
        plan += [(m * 0.7, "outage")]
    for t, what in sorted(plan):
        await asyncio.sleep(max(0, T0 + t * 60 - time.time()))
        if what == "restart":
            await server_restart()
        elif what == "snapshot":
            server_say("/save")
            await asyncio.sleep(2)
            shutil.copy(APSAVE, os.path.join(OUT, "snapshot.apsave"))
            ev("server snapshot taken")
        elif what == "restore":
            await server_restart(restore=True)
        elif what == "outage":
            await server_restart(down=90)
        elif what == "deathlink":
            await frisk_deathlink()


async def frisk_pace():
    n = max(1, len(bot["locs"]) or 100)
    while True:
        await asyncio.sleep(max(5.0, (a.minutes - 2) * 60 / n))
        await frisk_check()


async def main():
    spawn()
    await asyncio.sleep(6)
    tasks = [asyncio.create_task(x) for x in (frisk(), timeline(), frisk_pace())]
    rc = await run_game()
    for t in tasks:
        t.cancel()
    server_say("/save")
    await asyncio.sleep(3)
    srv.kill()
    return rc


rc = asyncio.run(main())

# ---- the checks ----
sys.path.insert(0, a.ap)
os.chdir(a.ap)
from Utils import restricted_loads   # noqa: E402
save = restricted_loads(zlib.decompress(open(APSAVE, "rb").read()))
recv = max((v for k, v in save["received_items"].items() if k[1] == SLOT_NO), key=len, default=[])
checked = save["location_checks"].get((0, SLOT_NO), set())
log = open(os.path.join(OUT, "game.log"), encoding="utf-8", errors="replace").read()
states = re.findall(r"state '[^']*' seed \S+ slot \d+ applied (\d+)/(\d+) checks (\d+)", log)
fails = []
if rc != 0:
    fails.append("the game exited with %s" % rc)
if not states:
    fails.append("no apstate line")
else:
    applied, known, checks = map(int, states[-1])
    if applied != known:
        fails.append("applied %d of the %d items the client knows" % (applied, known))
    if known != len(recv):
        fails.append("the client knows %d items, the server sent %d" % (known, len(recv)))
    if checks > len(checked):
        fails.append("the client holds %d checks, the server %d" % (checks, len(checked)))
    sent = [l for l in flag_locs if "check %d " % l["id"] in log]
    missing = [l["id"] for l in sent if l["id"] not in checked]
    if missing:
        fails.append("checks the server never got: %s" % missing)
for pat in ("attempt to", "script stopped", "Mod stopped", "stack traceback"):
    if pat in log:
        fails.append("'%s' in the game's log" % pat)
for f in re.findall(r"\[lua:%s\] flag 0x(57|59) = (-?\d+)" % MODID, log)[-2:]:
    ev("final flag 0x%s = %s" % f)
ev("server: %d items to %s, %d of its locations checked; frisk %d/%d checked" % (len(recv), SLOT, len(checked), bot["next"],
                                                                                  len(bot["locs"])))
for f in fails:
    ev("FAIL", f)
ev("PASS" if not fails else "FAILED")
print(open(os.path.join(OUT, "events.log")).read()[-3000:])
sys.exit(1 if fails else 0)
