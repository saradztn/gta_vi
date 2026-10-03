-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- client.lua - the orchestrator.  On resource start it
--     1. loads the shared texture set
--     2. compiles the shaders (each one independently, a failure never kills the rest)
--     3. discovers the road textures of the running map and applies a material to each of them
--     4. starts the reflection, the rain and the background scanner
--     5. prints an initialisation report
--
-- It never creates geometry, never spawns an object, never touches a collision and never moves a
-- road: only engineApplyShaderToWorldTexture() on materials that are already in the map.
--
-- Everything lives in the single global table RR so no two scripts can define the same global.
-- -----------------------------------------------------------------------------
RR = RR or {}

RR.VERSION = '1.0.0'
RR.Count = { materials = 0, markings = 0, shaders = 0, applied = 0, failed = 0, textures = 0 }
RR.State = {
    quality = 'high',
    fx = 2,                    -- 0 off, 1 materials, 2 +reflection, 3 +rain, 4 +grade
    wet = 0.0,
    puddle = 0.0,
    rain = 0.0,
    night = 0.0,
    reflection = 1.0,
    exposure = 1.0,
    debug = 0,
    started = false,
    forcedNight = nil,
    forcedPuddle = nil,
}

-- ---------------------------------------------------------------------------
-- tiny helpers
-- ---------------------------------------------------------------------------
local TAG = '#7ec8ff[RoadRealism]#ffffff '

function RR.Say(msg)
    outputChatBox(TAG .. tostring(msg), 255, 255, 255, true)
    if SETTINGS.debug or RR.State.debug > 0 then
        outputDebugString('[RoadRealism] ' .. tostring(msg))
    end
end

function RR.Warn(msg)
    outputChatBox('#ff9c5c[RoadRealism]#ffffff ' .. tostring(msg), 255, 255, 255, true)
    outputDebugString('[RoadRealism] WARNING: ' .. tostring(msg), 1)
end

function RR.Fail(msg)
    outputChatBox('#ff5c5c[RoadRealism]#ffffff ' .. tostring(msg), 255, 255, 255, true)
    outputDebugString('[RoadRealism] ERROR: ' .. tostring(msg), 1)
end

local function num(v, d)
    v = tonumber(v)
    if not v then
        return d
    end
    return v
end

local function countOf(t)
    local n = 0
    for _ in pairs(t) do
        n = n + 1
    end
    return n
end

for _ in pairs(ROAD_MATERIALS) do
    RR.Count.materials = RR.Count.materials + 1
end
for _ in pairs(ROAD_MARKINGS) do
    RR.Count.markings = RR.Count.markings + 1
end

-- ---------------------------------------------------------------------------
-- textures
-- ---------------------------------------------------------------------------
RR.Tex = { shared = {}, mats = {}, marks = {} }

