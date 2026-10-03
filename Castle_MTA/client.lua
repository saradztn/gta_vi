-- Castle MTA | client-side custom object resource
-- No GTA model IDs are replaced: dynamic object model IDs are requested with MTA's
-- engineRequestModel, then paired with the generated RenderWare DFF/TXD/COL files.
-- Edit CASTLE_ORIGIN below to move the complete, planned site on your map.
local CASTLE_ORIGIN = { x = -3525.46460, y = -162.18356, z = 46.86824, rz = 0.0 } -- requested site
local CFG = {
    dimension = 0,
    interior = 0,
    highNear = 250.0,
    highFar = 340.0,
    lodNear = 250.0,
    lodFar = 1550.0,
    interiorRadius = 235.0,
    lightRadius = 240.0,
    glowRadius = 650.0,
    maxPedLights = 18,
    maxGlowCards = 48,
    syncMs = 600,
    loadStep = 3,
}

local S = {
    ready = false,
    failed = false,
    hidden = false,
    loading = false,
    ids = {},
    dffs = {},
    cols = {},
    txd = nil,
    objects = {},
    lightElements = {},
    visibleLights = {},
    glowTexture = nil,
    timers = {},
    generation = 0,
    alpha = {},
}
local syncCastle

local function debugMessage(message, level)
    outputDebugString("[Castle_MTA] " .. tostring(message), level or 3)
end

local function say(message, r, g, b)
    outputChatBox("#D6B36A[Castle] #FFFFFF" .. tostring(message), r or 255, g or 255, b or 255, true)
end

local function transform(x, y, z, rotation)
    local a = math.rad(CASTLE_ORIGIN.rz or 0)
    local c, s = math.cos(a), math.sin(a)
    local wx = CASTLE_ORIGIN.x + x * c - y * s
    local wy = CASTLE_ORIGIN.y + x * s + y * c
    local wz = CASTLE_ORIGIN.z + z
    return wx, wy, wz, (rotation or 0) + (CASTLE_ORIGIN.rz or 0)
end

local function distance2D(x1, y1, x2, y2)
    local dx, dy = x1 - x2, y1 - y2
    return math.sqrt(dx * dx + dy * dy)
end

local function nightFactor()
    local h, minute = getTime()
    h, minute = tonumber(h) or 12, tonumber(minute) or 0
    local t = h + minute / 60
    -- Day: 06:00-18:00. A brief half-hour twilight softens dawn and sunset.
    if t < 5.5 or t >= 18.5 then return 1 end
    if t >= 5.5 and t < 6.0 then return 1 - (t - 5.5) / 0.5 end
    if t >= 18.0 and t < 18.5 then return (t - 18.0) / 0.5 end
    return 0
end

local function setAlphaIfChanged(element, alpha)
    if not isElement(element) then return end
    alpha = math.max(0, math.min(255, math.floor(alpha + 0.5)))
    if S.alpha[element] ~= alpha then
        setElementAlpha(element, alpha)
        S.alpha[element] = alpha
    end
end

local function freeResources()
    if isTimer(S.syncTimer) then killTimer(S.syncTimer) end
    S.syncTimer = nil
    for _, timer in ipairs(S.timers) do
        if isTimer(timer) then killTimer(timer) end
    end
    S.timers = {}
    for _, light in pairs(S.lightElements) do
        if isElement(light) then destroyElement(light) end
    end
    S.lightElements = {}
    for _, list in pairs(S.objects) do
        for _, object in ipairs(list) do
            if isElement(object) then destroyElement(object) end
        end
    end
    S.objects = {}
    if isElement(S.glowTexture) then destroyElement(S.glowTexture) end
    S.glowTexture = nil
    for _, element in pairs(S.dffs) do
        if isElement(element) then destroyElement(element) end
    end
    for _, element in pairs(S.cols) do
        if isElement(element) then destroyElement(element) end
    end
    if isElement(S.txd) then destroyElement(S.txd) end
    S.txd = nil
    for _, id in pairs(S.ids) do
        if id then
            pcall(engineFreeModel, id)
        end
    end
    S.ids, S.dffs, S.cols = {}, {}, {}
    S.alpha = {}
    S.ready, S.loading = false, false
end

