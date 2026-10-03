-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- tools/texture_scanner.lua - finds the road textures that are actually present in the running
-- game and classifies them.  Nothing is applied here, this module only *knows*.
--
-- Two sources of truth:
--   1. engineGetVisibleTextureNames() - every texture the renderer currently has loaded.  This is
--      what makes the resource work on a modded server: whatever the map really uses is found,
--      not just what the shipped database happens to list.
--   2. the streamed map objects - for each of them engineGetModelTextureNames() says which texture
--      belongs to which model, which is how the report can name the model behind a texture.
--
-- Classification tiers (see config/roads.lua):
--   apply     definitely a road surface (verified against the shipped San Andreas TXDs)
--   review    name is ambiguous ("BLOCK") - reported, applied only with /roadapply <name>
--   pattern   a road pattern matched - reported, applied only if SETTINGS.autoApplyPatterns
--   banned    must never be touched (a drain, a fence, a wall, ...)
--   unrelated everything else
-- -----------------------------------------------------------------------------
RR = RR or {}

RR.Scan = {
    found = {},                                    -- lower case name -> record
    order = {},                                    -- discovery order, for stable reports
    modelTex = {},                                 -- model id -> { texture, ... }
    texModel = {},                                 -- lower case name -> { model id, ... }
    timer = nil,
    objectsDone = 0,
    running = false,
    stats = { examined = 0, road = 0, banned = 0, unknown = 0, models = 0, patterns = 0 },
}

local S = RR.Scan

-- ---------------------------------------------------------------------------
-- classification
-- ---------------------------------------------------------------------------
local function hasReject(lower)
    for _, bad in ipairs(ROAD_PATTERN_REJECT) do
        if string.find(lower, bad, 1, true) then
            return bad
        end
    end
    return nil
end

--- Classify one texture name.  Pure function, no side effects.
-- @return cat, matKey, markKey, tier, why
function RR.Scan.classify(name)
    local lower = string.lower(name)
    if ROAD_BANNED[lower] then
        return 'banned', nil, nil, 'banned', 'blacklist'
    end
    local hit = ROAD_TEXTURES[lower]
    if hit then
        return hit.cat or 'road', hit.mat, hit.mark or nil, hit.tier, 'database'
    end
    for _, p in ipairs(ROAD_PATTERNS) do
        if string.find(lower, p[1]) then
            local bad = hasReject(lower)
            if bad then
                return 'rejected', nil, nil, 'banned', 'pattern "' .. p[1] .. '" but contains "' .. bad .. '"'
            end
            return 'pattern', p[2], p[3] or nil, 'pattern', 'pattern "' .. p[1] .. '"'
        end
    end
    return 'unrelated', nil, nil, 'unrelated', 'no road pattern'
end

