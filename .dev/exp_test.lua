-- The EXP multipliers (ap/ys.lua Logic:exp_factor) with and without the player's base / catch-up overrides:
--     lua5.4 .dev/exp_test.lua            (from the mod's folder)
package.path = "./?.lua;" .. package.path
cleria = {game = {flag = function() return 0 end}, player = {}}
local ys = dofile("ap/ys.lua")
local L = ys.logic()
L.opt.level_scaling, L.opt.exp_base_mult, L.opt.exp_catchup_mult, L.opt.exp_catchup_margin = 2, 3, 5, 5
L.expected_hi = 20
local function eq(a,b,w) if a ~= b then print("FAIL "..w, a, b) os.exit(1) end end
eq(L:exp_factor(10), 5, "catch-up seed"); eq(L:exp_factor(30), 3, "base seed")
eq(L:exp_factor(10, 7, 9), 9, "catch-up override"); eq(L:exp_factor(30, 7, 9), 7, "base override")
eq(L:exp_factor(30, 0, 0), 3, "0 keeps seed")
L.opt.level_scaling = 1; eq(L:exp_factor(30, 7, 9), 1, "no exp scaling")
print("exp ok")
