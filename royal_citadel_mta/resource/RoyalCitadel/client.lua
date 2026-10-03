-- Royal Citadel | client-side modular RenderWare scene for MTA:SA 1.6+
-- Each player loads the same asset set and creates a local, static scene. No edits
-- to the original MTA world or to the user's map resource are made.

local modelIDs = {}
local liveObjects = {}
local liveLights = {}
local requestedIDs = {}
local loadedData = {}
local sceneReady = false
local sceneVisible = false
local buildFailed = false
local txdElement

local function log(message, r, g, b)
    outputChatBox("#D7B56D[Royal Citadel] #FFFFFF" .. tostring(message), r or 232, g or 222, b or 205, true)
end

local function releaseRequested()
    for i = #requestedIDs, 1, -1 do
        local id = requestedIDs[i]
        if type(engineRestoreCOL) == "function" then pcall(engineRestoreCOL, id) end
        if type(engineRestoreModel) == "function" then pcall(engineRestoreModel, id) end
        if type(engineFreeModel) == "function" then pcall(engineFreeModel, id) end
    end
    requestedIDs = {}
    modelIDs = {}
    for i = #loadedData, 1, -1 do
        if isElement(loadedData[i]) then destroyElement(loadedData[i]) end
    end
    loadedData = {}
    if isElement(txdElement) then destroyElement(txdElement) end
    txdElement = nil
    sceneReady = false
end