local function loadAsset(def)
    local id = engineRequestModel("object")
    if not id then
        debugMessage("engineRequestModel failed for " .. def.name, 1)
        return false
    end
    S.ids[def.name] = id

    -- MTA's loading order is COL, TXD, then DFF. Load the shared dictionary after
    -- the first COL so the first model follows that order as well.
    local col
    if def.col then
        col = engineLoadCOL("models/" .. def.name .. ".col")
        if not col then
            debugMessage("engineLoadCOL failed: " .. def.name .. ".col", 1)
            return false
        end
    end
    if not S.txd then
        S.txd = engineLoadTXD("models/castle.txd")
        if not S.txd then
            debugMessage("engineLoadTXD failed: models/castle.txd", 1)
            if isElement(col) then destroyElement(col) end
            return false
        end
    end
    local dff = engineLoadDFF("models/" .. def.name .. ".dff")
    if not dff then
        debugMessage("engineLoadDFF failed: " .. def.name .. ".dff", 1)
        if isElement(col) then destroyElement(col) end
        return false
    end

    if def.col then
        if not engineReplaceCOL(col, id) then
            debugMessage("engineReplaceCOL rejected " .. def.name, 1)
            destroyElement(col)
            destroyElement(dff)
            return false
        end
        S.cols[def.name] = col
    end
    if not engineImportTXD(S.txd, id) then
        debugMessage("engineImportTXD rejected " .. def.name, 1)
        destroyElement(dff)
        return false
    end
    if not engineReplaceModel(dff, id, false) then
        debugMessage("engineReplaceModel rejected " .. def.name, 1)
        destroyElement(dff)
        return false
    end
    S.dffs[def.name] = dff
    pcall(engineSetModelLODDistance, id, def.distance or 400, true)
    return true
end

local function makeObject(placement)
    local model = S.ids[placement.name]
    if not model then return nil end
    local x, y, z, rz = transform(placement.x, placement.y, placement.z, placement.rz)
    local object = createObject(model, x, y, z, 0, 0, rz, false)
    if not object then
        debugMessage("createObject failed for " .. placement.name, 2)
        return nil
    end
    setElementFrozen(object, true)
    setObjectBreakable(object, false)
    setElementDimension(object, CFG.dimension)
    setElementInterior(object, CFG.interior)
    local collision = false
    for _, def in ipairs(CASTLE_ASSETS) do
        if def.name == placement.name then
            collision = def.col
            break
        end
    end
    setElementCollisionsEnabled(object, collision)
    return object
end