function RR.Tex.loadShared()
    local n, bad = 0, {}
    for key, path in pairs(ROAD_SHARED) do
        local t = dxCreateTexture(path, key == 'puddle' and 'dxt5' or 'argb', true, 'wrap')
        if t then
            RR.Tex.shared[key] = t
            n = n + 1
        else
            bad[#bad + 1] = path
        end
    end
    if #bad > 0 then
        RR.Fail('shared textures missing: ' .. table.concat(bad, ', '))
    end
    RR.Count.textures = n
    return n, #bad
end

--- Material albedo / mask, created on first use and cached.
function RR.Tex.material(matKey)
    local c = RR.Tex.mats[matKey]
    if c ~= nil then
        return c
    end
    local m = ROAD_MATERIALS[matKey]
    if not m then
        RR.Tex.mats[matKey] = false
        return false
    end
    local a = dxCreateTexture(m.albedo, 'dxt1', true, 'wrap')
    local k = dxCreateTexture(m.mask, 'dxt5', true, 'wrap')
    if not (a and k) then
        if a and isElement(a) then
            destroyElement(a)
        end
        if k and isElement(k) then
            destroyElement(k)
        end
        RR.Warn('material ' .. matKey .. ' could not be loaded (' .. m.albedo .. ')')
        RR.Tex.mats[matKey] = false
        return false
    end
    RR.Tex.mats[matKey] = { albedo = a, mask = k }
    RR.Count.textures = RR.Count.textures + 2
    return RR.Tex.mats[matKey]
end

function RR.Tex.marking(markKey)
    if not markKey then
        return nil
    end
    local c = RR.Tex.marks[markKey]
    if c ~= nil then
        return c
    end
    local mk = ROAD_MARKINGS[markKey]
    if not mk then
        RR.Tex.marks[markKey] = false
        return false
    end
    local t = dxCreateTexture(mk.file, 'dxt5', true, 'wrap')
    if not t then
        RR.Warn('marking ' .. markKey .. ' could not be loaded (' .. mk.file .. ')')
        RR.Tex.marks[markKey] = false
        return false
    end
    RR.Tex.marks[markKey] = t
    RR.Count.textures = RR.Count.textures + 1
    return t
end

function RR.Tex.destroyAll()
    for _, v in pairs(RR.Tex.shared) do
        if isElement(v) then
            destroyElement(v)
        end
    end
    for _, v in pairs(RR.Tex.mats) do
        if v and isElement(v.albedo) then
            destroyElement(v.albedo)
        end
        if v and isElement(v.mask) then
            destroyElement(v.mask)
        end
    end
    for _, v in pairs(RR.Tex.marks) do
        if v and isElement(v) then
            destroyElement(v)
        end
    end
    -- clear the caches in place: replacing RR.Tex would drop its own methods
    for k in pairs(RR.Tex.shared) do
        RR.Tex.shared[k] = nil
    end
    for k in pairs(RR.Tex.mats) do
        RR.Tex.mats[k] = nil
    end
    for k in pairs(RR.Tex.marks) do
        RR.Tex.marks[k] = nil
    end
    RR.Count.textures = 0
end

-- ---------------------------------------------------------------------------
-- shaders
-- ---------------------------------------------------------------------------
RR.Shaders = { cache = {} }

--- Create (or reuse) a shader.  A compile failure is contained: it returns nil and the caller
-- carries on with the other effects, which is exactly the failsafe this resource promises.
function RR.Shaders.create(file)
    local c = RR.Shaders.cache[file]
    if c ~= nil then
        return c.shader, c.tech, c.err
    end
    if not ROAD_SHADER_UNIFORMS[file] then
        RR.Shaders.cache[file] = { shader = false, tech = nil, err = 'not declared in meta.xml' }
        return nil, nil, 'not declared in meta.xml'
    end
    local sh, tech = dxCreateShader(file, 0, 0, false, 'world')
    if not sh then
        RR.Shaders.cache[file] = { shader = false, tech = nil, err = tostring(tech) }
        RR.Count.failed = RR.Count.failed + 1
        RR.Fail('shader ' .. file .. ' did not compile: ' .. tostring(tech))
        return nil, nil, tostring(tech)
    end
    RR.Shaders.cache[file] = { shader = sh, tech = tech, err = nil }
    RR.Count.shaders = RR.Count.shaders + 1
    if tech and tech ~= 'tec0' then
        RR.Warn('shader ' .. file .. ' fell back to technique "' .. tostring(tech) .. '"')
    end
    return sh, tech
end

function RR.Shaders.destroy(file)
    local c = RR.Shaders.cache[file]
    if c and c.shader and isElement(c.shader) then
        destroyElement(c.shader)
    end
    RR.Shaders.cache[file] = nil
    RR.Count.shaders = 0
    for _, v in pairs(RR.Shaders.cache) do
        if v.shader then
            RR.Count.shaders = RR.Count.shaders + 1
        end
    end
end

function RR.Shaders.get(file)
    local c = RR.Shaders.cache[file]
    return c and c.shader or nil
end

function RR.Shaders.destroyAll()
    for file in pairs(RR.Shaders.cache) do
        RR.Shaders.destroy(file)
    end
    RR.Shaders.cache = {}
    RR.Count.shaders = 0
end

--- Set one uniform if this shader really declares it (a driver may optimise one away).
local function setV(shader, file, name, ...)
    local u = ROAD_SHADER_UNIFORMS[file]
    if not (u and u[name]) then
        return false
    end
    local ok = dxSetShaderValue(shader, name, ...)
    if not ok and RR.State.debug >= 3 then
        outputDebugString('[RoadRealism] dxSetShaderValue ' .. name .. ' on ' .. file .. ' failed', 3)
    end
    return ok and true or false
end

-- ---------------------------------------------------------------------------
-- shader parameters.  ROAD_SHADER_PACK (generated) says which named value goes into which
-- component of which packed float4, so the shader and the Lua can never drift apart.
-- ---------------------------------------------------------------------------
RR.Params = {}

--- Collect every named value for one material / marking combination.
function RR.Params.build(matKey, markKey)
    local m = ROAD_MATERIALS[matKey]
    if not m then
        return nil
    end
    local mk = markKey and ROAD_MARKINGS[markKey] or nil
    local st = RR.State
    local q = ROAD_QUALITY[st.quality] or ROAD_QUALITY.high
    local fogEnd = 300
    local ok, fd = pcall(getFogDistance)
    if ok and fd and fd > 1 then
        fogEnd = fd
    end
    local sky = { 0.55, 0.6, 0.66 }
    local ok2, topR, topG, topB = pcall(getSkyGradient)
    if ok2 and topR then
        sky = { (topR + 90) / 400, (topG + 90) / 400, (topB + 90) / 400 }
    end
    local v = {
        wet = st.wet,
        wetVar = 0.35,
        puddleLevel = st.forcedPuddle or st.puddle,
        night = st.forcedNight or st.night,
        exposure = st.exposure,
        albedoLift = 1.12,
        worldScale = m.worldScale,
        detailScale = m.detailScale,
        meshUVScale = 1.0,
        useMeshUV = 0.0,
        normalScale = m.normalScale * (q.detailTex and 1.0 or 0.6),
        parallax = q.parallax and 0.012 or 0.0,
        markingRough = mk and mk.rough or 0.55,
        markingRetro = mk and mk.retro or 0.0,
        retroBoost = SETTINGS.nightRetro * SETTINGS.nightSpecBoost,
        hasMarking = mk and 1.0 or 0.0,
        originalMix = 0.0,
        reflectStrength = SETTINGS.reflectStrength * st.reflection * m.reflection * (q.ssr and 1.0 or 0.55),
        reflectBlur = SETTINGS.reflectBlur,
        reflectStretch = SETTINGS.reflectStretch,
        reflectAnglePow = SETTINGS.reflectAnglePow,
        sunSpec = 0.55 + 0.9 * (1 - st.night),
        time = getTickCount() / 1000,
        reflTaps = q.reflectTaps,
    }
    local vec = {
        gSun = { (RR.State.sun and RR.State.sun.dir[1]) or 0.3, (RR.State.sun and RR.State.sun.dir[2]) or 0.5,
                 (RR.State.sun and RR.State.sun.dir[3]) or 0.8, (RR.State.sun and RR.State.sun.intensity) or 0 },
        gSunColor = { (RR.State.sun and RR.State.sun.color[1]) or 1, (RR.State.sun and RR.State.sun.color[2]) or 1,
                      (RR.State.sun and RR.State.sun.color[3]) or 1, 1 },
        gLightColor = { 1.0, 0.95, 0.85, 1 },
        gScreenSize = { RR.Refl.w, RR.Refl.h, 1 / math.max(RR.Refl.w, 1), 1 / math.max(RR.Refl.h, 1) },
        gFog = { fogEnd * 0.45, fogEnd, 0, 0 },
        gFogColor = { sky[1] * 0.35, sky[2] * 0.38, sky[3] * 0.45, 1 },
    }
    return v, vec, m, mk
end

--- Push every uniform a shader declares.  Cheap enough to run whenever a value changes.
function RR.Shaders.push(shader, file, matKey, markKey)
    local v, vec, m = RR.Params.build(matKey, markKey)
    if not v then
        return false
    end
    for pack, names in pairs(ROAD_SHADER_PACK) do
        if ROAD_SHADER_UNIFORMS[file] and ROAD_SHADER_UNIFORMS[file][pack] then
            setV(shader, file, pack, v[names[1]], v[names[2]], v[names[3]], v[names[4]])
        end
    end
    for name, arr in pairs(vec) do
        setV(shader, file, name, arr[1], arr[2], arr[3], arr[4])
    end
    local tex = RR.Tex.material(matKey)
    if not tex then
        return false
    end
    setV(shader, file, 'gAlbedo', tex.albedo)
    setV(shader, file, 'gMask', tex.mask)
    setV(shader, file, 'gDetailNormal', RR.Tex.shared.detailNormal)
    setV(shader, file, 'gDetailData', RR.Tex.shared.detailData)
    setV(shader, file, 'gMicroNormal', RR.Tex.shared.microNormal)
    setV(shader, file, 'gMacro', RR.Tex.shared.macro)
    setV(shader, file, 'gPuddle', RR.Tex.shared.puddle)
    setV(shader, file, 'gWetNormal', RR.Tex.shared.wetNormal)
    setV(shader, file, 'gScreen', RR.Refl.texture() or RR.Tex.shared.macro)
    local mkt = RR.Tex.marking(markKey)
    if mkt then
        setV(shader, file, 'gMarking', mkt)
    end
    return true
end

--- The per-frame values (wetness, night, lights) change constantly; push them to every road
-- shader without re-binding the textures.
function RR.Shaders.pushLights()
    local lights = RR.State.lights or {}
    for _, inst in pairs(RR.Apply.instances) do
        if inst.shader and isElement(inst.shader) then
            local file = inst.file
            for i = 0, 3 do
                local l = lights[i + 1]
                if l then
                    setV(inst.shader, file, 'gLights' .. i, l[1], l[2], l[3], l[4])
                end
            end
        end
    end
end

function RR.Shaders.pushDynamic()
    for key, inst in pairs(RR.Apply.instances) do
        if type(inst) == 'table' and inst.shader and isElement(inst.shader) then
            local v, vec = RR.Params.build(inst.mat, inst.mark)
            if v then
                for pack, names in pairs(ROAD_SHADER_PACK) do
                    if ROAD_SHADER_UNIFORMS[inst.file][pack] then
                        setV(inst.shader, inst.file, pack, v[names[1]], v[names[2]], v[names[3]], v[names[4]])
                    end
                end
                for name, arr in pairs(vec) do
                    setV(inst.shader, inst.file, name, arr[1], arr[2], arr[3], arr[4])
                end
                setV(inst.shader, inst.file, 'gScreen', RR.Refl.texture() or RR.Tex.shared.macro)
            end
        end
    end
end

-- ---------------------------------------------------------------------------
-- applying materials to the world
-- ---------------------------------------------------------------------------
RR.Apply = { instances = {}, byTexture = {}, queue = {}, timer = nil }

--- One shader per (material, marking) pair - MTA batches by shader, so reusing them keeps the
-- number of state changes (and therefore the draw calls) as low as the material list allows.
function RR.Apply.instance(matKey, markKey)
    local key = matKey .. '|' .. tostring(markKey or '')
    local inst = RR.Apply.instances[key]
    if inst ~= nil then
        return inst
    end
    if countOf(RR.Apply.instances) >= SETTINGS.maxShaders then
        RR.Warn('shader limit reached (' .. SETTINGS.maxShaders .. ') - ' .. key .. ' not created')
        RR.Apply.instances[key] = false
        return false
    end
    local q = ROAD_QUALITY[RR.State.quality] or ROAD_QUALITY.high
    local file = q.road
    local shader, tech = RR.Shaders.create(file)
    if not shader then
        -- the high shader is not available: try the ps_2_0 one before giving up entirely
        file = 'shaders/wetroad.fx'
        shader, tech = RR.Shaders.create(file)
    end
    if not shader then
        RR.Apply.instances[key] = false
        return false
    end
    inst = { key = key, mat = matKey, mark = markKey, file = file, shader = shader, tech = tech, textures = {} }
    if not RR.Shaders.push(shader, file, matKey, markKey) then
        RR.Apply.instances[key] = false
        return false
    end
    RR.Apply.instances[key] = inst
    return inst
end

--- Apply the material of `rec` (a scanner record) to its world texture.
function RR.Apply.one(rec)
    if not rec or not rec.mat or rec.applied then
        return false
    end
    local inst = RR.Apply.instance(rec.mat, rec.mark)
    if not inst then
        return false
    end
    local ok = engineApplyShaderToWorldTexture(inst.shader, rec.name)
    if ok then
        rec.applied = true
        rec.shader = inst.shader
        inst.textures[rec.lower] = rec.name
        RR.Apply.byTexture[rec.lower] = inst
        RR.Count.applied = RR.Count.applied + 1
        return true
    end
    return false
end

function RR.Apply.removeTexture(name)
    local lower = string.lower(name or '')
    local rec = RR.Scan.get(lower)
    local inst = RR.Apply.byTexture[lower]
    if inst and inst.shader and isElement(inst.shader) then
        engineRemoveShaderFromWorldTexture(inst.shader, rec and rec.name or name)
    end
    if rec then
        rec.applied = false
        rec.shader = nil
        RR.Count.applied = math.max(0, RR.Count.applied - 1)
    end
    RR.Apply.byTexture[lower] = nil
    if inst then
        inst.textures[lower] = nil
    end
end

--- Queue everything the scanner currently knows about and apply it in small steps.
function RR.Apply.addFromScan()
    local includeReview = SETTINGS.autoApplyReview
    local includePattern = SETTINGS.autoApplyPatterns
    for _, rec in ipairs(RR.Scan.roadList(includeReview, includePattern)) do
        if not rec.applied then
            RR.Apply.queue[#RR.Apply.queue + 1] = rec
        end
    end
    RR.Apply.startTimer()
end

function RR.Apply.startTimer()
    if RR.Apply.timer and isTimer(RR.Apply.timer) then
        return
    end
    if #RR.Apply.queue == 0 then
        return
    end
    RR.Apply.timer = setTimer(function()
        local n, guard = 0, 0
        while #RR.Apply.queue > 0 and n < SETTINGS.applyPerStep and guard < 400 do
            guard = guard + 1
            local rec = table.remove(RR.Apply.queue, 1)
            if rec and not rec.applied then
                RR.Apply.one(rec)
                n = n + 1
            end
        end
        if #RR.Apply.queue == 0 then
            if RR.Apply.timer and isTimer(RR.Apply.timer) then
                killTimer(RR.Apply.timer)
            end
            RR.Apply.timer = nil
            if RR.State.started then
                local _, road, applied = RR.Scan.count()
                RR.Say(string.format('road materials applied: %d of %d road textures (%d shader sets)',
                    applied, road, countOf(RR.Apply.instances)))
            end
        end
    end, 60, 0)
end

function RR.Apply.removeAll()
    for lower in pairs(RR.Apply.byTexture) do
        RR.Apply.removeTexture(lower)
    end
    RR.Apply.byTexture = {}
    RR.Apply.queue = {}
    RR.Count.applied = 0
end

--- Re-create every shader set (quality change, /roadreload) and re-apply.
function RR.Apply.rebuild()
    RR.Apply.removeAll()
    for key in pairs(RR.Apply.instances) do
        RR.Apply.instances[key] = nil
    end
    RR.Apply.instances = {}
    RR.Scan.reset()
    RR.Scan.full(6, 500)
    RR.Apply.addFromScan()
end

-- ---------------------------------------------------------------------------
-- failsafe: no shader at all -> import new pixels under the ORIGINAL texture names
-- ---------------------------------------------------------------------------
RR.Fallback = { txd = nil, active = false }

function RR.Fallback.enable()
    if RR.Fallback.active or not SETTINGS.fallbackTXD then
        return false
    end
    local txd = engineLoadTXD(ROAD_FALLBACK_TXD)
    if not txd then
        RR.Fail('the fallback TXD could not be loaded (' .. ROAD_FALLBACK_TXD .. ')')
        return false
    end
    RR.Fallback.txd = txd
    local n = 0
    for _, rec in ipairs(RR.Scan.roadList(false, false)) do
        for _, id in ipairs(rec.models or {}) do
            if engineImportTXD(txd, id) then
                n = n + 1
            end
        end
    end
    RR.Fallback.active = true
    RR.Say('shaders unavailable - imported new road textures into ' .. n .. ' models instead')
    return true
end

function RR.Fallback.disable()
    if RR.Fallback.txd and isElement(RR.Fallback.txd) then
        destroyElement(RR.Fallback.txd)
    end
    RR.Fallback.txd = nil
    RR.Fallback.active = false
end

-- ---------------------------------------------------------------------------
-- quality presets
-- ---------------------------------------------------------------------------
function RR.Quality()
    return ROAD_QUALITY[RR.State.quality] or ROAD_QUALITY.high
end

-- load order / shader inventory (used by tools/material_report.lua)
RR.Order = {
    scripts = { 'config/settings.lua', 'config/materials.lua', 'config/roads.lua',
                'tools/texture_scanner.lua', 'tools/material_report.lua',
                'reflect.lua', 'rain.lua', 'client.lua' },
    shaderFiles = { 'shaders/road.fx', 'shaders/wetroad.fx', 'shaders/reflection.fx',
                    'shaders/rain.fx', 'shaders/post.fx' },
}

function RR.SetQuality(name, silent)
    local q = ROAD_QUALITY[name]
    if not q then
        local list = {}
        for k in pairs(ROAD_QUALITY) do
            list[#list + 1] = k
        end
        table.sort(list)
        RR.Say('usage: /roadquality ' .. table.concat(list, '|'))
        return false
    end
    RR.State.quality = name
    if RR.State.started then
        RR.Rain.initStreaks()
        RR.Rain.setupPost(name)
        RR.Refl.setup(name)
        RR.Apply.rebuild()
    end
    if not silent then
        RR.Say('quality preset: ' .. name .. ' (' .. q.label .. ')')
    end
    return true
end

--- 0 off, 1 materials, 2 + reflection, 3 + rain, 4 + grade
function RR.SetFx(level, silent)
    level = math.floor(num(level, RR.State.fx))
    level = math.max(0, math.min(4, level))
    local prev = RR.State.fx
    RR.State.fx = level
    if level == 0 then
        RR.Apply.removeAll()
        if prev > 0 then
            RR.Refl.stop()
        end
    else
        if prev == 0 then
            RR.Apply.addFromScan()
        end
        if level >= 2 then
            if not (RR.Refl.source and isElement(RR.Refl.source)) then
                RR.Refl.setup(RR.State.quality)
                RR.Refl.start()
            end
        end
        if level >= 3 then
            RR.Rain.setupPost(RR.State.quality)
        end
    end
    if not silent then
        local names = { 'off (original San Andreas materials)', 'road materials only',
                        'road materials + reflection', 'road materials + reflection + rain',
                        'road materials + reflection + rain + grade' }
        RR.Say('effects: ' .. names[level + 1])
    end
    return level
end

-- ---------------------------------------------------------------------------
-- per frame
-- ---------------------------------------------------------------------------
local lastTick = 0

function RR.onPreRender()
    if RR.State.fx >= 3 then
        RR.Rain.drawStreaks()
    end
end

function RR.onRender()
    local now = getTickCount()
    local dt = math.min(0.25, (now - lastTick) / 1000)
    lastTick = now

    RR.Refl.computeSun()
    RR.Rain.integrate(dt)
    if RR.State.fx >= 3 then
        RR.Rain.drawSplashes(dt)
    end
    if RR.State.fx >= 2 then
        RR.Refl.frame()
    end
    if RR.State.fx >= 1 then
        RR.Shaders.pushDynamic()
    end
    if RR.State.fx >= 3 then
        RR.Rain.drawPost()
    end
    if RR.State.fx >= 4 and RR.Tex.shared and RR.State.postShader then
        local sx, sy = guiGetScreenSize()
        local sh = RR.State.postShader
        dxSetShaderValue(sh, 'gSource', RR.Refl.source)
        dxSetShaderValue(sh, 'gGrade', RR.State.exposure, 1.06, 1.06, 0.55)
        dxSetShaderValue(sh, 'gTint', RR.Rain.level * 0.5, RR.State.night * 0.3, 0, 0)
        dxDrawImage(0, 0, sx, sy, sh, 0, 0, 0, tocolor(255, 255, 255, 255), true)
    end
    if RR.State.debug > 0 then
        RR.Debug.draw()
    end
end

-- ---------------------------------------------------------------------------
-- debug overlay
-- ---------------------------------------------------------------------------
RR.Debug = {}

function RR.Debug.info()
    local fps = 0
    local ok, stat = pcall(getPerformanceStats, 'fps')
    if ok and type(stat) == 'table' then
        fps = tonumber(stat.counter) or tonumber(stat[1]) or 0
    end
    local total, road, applied = RR.Scan.count()
    local mem = ''
    local ok2, ds = pcall(dxGetStatus)
    if ok2 and type(ds) == 'table' then
        mem = string.format('video %s MB free / %s MB, shaders supported %s',
            tostring(ds.VideoMemoryFree and math.floor(ds.VideoMemoryFree / 1048576) or '?'),
            tostring(ds.VideoMemoryTotal and math.floor(ds.VideoMemoryTotal / 1048576) or '?'),
            tostring(ds.ShaderModel or '?'))
    end
    return {
        string.format('RoadRealism %s   preset %s   fx %d', RR.VERSION, RR.State.quality, RR.State.fx),
        string.format('fps %.0f   %s', fps, mem),
        string.format('textures discovered %d   road %d   replaced %d   shader sets %d   shaders %d',
            total, road, applied, countOf(RR.Apply.instances), RR.Count.shaders),
        string.format('rain %.2f   wetness %.2f   puddles %.2f   night %.2f   reflection %.2f   exposure %.2f',
            RR.Rain.level, RR.State.wet, RR.State.puddle, RR.State.night,
            SETTINGS.reflectStrength * RR.State.reflection, RR.State.exposure),
        string.format('road shader %s   reflection %s   rain %s   fallback TXD %s',
            tostring(RR.State.quality and (ROAD_QUALITY[RR.State.quality] or {}).road or '-'),
            RR.Refl.ok and 'ok' or 'off', RR.Rain.shader and 'ok' or 'off',
            RR.Fallback.active and 'ACTIVE' or 'no'),
    }
end

function RR.Debug.draw()
    local lines = RR.Debug.info()
    local sx = guiGetScreenSize()
    local y = 6
    for i, l in ipairs(lines) do
        dxDrawText(l, 8, y, sx - 8, y + 18, tocolor(220, 240, 255, 235), 1.0, 'default-bold',
            'left', 'top', false, false, true)
        y = y + 17
    end
end

function RR.Debug.dump()
    for _, l in ipairs(RR.Debug.info()) do
        RR.Say(l)
    end
    local groups = RR.Scan.byMaterial()
    local keys = {}
    for k in pairs(groups) do
        keys[#keys + 1] = k
    end
    table.sort(keys)
    RR.Say('materials in use: ' .. (#keys > 0 and table.concat(keys, ', ') or 'none'))
end

-- ---------------------------------------------------------------------------
-- commands
-- ---------------------------------------------------------------------------
local function cmdQuality(_, arg)
    if not arg then
        RR.Say('usage: /roadquality low|medium|high|ultra   (now: ' .. RR.State.quality .. ')')
        return
    end
    RR.SetQuality(string.lower(arg))
end

local function cmdRain(_, arg)
    if not arg then
        RR.Say(string.format('usage: /roadrain 0-1   (now %.2f: %s)', RR.Rain.level, RR.Rain.describe(RR.Rain.level)))
        return
    end
    RR.State.rain = RR.Rain.set(arg)
end

local function cmdWet(_, arg)
    if not arg then
        RR.Say(string.format('usage: /roadwet 0-1   (now %.2f)', RR.State.wet))
        return
    end
    RR.Rain.setWet(arg)
end

local function cmdFx(_, arg)
    if not arg then
        RR.Say('usage: /roadfx 0-4  (0 off, 1 materials, 2 +reflection, 3 +rain, 4 +grade; now ' .. RR.State.fx .. ')')
        return
    end
    RR.SetFx(arg)
end

local function cmdRefl(_, arg)
    if not arg then
        RR.Say(string.format('usage: /roadrefl 0-2   (now %.2f)', RR.State.reflection))
        return
    end
    RR.State.reflection = math.max(0, math.min(2, num(arg, 1)))
    RR.Say(string.format('reflection strength %.2f', RR.State.reflection))
end

local function cmdExposure(_, arg)
    if not arg then
        RR.Say(string.format('usage: /roadexposure 0.4-2.5   (now %.2f)', RR.State.exposure))
        return
    end
    RR.State.exposure = math.max(0.4, math.min(2.5, num(arg, 1)))
    RR.Say(string.format('road exposure %.2f', RR.State.exposure))
end

local function cmdNight(_, arg)
    if not arg then
        RR.State.forcedNight = nil
        RR.Say('night factor follows the game clock again (' .. string.format('%.2f', RR.State.night) .. ')')
        return
    end
    RR.State.forcedNight = math.max(0, math.min(1, num(arg, 0)))
    RR.Say(string.format('night factor forced to %.2f', RR.State.forcedNight))
end

local function cmdPuddle(_, arg)
    if not arg then
        RR.State.forcedPuddle = nil
        RR.Say('puddles follow the wetness again')
        return
    end
    RR.State.forcedPuddle = math.max(0, math.min(1, num(arg, 0)))
    RR.Say(string.format('puddle level forced to %.2f', RR.State.forcedPuddle))
end

local function cmdDebug(_, arg)
    local lvl = math.floor(num(arg, RR.State.debug > 0 and 0 or 1))
    RR.State.debug = math.max(0, math.min(3, lvl))
    if RR.State.debug > 0 then
        RR.Say('debug overlay on (level ' .. RR.State.debug .. ')')
        RR.Debug.dump()
    else
        RR.Say('debug overlay off')
    end
end

local function cmdInfo()
    local total, road, applied = RR.Scan.count()
    RR.Say(string.format('%d materials, %d markings, %d textures loaded, %d shader sets',
        RR.Count.materials, RR.Count.markings, RR.Count.textures, countOf(RR.Apply.instances)))
    RR.Say(string.format('%d textures discovered, %d road related, %d replaced', total, road, applied))
    RR.Say('commands: /roadquality /roadrain /roadwet /roadfx /roadrefl /roadexposure /roadnight ' ..
           '/roadpuddle /roadscan /roadtextures /roadreport /roadapply /roadremove /roadreload /roaddebug /roadinfo')
end

local function cmdTextures(_, arg)
    local filter = arg and string.lower(arg) or nil
    local shown = 0
    for _, lower in ipairs(RR.Scan.order) do
        local r = RR.Scan.found[lower]
        if (not filter or string.find(lower, filter, 1, true)) and r.mat then
            RR.Say(string.format('%-28s %-16s %-8s %-20s %s', r.name, tostring(r.mat), r.tier,
                r.applied and 'replaced' or 'not replaced', tostring(r.mark or '-')))
            shown = shown + 1
            if shown >= 40 then
                RR.Say('... (' .. shown .. ' shown, use /roadreport for the full list)')
                break
            end
        end
    end
    if shown == 0 then
        RR.Say('no road textures found' .. (filter and (' matching "' .. filter .. '"') or '') ..
               ' - try /roadscan first')
    end
end

local function cmdScan(_, arg)
    RR.Say('scanning the visible world textures ...')
    local new, steps = RR.Scan.full(arg == 'full' and 60 or 20, 500)
    RR.Apply.addFromScan()
    local total, road, applied = RR.Scan.count()
    RR.Say(string.format('scan done in %d step(s): %d new textures, %d road related in total, %d replaced',
        steps, new, road, applied))
end

local function cmdReport(_, arg)
    if arg == 'save' or arg == 'write' then
        local ok, name, bytes = RR.Report.save()
        if ok then
            RR.Say(string.format('report written to %s (%d bytes) in the client resource folder', name, bytes))
        else
            RR.Fail('could not write the report: ' .. tostring(name))
        end
    else
        RR.Report.dump()
        RR.Say('use /roadreport save to write road_texture_report.txt')
    end
end

local function cmdApply(_, arg)
    if not arg then
        RR.Say('usage: /roadapply <texture name>  (applies an ambiguous "review" texture)')
        return
    end
    local rec = RR.Scan.get(arg)
    if not rec then
        RR.Say('"' .. arg .. '" was not discovered - run /roadscan first')
        return
    end
    if not rec.mat then
        RR.Say('"' .. arg .. '" has no road material suggestion')
        return
    end
    if RR.Apply.one(rec) then
        RR.Say(string.format('%s -> %s%s', rec.name, rec.mat, rec.mark and (' + ' .. rec.mark) or ''))
    else
        RR.Fail('could not apply a material to ' .. rec.name)
    end
end

local function cmdRemove(_, arg)
    if not arg then
        RR.Say('usage: /roadremove <texture name>   (or /roadremove all)')
        return
    end
    if string.lower(arg) == 'all' then
        RR.Apply.removeAll()
        RR.Say('all road materials removed - the original San Andreas textures are back')
        return
    end
    local rec = RR.Scan.get(arg)
    if not rec then
        RR.Say('"' .. arg .. '" was not discovered')
        return
    end
    RR.Apply.removeTexture(arg)
    RR.Say(rec.name .. ' restored to the original texture')
end

local function cmdReload()
    RR.Say('reloading shaders and textures ...')
    RR.Apply.removeAll()
    RR.Shaders.destroyAll()
    RR.Tex.destroyAll()
    RR.Refl.teardown()
    local n, bad = RR.Tex.loadShared()
    if n == 0 then
        RR.Fail('reload aborted: no shared texture could be loaded')
        return
    end
    RR.State.quality = SETTINGS.defaultQuality
    RR.SetQuality(RR.State.quality, true)
    if RR.State.fx >= 2 then
        RR.Refl.setup(RR.State.quality)
        RR.Refl.start()
    end
    RR.Rain.setupPost(RR.State.quality)
    RR.Scan.reset()
    RR.Scan.full(6, 500)
    RR.Apply.addFromScan()
    RR.Say(string.format('reload done: %d shared textures, %d materials, %d markings%s',
        n, RR.Count.materials, RR.Count.markings, bad > 0 and (' (' .. bad .. ' missing)') or ''))
end

local function cmdOff()
    RR.SetFx(0)
end

local function cmdOn()
    RR.SetFx(2)
end

-- ---------------------------------------------------------------------------
-- lifecycle
-- ---------------------------------------------------------------------------
function RR.start()
    if RR.State.started then
        return
    end
    local t0 = getTickCount()
    RR.Say('loading road materials ...')
    RR.State.quality = SETTINGS.defaultQuality
    RR.State.exposure = SETTINGS.exposure
    RR.State.debug = SETTINGS.debug and 1 or 0

    local n, bad = RR.Tex.loadShared()
    RR.Say(string.format('shared texture set loaded: %d%s', n, bad > 0 and (' (' .. bad .. ' missing)') or ''))

    -- shaders are created independently: one that fails only disables its own effect
    local roadFile = (ROAD_QUALITY[RR.State.quality] or ROAD_QUALITY.high).road
    local roadSh, roadTech = RR.Shaders.create(roadFile)
    if roadSh then
        RR.Say('road shader loaded (' .. roadFile .. ', technique ' .. tostring(roadTech) .. ')')
    else
        roadSh, roadTech = RR.Shaders.create('shaders/wetroad.fx')
        if roadSh then
            RR.Warn('using the compatibility road shader instead (wetroad.fx)')
        else
            RR.Fail('no road shader compiled - falling back to replaced textures only')
        end
    end
    if not roadSh then
        RR.Fallback.enable()
    end

    RR.Refl.setup(RR.State.quality)
    if RR.Refl.ok then
        RR.Say('reflection shader loaded (' .. RR.Refl.w .. 'x' .. RR.Refl.h .. ' screen source)')
    end
    RR.Rain.setupPost(RR.State.quality)
    if RR.Rain.shader then
        RR.Say('rain shader loaded')
    else
        RR.Warn('rain.fx not available - no lens droplets')
    end
    local post = RR.Shaders.create('shaders/post.fx')
    RR.State.postShader = post or nil

    RR.Rain.start()
    RR.Refl.start()
    RR.State.started = true
    RR.State.fx = 2
    RR.Say(string.format('asphalt / concrete / pavement materials loaded: %d (+ %d road markings)',
        RR.Count.materials, RR.Count.markings))

    -- discover and apply, in bounded steps so the first frames stay smooth
    local new = RR.Scan.full(6, 500)
    local total, road = RR.Scan.count()
    RR.Say(string.format('road textures detected: %d (of %d visible textures)', road, total))
    RR.Apply.addFromScan()
    RR.Scan.start()

    addEventHandler('onClientPreRender', root, RR.onPreRender)
    addEventHandler('onClientRender', root, RR.onRender)
    lastTick = getTickCount()

    RR.Say(string.format('road overhaul initialised successfully in %.2f s - %d road textures queued',
        (getTickCount() - t0) / 1000, #RR.Apply.queue))
    RR.Say('type /roadinfo for the command list')
end

function RR.stop()
    removeEventHandler('onClientPreRender', root, RR.onPreRender)
    removeEventHandler('onClientRender', root, RR.onRender)
    RR.Scan.stop()
    RR.Apply.removeAll()
    RR.Apply.timer = nil
    RR.Rain.stop()
    RR.Refl.stop()
    RR.Fallback.disable()
    if RR.State.postShader and isElement(RR.State.postShader) then
        destroyElement(RR.State.postShader)
    end
    RR.State.postShader = nil
    RR.Shaders.destroyAll()
    RR.Tex.destroyAll()
    RR.Apply.instances = {}
    RR.State.started = false
    RR.State.forcedNight = nil
    RR.State.forcedPuddle = nil
end

addEventHandler('onClientResourceStart', resourceRoot, function()
    local ok, err = pcall(RR.start)
    if not ok then
        RR.Fail('initialisation failed: ' .. tostring(err))
    end
end)

addEventHandler('onClientResourceStop', resourceRoot, function()
    local ok, err = pcall(RR.stop)
    if not ok then
        outputDebugString('[RoadRealism] cleanup failed: ' .. tostring(err), 1)
    end
end)

for name, fn in pairs({
    roadquality = cmdQuality, roadrain = cmdRain, roadwet = cmdWet, roadfx = cmdFx,
    roadrefl = cmdRefl, roadexposure = cmdExposure, roadnight = cmdNight, roadpuddle = cmdPuddle,
    roaddebug = cmdDebug, roadinfo = cmdInfo, roadtextures = cmdTextures, roadscan = cmdScan,
    roadreport = cmdReport, roadapply = cmdApply, roadremove = cmdRemove, roadreload = cmdReload,
    roadoff = cmdOff, roadon = cmdOn,
}) do
    addCommandHandler(name, fn)
end

-- the server can drive the rain for everybody (see server.lua)
addEvent('RoadRealism:setRain', true)
addEventHandler('RoadRealism:setRain', root, function(level)
    RR.State.rain = RR.Rain.set(level, true)
end)

addEvent('RoadRealism:reload', true)
addEventHandler('RoadRealism:reload', root, function()
    RR.Say('the server asked for a reload')
    cmdReload()
end)