-- ---------------------------------------------------------------------------
-- discovery
-- ---------------------------------------------------------------------------
--- Add texture names to the table of found textures.
-- @param names table (array) of texture names
-- @return number of NEW names
function RR.Scan.examine(names)
    local new = 0
    if type(names) ~= 'table' then
        return 0
    end
    for _, name in ipairs(names) do
        if type(name) == 'string' and name ~= '' then
            local lower = string.lower(name)
            if not S.found[lower] then
                local cat, mat, mark, tier, why = RR.Scan.classify(name)
                S.found[lower] = {
                    name = name, lower = lower, cat = cat, mat = mat, mark = mark,
                    tier = tier, why = why, applied = false, shader = nil, models = {},
                }
                S.order[#S.order + 1] = lower
                new = new + 1
                if tier == 'apply' or tier == 'review' or tier == 'pattern' then
                    S.stats.road = S.stats.road + 1
                    if tier == 'pattern' then
                        S.stats.patterns = S.stats.patterns + 1
                    end
                elseif tier == 'banned' then
                    S.stats.banned = S.stats.banned + 1
                else
                    S.stats.unknown = S.stats.unknown + 1
                end
            end
        end
    end
    S.stats.examined = S.stats.examined + new
    return new
end

--- One scan step: look at the visible textures and at a few streamed objects.
-- Bounded work so it can run every few seconds without costing a frame.
-- @param maxNames number of new texture names to accept this step
-- @return number of new names
function RR.Scan.step(maxNames)
    local new = 0
    local ok, names = pcall(engineGetVisibleTextureNames)
    if ok and type(names) == 'table' then
        -- engineGetVisibleTextureNames returns everything at once; only classify what is new and
        -- stop as soon as the budget for this step is used up
        for i = 1, #names do
            if new >= maxNames then
                break
            end
            local lower = string.lower(names[i])
            if not S.found[lower] then
                new = new + RR.Scan.examine({ names[i] })
            end
        end
    end
    -- model association, a few streamed objects per step
    local objs = getElementsByType('object')
    local budget = 40
    for i = S.objectsDone + 1, math.min(#objs, S.objectsDone + budget) do
        local el = objs[i]
        if isElement(el) then
            local id = getElementModel(el)
            if id and not S.modelTex[id] then
                local ok2, tl = pcall(engineGetModelTextureNames, id)
                if ok2 and type(tl) == 'table' then
                    S.modelTex[id] = tl
                    S.stats.models = S.stats.models + 1
                    for _, tn in ipairs(tl) do
                        local low = string.lower(tn)
                        S.texModel[low] = S.texModel[low] or {}
                        table.insert(S.texModel[low], id)
                        if S.found[low] then
                            S.found[low].models[#S.found[low].models + 1] = id
                        end
                    end
                end
            end
        end
    end
    S.objectsDone = math.min(#objs, S.objectsDone + budget)
    if S.objectsDone >= #objs then
        S.objectsDone = 0                                  -- wrap so newly streamed objects are seen
    end
    return new
end

--- Background scanning.  Runs until the resource stops; each pass costs one bounded step.
function RR.Scan.start()
    if S.running then
        return
    end
    S.running = true
    S.timer = setTimer(function()
        if not RR or not RR.Scan then
            return
        end
        local new = RR.Scan.step(SETTINGS.scanPerStep)
        if new > 0 and RR.Apply and RR.Apply.addFromScan then
            RR.Apply.addFromScan()
        end
    end, math.max(500, SETTINGS.scanInterval), 0)
end

function RR.Scan.stop()
    if S.timer and isTimer(S.timer) then
        killTimer(S.timer)
    end
    S.timer = nil
    S.running = false
end

--- Scan until nothing new shows up (used by /roadscan).  Bounded, so it always terminates.
-- @param maxSteps safety limit
-- @param perStep names per step
-- @return total number of new names
function RR.Scan.full(maxSteps, perStep)
    local total, steps = 0, 0
    repeat
        local new = RR.Scan.step(perStep or 400)
        total = total + new
        steps = steps + 1
    until new == 0 or steps >= (maxSteps or 40)
    return total, steps
end

--- Forget everything (used by /roadreload).
function RR.Scan.reset()
    RR.Scan.stop()
    S.found, S.order, S.modelTex, S.texModel = {}, {}, {}, {}
    S.objectsDone = 0
    S.stats = { examined = 0, road = 0, banned = 0, unknown = 0, models = 0, patterns = 0 }
end

-- ---------------------------------------------------------------------------
-- queries
-- ---------------------------------------------------------------------------
--- Every texture that should get a material, in discovery order.
-- @param includeReview boolean also return the ambiguous tier
-- @param includePattern boolean also return the pattern guesses
function RR.Scan.roadList(includeReview, includePattern)
    local out = {}
    for _, lower in ipairs(S.order) do
        local r = S.found[lower]
        if r.mat and (r.tier == 'apply' or (includeReview and r.tier == 'review')
                      or (includePattern and r.tier == 'pattern')) then
            out[#out + 1] = r
        end
    end
    return out
end

function RR.Scan.get(name)
    return S.found[string.lower(name or '')]
end

function RR.Scan.count()
    local n, road, applied = 0, 0, 0
    for _, r in pairs(S.found) do
        n = n + 1
        if r.mat and r.tier ~= 'banned' then
            road = road + 1
        end
        if r.applied then
            applied = applied + 1
        end
    end
    return n, road, applied
end

--- Names grouped by material, for /roadtextures and the report.
function RR.Scan.byMaterial()
    local groups = {}
    for _, r in pairs(S.found) do
        if r.mat then
            groups[r.mat] = groups[r.mat] or {}
            table.insert(groups[r.mat], r)
        end
    end
    return groups
end

function RR.Scan.modelsFor(name)
    local t = S.texModel[string.lower(name or '')]
    if not t then
        return ''
    end
    local seen, out = {}, {}
    for _, id in ipairs(t) do
        if not seen[id] then
            seen[id] = true
            out[#out + 1] = tostring(id)
        end
        if #out >= 8 then
            break
        end
    end
    return table.concat(out, ',')
end