local function buildObjects(token)
    local i = 0
    local function step()
        if token ~= S.generation or S.failed then return end
        local finish = math.min(i + 12, #CASTLE_PLACEMENTS)
        while i < finish do
            i = i + 1
            local p = CASTLE_PLACEMENTS[i]
            local object = makeObject(p)
            if object then
                S.objects[p.zone] = S.objects[p.zone] or {}
                S.objects[p.zone][#S.objects[p.zone] + 1] = object
            end
        end
        if i < #CASTLE_PLACEMENTS then
            local timer = setTimer(step, 35, 1)
            S.timers[#S.timers + 1] = timer
        else
            S.ready = true
            S.glowTexture = dxCreateTexture("textures/glow.png", "argb", true, "clamp")
            if not S.glowTexture then debugMessage("glow texture unavailable; emissive DFF lights still work", 2) end
            S.syncTimer = setTimer(syncCastle, CFG.syncMs, 0)
            syncCastle()
            say("مشروع القلعة جاهز. استخدم /castle للدخول من الجسر و /castleinside للقاعة الملكية.")
        end
    end
    step()
end

syncCastle = function()
    if not S.ready then return end
    local px, py = getElementPosition(localPlayer)
    local dist = distance2D(px, py, CASTLE_ORIGIN.x, CASTLE_ORIGIN.y)
    local highAlpha = 255
    if dist >= CFG.highFar then
        highAlpha = 0
    elseif dist > CFG.highNear then
        highAlpha = 255 * (CFG.highFar - dist) / (CFG.highFar - CFG.highNear)
    end
    local lodAlpha = 0
    if dist >= CFG.lodNear and dist < CFG.lodFar then
        lodAlpha = 255
        if dist < CFG.highFar then
            lodAlpha = 255 * (dist - CFG.lodNear) / math.max(1, CFG.highFar - CFG.lodNear)
        elseif dist > CFG.lodFar - 180 then
            lodAlpha = 255 * (CFG.lodFar - dist) / 180
        end
    end
    if S.hidden then highAlpha, lodAlpha = 0, 0 end

    for zone, objects in pairs(S.objects) do
        local alpha = highAlpha
        if zone == "lod" then alpha = lodAlpha end
        if zone == "interior" then
            alpha = (dist <= CFG.interiorRadius and not S.hidden) and 255 or 0
        elseif zone == "night" then
            -- The window/mantle emissive overlay remains available across the high-to-low hand-off.
            alpha = math.max(highAlpha, lodAlpha) * nightFactor()
            if S.hidden then alpha = 0 end
        end
        for _, object in ipairs(objects) do
            setAlphaIfChanged(object, alpha)
            if zone == "interior" then
                setElementCollisionsEnabled(object, alpha > 0)
            end
        end
    end

    -- Keep only the nearest small set of warm lights alive. MTA point lights illuminate peds/vehicles;
    -- the emissive glass mesh and DX glow cards provide the actual architectural night appearance.
    local factor = nightFactor()
    if S.hidden or factor < 0.05 or dist > CFG.lightRadius then
        for k, light in pairs(S.lightElements) do
            if isElement(light) then destroyElement(light) end
            S.lightElements[k] = nil
        end
        S.visibleLights = {}
        return
    end
    local ranked = {}
    for i, item in ipairs(CASTLE_LIGHTS) do
        local wx, wy, wz = transform(item[1], item[2], item[3], 0)
        local d = distance2D(wx, wy, px, py)
        if d < CFG.glowRadius then
            ranked[#ranked + 1] = { index = i, item = item, x = wx, y = wy, z = wz, d = d }
        end
    end
    table.sort(ranked, function(a, b) return a.d < b.d end)
    S.visibleLights = {}
    for n, lightData in ipairs(ranked) do
        if n <= CFG.maxGlowCards then S.visibleLights[#S.visibleLights + 1] = lightData end
        if n <= CFG.maxPedLights and lightData.d <= CFG.lightRadius then
            if not isElement(S.lightElements[lightData.index]) then
                local item = lightData.item
                local light = createLight(0, lightData.x, lightData.y, lightData.z, item[4], item[5], item[6], item[7])
                if light then S.lightElements[lightData.index] = light end
            end
        elseif isElement(S.lightElements[lightData.index]) then
            destroyElement(S.lightElements[lightData.index])
            S.lightElements[lightData.index] = nil
        end
    end
    for index, light in pairs(S.lightElements) do
        if not isElement(light) then S.lightElements[index] = nil end
    end
end

local function drawGlows()
    if not S.ready or S.hidden or not S.glowTexture then return end
    local factor = nightFactor()
    if factor <= 0.01 then return end
    local cameraX, cameraY, cameraZ = getCameraMatrix()
    for _, source in ipairs(S.visibleLights) do
        local item = source.item
        local size = math.max(0.9, math.min(2.4, item[4] * 0.16))
        local alpha = math.floor(150 * factor * math.max(0.25, 1.0 - source.d / CFG.glowRadius))
        local color = tocolor(item[5], item[6], item[7], alpha)
        dxDrawMaterialLine3D(source.x - size * 0.45, source.y, source.z,
            source.x + size * 0.45, source.y, source.z, false, S.glowTexture, size * 1.4,
            color, "postfx", cameraX, cameraY, cameraZ)
    end
end

local function showCastle()
    S.hidden = false
    syncCastle()
end

local function hideCastle()
    S.hidden = true
    syncCastle()
end

local function teleportTo(x, y, z)
    if not S.ready then
        say("القلعة ما زالت تُحمّل؛ حاول بعد لحظات.", 255, 190, 120)
        return
    end
    local wx, wy, wz = transform(x, y, z, 0)
    setElementPosition(localPlayer, wx, wy, wz)
    setElementVelocity(localPlayer, 0, 0, 0)
end

local function startLoading()
    if S.loading or S.ready then return end
    S.loading = true
    S.generation = S.generation + 1
    local token = S.generation
    local i, failures = 0, 0
    local function loadStep()
        if token ~= S.generation then return end
        local finish = math.min(i + CFG.loadStep, #CASTLE_ASSETS)
        while i < finish do
            i = i + 1
            if not loadAsset(CASTLE_ASSETS[i]) then failures = failures + 1 end
        end
        if i < #CASTLE_ASSETS then
            local timer = setTimer(loadStep, 40, 1)
            S.timers[#S.timers + 1] = timer
        elseif failures > 0 then
            S.failed = true
            S.loading = false
            debugMessage(tostring(failures) .. " model(s) failed; partial castle removed", 1)
            say("تعذر تحميل " .. failures .. " موديل. لن تُنشأ القلعة حتى لا تبقى Collision ناقصة.", 255, 100, 100)
            freeResources()
            S.failed = true
        else
            S.loading = false
            buildObjects(token)
        end
    end
    loadStep()
end

addEventHandler("onClientResourceStart", resourceRoot, startLoading)
addEventHandler("onClientRender", root, drawGlows)
addEventHandler("onClientResourceStop", resourceRoot, freeResources)

addCommandHandler("castle", function()
    showCastle()
    teleportTo(0, -162, 2.3)
end)
addCommandHandler("castleinside", function()
    showCastle()
    teleportTo(0, -8, 2.2)
end)
addCommandHandler("castlehide", hideCastle)
addCommandHandler("castleshow", showCastle)
addCommandHandler("castlewhere", function()
    say(string.format("Origin: %.1f, %.1f, %.1f | heading %.1f°", CASTLE_ORIGIN.x, CASTLE_ORIGIN.y, CASTLE_ORIGIN.z, CASTLE_ORIGIN.rz))
end)
