-- The statue shop's answers (ap/ys.lua Logic:shop_answer / on_blessing / the bit detection) against a fake game:
--     lua5.4 .dev/shop_test.lua            (from the mod's folder)
-- No CleriaCore needed: cleria.game / cleria.player are stubs over a flag table.
package.path = "./?.lua;" .. package.path

local flags = {}
local shop_api = true
cleria = {
    game = {flag = function(i) return flags[i] or 0 end, set_flag = function(i, v) flags[i] = v end,
            in_game = function() return true end, character = function() return 1 end, upgrade = function() return 0 end},
    player = {level = function() return 10 end, refresh = function() end},
}
local function with_shop(on) cleria.shop = on and {add_filter = function() end} or nil end

local ys = dofile("ap/ys.lua")

-- a few locations as data/ys_origin.json has them: blessings by bit of flag 217, one armor upgrade cell
local tbl = {loc = {}, locations = {}, scene_floors = {}, scene_names = {}}
local function loc(id, name, d)
    local l = {id = id, name = name, scene = 0, floor = "", detect = d.method, flag = d.flag or -1, index = d.index or -1,
               bit = d.bit or -1, detect_scene = 0, detect_floor = 0}
    tbl.loc[id] = l
    tbl.locations[#tbl.locations + 1] = l
end
local HEAL, TERRAIN, DROP, RESIST1, RESIST2, ARMOR = 5857332, 5857339, 5857330, 5857317, 5857318, 5857342
loc(HEAL, "Increase stationary heal rate", {method = "bit", flag = 217, bit = 0})        -- @Grow00
loc(TERRAIN, "Reduce damage from terrain", {method = "bit", flag = 217, bit = 1})        -- @Grow01
loc(DROP, "Increase item drop rate", {method = "bit", flag = 217, bit = 3})              -- @Grow03
loc(RESIST1, "Bolster bad status resists LV1", {method = "bit", flag = 217, bit = 9})    -- @Grow11
loc(RESIST2, "Bolster bad status resists LV2", {method = "bit", flag = 217, bit = 22})   -- @Grow24
loc(ARMOR, "Strengthen Battle Armor", {method = "item_arr", index = 10})                -- @GrowAr

local fails, n = 0, 0
local function check(ok, what)
    n = n + 1
    if not ok then fails = fails + 1 print("FAIL " .. what) end
end
local function eq(a, b, what)
    local function s(v)
        if type(v) ~= "table" then return tostring(v) end
        local t = {}
        for k, x in pairs(v) do t[#t + 1] = k .. "=" .. tostring(x) end
        table.sort(t)
        return "{" .. table.concat(t, ",") .. "}"
    end
    check(s(a) == s(b), what .. ": got " .. s(a) .. ", want " .. s(b))
end
local function logic(sd)
    flags = {}
    local L = ys.logic()
    L:configure(sd, tbl)
    return L
end
local function q(kind, index, value, extra)
    local t = {kind = kind, index = index, value = value, sub = 0, text = "", script = "@Grow"}
    for k, v in pairs(extra or {}) do t[k] = v end
    return t
end
local function label(s) return "Item " .. s.item end

-- ---- blessing_items ------------------------------------------------------------------------------------------
with_shop(true)
do
    local L = logic({blessing_items = true})
    check(L.opt.bless_by_purchase and #L.opt.unsupported == 0, "blessing_items is supported with the shop hooks")
    eq(L:shop_answer(q("owned", 0, 0)), {action = "replace", value = 0}, "owned: not bought yet")
    eq(L:shop_answer(q("buy", 0, 1000)), "suppress", "buy: the effect is not applied")
    local f = L:on_blessing(0)
    eq(f, {HEAL}, "the purchase is the check")
    eq(L:on_blessing(0), {}, "a second purchase sends nothing")
    eq(L:shop_answer(q("owned", 0, 0)), {action = "replace", value = 1}, "owned: bought, so the row is [Done]")
    -- the effect received (bit 1 set) does not detect the other slot's check, nor take it off sale
    flags[217] = 1 << 1
    eq(L:sweep(), {}, "a received effect bit is no check")
    eq(L:on_store(217, 0, 1 << 1), {}, "nor is its store")
    eq(L:shop_answer(q("owned", 1, 1)), {action = "replace", value = 0}, "owned: the effect alone keeps the slot on sale")
    -- tiers: LV2's row comes once LV1's location is checked
    eq(L:on_blessing(11), {RESIST1}, "@Grow11 is bit 9")
    eq(L:shop_answer(q("owned", 11, 0)), {action = "replace", value = 1}, "LV1 bought")
    eq(L:shop_answer(q("owned", 24, 0)), {action = "replace", value = 0}, "LV2 on sale")
    -- the gear rows are never ours
    flags[152] = 10
    eq(L:shop_answer(q("owned", 7, 0)), nil, "armor row: the game's own owned")
    eq(L:shop_answer(q("buy", 7, 300)), nil, "armor row: the upgrade is applied")
    eq(L:on_blessing(7), {}, "armor purchase: its cell detects it")
    -- a blessing that is no location of the slot keeps the game's rules
    eq(L:shop_answer(q("buy", 9, 100)), nil, "buy: not a location")
end
do   -- blessing_items off: the game's own owned / buy, the bit detects the check as before
    local L = logic({})
    eq(L:shop_answer(q("owned", 0, 0)), nil, "owned: the game's")
    eq(L:shop_answer(q("buy", 0, 1000)), nil, "buy: the vanilla effect")
    flags[217] = 1
    eq(L:sweep(), {HEAL}, "the bit is the check")
    eq(L:on_blessing(0), {}, "and the purchase event adds nothing")
end
with_shop(false)
do
    local L = logic({blessing_items = true})
    check(not L.opt.bless_by_purchase and #L.opt.unsupported == 1, "no shop hooks: blessing_items unsupported")
    flags[217] = 1
    eq(L:sweep(), {HEAL}, "no shop hooks: the bit still detects")
end
with_shop(true)

-- ---- prices --------------------------------------------------------------------------------------------------
do
    local L = logic({blessing_costs = {[tostring(HEAL)] = 70}, blessing_vanilla_price_map = {["1000"] = 70, ["24000"] = 90}})
    eq(L:shop_answer(q("price", 0, 1000, {sub = 0x61})), {action = "replace", value = 70}, "price by location")
    eq(L:shop_answer(q("price", 3, 24000, {sub = 0x69})), {action = "replace", value = 90}, "price by the vanilla map")
    eq(L:shop_answer(q("price", 9, 24000, {sub = 0x69})), {action = "replace", value = 90}, "not a location: the vanilla map")
    eq(L:shop_answer(q("price", 7, 1000, {sub = 0xb0})), nil, "the armor ladder keeps its price")
    eq(L:shop_answer(q("row", 0, 70, {text = "Increase stationary heal rate - [SP:]70"}), {}),
       {action = "replace", text = "Increase stationary heal rate - [SP:]70"}, "row without hints")
    eq(L:shop_answer(q("row", 0, 70), {[HEAL] = {item = 5, player = 1, flags = 0}}, label),
       {action = "replace", text = "Item 5 - [SP:]70"}, "row with the hint")
    eq(L:shop_answer(q("row", 0, -1), {[HEAL] = {item = 5, player = 1, flags = 0}}, label), nil, "a [Done] row")
end
do   -- hints with vanilla prices name the item too [MOD ap_menu_row]
    local L = logic({})
    eq(L:shop_answer(q("row", 0, 1000), {[HEAL] = {item = 5, player = 1, flags = 0}}, label),
       {action = "replace", text = "Item 5 - [SP:]1000"}, "vanilla prices, hint")
    local L2 = logic({shop_hints = false})
    eq(L2:shop_answer(q("row", 0, 1000), {[HEAL] = {item = 5, player = 1, flags = 0}}, label), nil, "hints off")
end

-- ---- one_per_floor -------------------------------------------------------------------------------------------
do
    local L = logic({blessing_costs = {[tostring(HEAL)] = 70, [tostring(TERRAIN)] = 60, [tostring(DROP)] = 80},
                     blessing_shop_unlock = 1})
    L.st.floors[1] = true
    eq(L:shop_answer(q("price", 1, 3000)), {action = "replace", value = 60}, "the cheapest is on sale")
    eq(L:shop_answer(q("price", 0, 1000)), {action = "replace", value = 1000000}, "the second is locked")
    eq(L:shop_answer(q("row", 3, 80)), {action = "replace", text = "Locked: visit 2 more floors"}, "the third: 2 floors")
    eq(L:shop_answer(q("row", 0, 70), {[HEAL] = {item = 5, player = 1, flags = 1}}, label),
       {action = "replace", text = "Item 5 - [SP:]70"}, "progression is never held back")
    L.st.floors[2] = true
    eq(L:shop_answer(q("price", 0, 1000)), {action = "replace", value = 70}, "a second floor: on sale")
    eq(L:shop_answer(q("row", 3, 80)), {action = "replace", text = "Locked: visit 1 more floor"}, "the third: 1 floor")
end

print(string.format("%d/%d passed", n - fails, n))
os.exit(fails == 0 and 0 or 1)