local function allocateModel()
    if type(engineRequestModel) ~= "function" then
        return false, "engineRequestModel is unavailable; MTA 1.6+ is required"
    end
    local id = engineRequestModel("object", 1337)
    if not id then id = engineRequestModel("object") end
    if not id then return false, "MTA could not allocate another custom object model ID" end
    requestedIDs[#requestedIDs + 1] = id
    return id
end

local function loadModel(def)
    local highID, err = allocateModel()
    if not highID then return false, err end
    local lowID
    lowID, err = allocateModel()
    if not lowID then return false, err end

    -- MTA's custom-model path is loaded in COL -> TXD -> DFF order.
    if def.col and def.col ~= false then
        local col = engineLoadCOL(def.col)
        if not col then return false, "engineLoadCOL failed: " .. def.col end
        if not engineReplaceCOL(col, highID) then
            destroyElement(col)
            return false, "engineReplaceCOL failed: " .. def.col
        end
        loadedData[#loadedData + 1] = col
    end
    if not txdElement then
        txdElement = engineLoadTXD("files/royal_citadel.txd", false)
        if not txdElement then return false, "Could not load files/royal_citadel.txd" end
    end
    if not engineImportTXD(txdElement, highID) or not engineImportTXD(txdElement, lowID) then
        return false, "engineImportTXD failed for " .. def.name
    end
    local highDFF = engineLoadDFF(def.dff, highID)
    if not highDFF then return false, "engineLoadDFF failed: " .. def.dff end
    if not engineReplaceModel(highDFF, highID, true) then
        destroyElement(highDFF)
        return false, "engineReplaceModel failed: " .. def.dff
    end
    loadedData[#loadedData + 1] = highDFF

    local lowDFF = engineLoadDFF(def.lod, lowID)
    if not lowDFF then return false, "engineLoadDFF failed: " .. def.lod end
    if not engineReplaceModel(lowDFF, lowID, true) then
        destroyElement(lowDFF)
        return false, "engineReplaceModel failed: " .. def.lod
    end
    loadedData[#loadedData + 1] = lowDFF

    if type(engineSetModelLODDistance) == "function" then
        engineSetModelLODDistance(highID, math.min(450, def.lodDistance))
        engineSetModelLODDistance(lowID, def.lodDistance)
    end
    modelIDs[def.name] = { high = highID, low = lowID, collision = def.collision }
    return true
end

local function loadAssets()
    if sceneReady then return true end
    if type(engineLoadTXD) ~= "function" or type(engineLoadCOL) ~= "function" then
        log("This resource needs MTA:SA 1.6+ custom-model support.", 255, 80, 80)
        return false
    end
    for _, def in ipairs(RC_MODEL_DEFS) do
        local ok, err = loadModel(def)
        if not ok then
            buildFailed = true
            releaseRequested()
            log("Asset load stopped: " .. tostring(err), 255, 80, 80)
            return false
        end
    end
    sceneReady = true
    log(string.format("Loaded %d modular model pairs. Use /royalcastle to visit, /royalhide to hide the scene.", #RC_MODEL_DEFS))
    return true
end

local function setStatic(obj, collisions)
    if not isElement(obj) then return end
    if type(setElementFrozen) == "function" then setElementFrozen(obj, true) end
    if type(setObjectBreakable) == "function" then setObjectBreakable(obj, false) end
    if type(setElementCollisionsEnabled) == "function" then setElementCollisionsEnabled(obj, collisions == true) end
    if type(setElementInterior) == "function" then setElementInterior(obj, 0) end
    if type(setElementDimension) == "function" then setElementDimension(obj, 0) end
end

local function destroyScene()
    for i = #liveObjects, 1, -1 do
        if isElement(liveObjects[i]) then destroyElement(liveObjects[i]) end
    end
    for i = #liveLights, 1, -1 do
        if isElement(liveLights[i]) then destroyElement(liveLights[i]) end
    end
    liveObjects, liveLights = {}, {}
    sceneVisible = false
end

local function createScene()
    if sceneVisible then return true end
    if not sceneReady and not loadAssets() then return false end
    local created, failed = 0, 0
    for _, item in ipairs(RC_OBJECTS) do
        local ids = modelIDs[item.model]
        if ids then
            local x, y, z = RC_WORLD.x + item.x, RC_WORLD.y + item.y, RC_WORLD.z + item.z
            local hi = createObject(ids.high, x, y, z, 0, 0, item.rz, false)
            if hi then
                setStatic(hi, ids.collision)
                if math.abs((item.scale or 1) - 1) > 0.001 and type(setObjectScale) == "function" then
                    setObjectScale(hi, item.scale)
                end
                liveObjects[#liveObjects + 1] = hi
                created = created + 1
                local lo = createObject(ids.low, x, y, z, 0, 0, item.rz, true)
                if lo then
                    setStatic(lo, false)
                    if math.abs((item.scale or 1) - 1) > 0.001 and type(setObjectScale) == "function" then
                        setObjectScale(lo, item.scale)
                    end
                    if type(setLowLODElement) == "function" then
                        setLowLODElement(hi, lo)
                        if type(setElementParent) == "function" then setElementParent(lo, hi) end
                    else
                        -- Older builds still show the high asset; keep the fallback LOD hidden.
                        if type(setElementAlpha) == "function" then setElementAlpha(lo, 0) end
                    end
                    liveObjects[#liveObjects + 1] = lo
                end
            else
                failed = failed + 1
                outputDebugString("[Royal Citadel] createObject failed for " .. tostring(item.model), 2)
            end
        else
            failed = failed + 1
        end
    end
    -- Warm coronas supplement the emissive-looking window/lantern geometry without
    -- creating a costly dynamic light for every decorative fixture.
    for _, light in ipairs(RC_LIGHTS) do
        local marker = createMarker(RC_WORLD.x + light.x, RC_WORLD.y + light.y, RC_WORLD.z + light.z,
                                   "corona", light.size, light.r, light.g, light.b, 135)
        if marker then
            if type(setElementDimension) == "function" then setElementDimension(marker, 0) end
            if type(setElementInterior) == "function" then setElementInterior(marker, 0) end
            liveLights[#liveLights + 1] = marker
        end
    end
    sceneVisible = true
    log(string.format("Scene visible: %d placements, %d creation errors, %d warm lantern coronas.",
                      created, failed, #liveLights), failed > 0 and 255 or 232, failed > 0 and 170 or 222, failed > 0 and 90 or 205)
    return failed == 0
end

addEventHandler("onClientResourceStart", resourceRoot, function()
    setTimer(function()
        if loadAssets() then createScene() end
    end, 1000, 1)
end)

addCommandHandler("royalshow", function()
    createScene()
end)

addCommandHandler("royalhide", function()
    destroyScene()
    log("Local scene hidden. Use /royalshow to restore it.")
end)

addCommandHandler("royalinfo", function()
    log(string.format("%s | %d object placements | AI albedo TXD | modular COL3 + paired LOD.",
                      sceneVisible and "visible" or "hidden", #RC_OBJECTS))
end)

addEventHandler("onClientResourceStop", resourceRoot, function()
    destroyScene()
    releaseRequested()
end)
