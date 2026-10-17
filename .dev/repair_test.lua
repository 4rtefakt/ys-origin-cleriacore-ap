-- The two play-order repairs (ap/ys.lua Logic:annex / barrier_3f) against a fake game:
--     lua5.4 .dev/repair_test.lua          (from the mod's folder)
-- No CleriaCore needed: cleria.game / cleria.player are stubs over a flag table and an accessory slot.
package.path = "./?.lua;" .. package.path

local flags, acc = {}, -1
cleria = {
    game = {flag = function(i) return flags[i] or 0 end, set_flag = function(i, v) flags[i] = v end,
            in_game = function() return true end},
    json = {array = function(t) return t end},
    player = {hp = function() return 10 end,
              equipment = function() return {accessory = acc} end,
              equip = function(slot, item)
                  if slot ~= "accessory" then return false end
                  if item == nil then acc = -1 return true end
                  if (flags[item] or 0) < 1 then return false end
                  acc = item
                  return true
              end},
}

local ys = dofile("ap/ys.lua")

local fails, n = 0, 0
local function check(ok, what)
    n = n + 1
    if not ok then fails = fails + 1 print("FAIL " .. what) end
end
local function fresh(char, set)
    flags, acc = {[150] = char}, -1
    for k, v in pairs(set or {}) do flags[k] = v end
    return ys.logic()
end
local function f(i) return flags[i] or 0 end

-- Rado's Annex: each character's flag held at 0 on the bridge and in the annex, put back outside.
for _, c in ipairs({{1, 225, "Yunica"}, {2, 272, "Hugo"}, {3, 289, "Toal"}}) do
    local ch, flag, name = c[1], c[2], c[3]
    local L = fresh(ch, {[flag] = 1})
    check(L:repair(4019, 0) == nil and f(flag) == 1, name .. ": nothing outside the annex")
    local s = L:repair(4014, 0)
    check(s and s:find(name .. "'s story flag " .. flag .. " held at 0", 1, true) and f(flag) == 0, name .. ": held in S_4014")
    check(L:repair(4104, 0) == nil and f(flag) == 0, name .. ": still held on the bridge")
    check(L:repair(4017, 0) == nil and f(flag) == 0, name .. ": still held in S_4017")
    local st = ys.state_from_table(ys.state_to_table((function() L.st.seed = "X" return L.st end)()))
    check(st.held[flag] == true, name .. ": the hold survives the save block")
    s = L:repair(4019, 0)
    check(s and s:find("put back", 1, true) and f(flag) == 1, name .. ": put back outside")
end
-- a flag never set is not touched (Yunica before Zava)
do
    local L = fresh(1)
    check(L:repair(4104, 0) == nil and f(225) == 0 and not L.st.held[225], "Yunica: 225 unset stays unset")
    check(L:repair(4019, 0) == nil and f(225) == 0, "Yunica: nothing put back that was not held")
end

-- The 3F barrier: Yunica / Hugo with the Blue Necklace on before S_1009 was entered.
for _, ch in ipairs({1, 2}) do
    local L = fresh(ch, {[0x37] = 1})
    acc = 0x37
    local s = L:repair(1013, 0)
    check(s and s:find("taken off", 1, true) and acc == -1 and L.st.necklace, ch .. ": the necklace comes off in S_1013")
    check(L:repair(1013, 0) == nil and acc == -1, ch .. ": once")
    check(ys.state_from_table(ys.state_to_table((function() L.st.seed = "X" return L.st end)())).necklace == true,
          ch .. ": the debt survives the save block")
    flags[310] = 1                               -- the teleport: S_1009's root
    s = L:repair(1009, 0)
    check(s and s:find("put back on", 1, true) and acc == 0x37 and not L.st.necklace, ch .. ": back on in S_1009")
    check(L:repair(1013, 0) == nil and acc == 0x37, ch .. ": after the teleport the necklace stays on in S_1013")
end
do   -- after 310, or with the barrier already broken, nothing is done
    local L = fresh(1, {[0x37] = 1, [310] = 1})
    acc = 0x37
    check(L:repair(1013, 0) == nil and acc == 0x37, "Yunica: 310 set: left on")
    L = fresh(1, {[0x37] = 1, [444] = 1})
    acc = 0x37
    check(L:repair(1013, 0) == nil and acc == 0x37, "Yunica: barrier already broken: left on")
end
do   -- another accessory put on meanwhile: the necklace is not forced back
    local L = fresh(1, {[0x37] = 1, [0x3a] = 1})
    acc = 0x37
    L:repair(1013, 0)
    acc = 0x3a
    local s = L:repair(1005, 0)
    check(s and s:find("left off", 1, true) and acc == 0x3a and not L.st.necklace, "Yunica: another accessory kept")
end
do   -- Toal: his boost flag dropped in S_1013 until the teleport
    local L = fresh(3, {[141] = 1})
    local s = L:repair(1013, 0)
    check(s and s:find("boost", 1, true) and f(141) == 0, "Toal: boost dropped in S_1013")
    flags[141], flags[310] = 1, 1
    check(L:repair(1013, 0) == nil and f(141) == 1, "Toal: after the teleport the boost passes")
end
do   -- a save that broke the barrier before the teleport: 444 put back next to S_1013, for every character
    for _, ch in ipairs({1, 2, 3}) do
        for _, room in ipairs({1005, 1010}) do
            local L = fresh(ch, {[444] = 1})
            local s = L:repair(room, 0)
            check(s and s:find("put back (444 = 0)", 1, true) and f(444) == 0, ch .. ": 444 cleared in S_" .. room)
        end
        local L = fresh(ch, {[444] = 1, [310] = 1})
        check(L:repair(1005, 0) == nil and f(444) == 1, ch .. ": broken after the teleport: left broken")
        L = fresh(ch, {[444] = 1})
        check(L:repair(1004, 0) == nil and f(444) == 1, ch .. ": only next to S_1013")
    end
end
do   -- an engine without player.equip: nothing happens
    local eq = cleria.player.equip
    cleria.player.equip = nil
    local L = fresh(1, {[0x37] = 1})
    acc = 0x37
    check(L:repair(1013, 0) == nil and acc == 0x37, "no player.equip: nothing")
    cleria.player.equip = eq
end

print(string.format("%d/%d passed", n - fails, n))
os.exit(fails == 0 and 0 or 1)
