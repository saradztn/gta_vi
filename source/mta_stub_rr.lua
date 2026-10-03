-- Created by: Arena.ai Agent Mode (AI) - strict headless MTA:SA model for RoadRealism
-- Runs the REAL client.lua / rain.lua / reflect.lua / tools / server.lua (Lua 5.1 via lupa) so every
-- logic, ordering, argument and cleanup path is exercised without a game.  Unknown globals raise,
-- elements die when destroyed, shaders can be forced to fail, and the visible world texture list is
-- seeded from the resource's own whitelist so the discovery system has real data to find.
math.atan2 = math.atan2 or function(y, x) return math.atan(y, x) end
unpack = unpack or table.unpack   -- MTA is Lua 5.1; the test VM may be newer

T = {
    now = 0, timers = {}, elems = {}, chat = {}, log = {}, files = {}, visible = {},
    applied = {}, removed = {}, imported = {}, shaders = {}, sounds = {},
    handlers = { client = {}, server = {} }, cmds = { client = {}, server = {} },
    calls = {}, weather = 0, rain = 0, hour = 12, minute = 0,
    shaderMode = 'ok', fog = 700,
    rainSet = nil, weatherSet = nil,
}

local function count(name) T.calls[name] = (T.calls[name] or 0) + 1 end

-- ---------------------------------------------------------------- elements
local function newEl(kind, props, parent)
    local e = props or {}
    e.kind, e.alive, e.parent = kind, true, parent
    T.elems[#T.elems + 1] = e
    return e
end
local root = newEl('root', {})
local resourceRoot = newEl('resourceRoot', {}, root)
local localPlayer = newEl('player', { x = 0, y = 0, z = 20 }, root)
T.root, T.resourceRoot, T.localPlayer = root, resourceRoot, localPlayer
root, resourceRoot, localPlayer = root, resourceRoot, localPlayer
-- expose as globals (MTA predefined)
_G.root = T.root
_G.resourceRoot = T.resourceRoot
_G.localPlayer = T.localPlayer

function T.alive(kind)
    local n = 0
    for _, e in ipairs(T.elems) do
        if e.kind == kind and e.alive then n = n + 1 end
    end
    return n
end
function T.created(kind)
    local n = 0
    for _, e in ipairs(T.elems) do
        if e.kind == kind then n = n + 1 end
    end
    return n
end

local function isEl(v) return type(v) == 'table' and v.isel == nil and v.kind ~= nil and v.alive == true end

-- ---------------------------------------------------------------- timers
function setTimer(fn, interval, times, ...)
    local t = { fn = fn, interval = interval, times = times or 1, left = times or 1, next = T.now + interval,
                args = { ... }, alive = true, isTimer = true }
    T.timers[#T.timers + 1] = t
    return t
end
function killTimer(t) if type(t) == 'table' then t.alive = false end return true end
function isTimer(t) return type(t) == 'table' and t.alive == true end
function T.liveTimers()
    local n = 0
    for _, t in ipairs(T.timers) do if t.alive then n = n + 1 end end
    return n
end

-- ---------------------------------------------------------------- events / commands
function addEvent(name, allowRemote) return true end
function addEventHandler(ev, el, fn, prop, prio)
    local side = (el == T.root or el == T.resourceRoot) and 'client' or 'client'
    T.handlers.client[ev] = T.handlers.client[ev] or {}
    table.insert(T.handlers.client[ev], fn)
    return true
end
function removeEventHandler(ev, el, fn)
    local l = T.handlers.client[ev] or {}
    for i = #l, 1, -1 do
        if l[i] == fn then table.remove(l, i) end
    end
    return true
end
function T.handlerCount(ev) return #(T.handlers.client[ev] or {}) end
function addCommandHandler(name, fn, restricted, caseSensitive)
    T.cmds.client[name] = fn
    return true
end
function removeCommandHandler(name, fn) T.cmds.client[name] = nil return true end
function T.hasCmd(name) return T.cmds.client[name] ~= nil end
function T.cmd(name, ...)
    local fn = T.cmds.client[name]
    if not fn then error('no client command ' .. name) end
    local ok, err = pcall(fn, name, ...)
    if not ok then table.insert(T.log, 'cmd error: ' .. tostring(err)) end
    return ok
end

-- ---------------------------------------------------------------- output
function outputChatBox(msg, ...)
    T.chat[#T.chat + 1] = tostring(msg)
    return true
end
function outputDebugString(msg, level)
    T.log[#T.log + 1] = tostring(msg)
    return true
end
function outputConsole(msg, el)
    T.chat[#T.chat + 1] = tostring(msg)
    return true
end
function outputServerLog(msg) T.log[#T.log + 1] = '[server] ' .. tostring(msg) return true end
function T.lastChat() return T.chat[#T.chat] end
function T.chatContains(s)
    for _, c in ipairs(T.chat) do if string.find(c, s, 1, true) then return true end end
    return false
end

-- ---------------------------------------------------------------- world state
function getTickCount() return T.now end
function getTime() return T.hour, T.minute end
function setTime(h, m) T.hour, T.minute = h, m return true end
function getWeather() return T.weather end
function setWeather(w) T.weather = w; T.weatherSet = w return true end
function setWeatherBlended(w) T.weather = w; T.weatherSet = w return true end
function getRainLevel() return T.rain end
function setRainLevel(r) T.rain = r; T.rainSet = r return true end
function getFogDistance() return T.fog end
function setFogDistance(d) T.fog = d return true end
function getSkyGradient() return 110, 130, 160, 40, 40, 50 end
function getSunColor() return 255, 240, 220, 255, 200, 150 end
function getWindVelocity() return 0.2, 0.1, 0 end
function getGroundPosition(x, y, z) return 10 end
function getRealTime() return { year = 126, month = 9, monthday = 3, hour = T.hour, minute = T.minute, second = 0 } end
function getVersion() return { name = 'MTA:SA', number = '1.6.0', sortable = '1.6.0' } end
function getResourceName(res) return 'RoadRealism' end
function getThisResource() return T.resourceRoot end
function guiGetScreenSize() return 1280, 720 end
function getPerformanceStats(cat) return { counter = '60', name = cat } end
function dxGetStatus() return { VideoMemoryFree = 200 * 1024 * 1024, VideoMemoryTotal = 2048 * 1024 * 1024, ShaderModel = '3.0' } end

-- ---------------------------------------------------------------- elements / camera
local cam = { 0, -6, 22, 0, 0, 20 }
function getCameraMatrix() return cam[1], cam[2], cam[3], cam[4], cam[5], cam[6], 1, 0, 0, 70 end
function T.setCam(...) cam = { ... } end
function getElementPosition(el) return el.x or 0, el.y or 0, el.z or 20 end
function getElementsByType(kind)
    local out = {}
    for _, e in ipairs(T.elems) do
        if e.kind == kind and e.alive then out[#out + 1] = e end
    end
    return out
end
function getDistanceBetweenPoints3D(x1, y1, z1, x2, y2, z2)
    local dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    return math.sqrt(dx * dx + dy * dy + dz * dz)
end
function isElement(v) return type(v) == 'table' and v.kind ~= nil and v.alive == true end
function destroyElement(el)
    if type(el) == 'table' then el.alive = false end
    return true
end
function getElementModel(el) return el.model or 1400 end
function getElementMatrix(el)
    return { { 1, 0, 0, 0 }, { 0, 1, 0, 0 }, { 0, 0, 1, 0 }, { el.x or 0, el.y or 0, el.z or 0, 1 } }
end
function areVehicleLightsOn(v) return v.lights ~= false end
function addVehicle(x, y, z)
    local v = newEl('vehicle', { x = x, y = y, z = z, lights = true, model = 411 }, root)
    return v
end

-- ---------------------------------------------------------------- textures / shaders
function fileExists(p) return T.files[p] == true end
T.written = {}
function fileCreate(path)
    if not path then return false end
    local h = { path = path, buf = '' }
    T.written[path] = h
    return h
end
function fileWrite(h, data)
    if type(h) ~= 'table' then return false end
    h.buf = h.buf .. tostring(data)
    return string.len(tostring(data))
end
function fileClose(h)
    if type(h) ~= 'table' then return false end
    h.closed = true
    T.files[h.path] = true
    return true
end
function dxCreateTexture(path, fmt, mip, ttype)
    count('dxCreateTexture')
    if not T.files[path] then return false end
    fmt = fmt or 'argb'
    -- MTA: format must be a pixel format, NOT an address mode
    if fmt ~= 'argb' and fmt ~= 'dxt1' and fmt ~= 'dxt3' and fmt ~= 'dxt5' then
        return false
    end
    -- MTA: 4th arg is textureType ("2d"/"3d"/"cube"); anything else is a hard failure
    if ttype ~= nil and ttype ~= '2d' and ttype ~= '3d' and ttype ~= 'cube' then
        return false
    end
    local e = newEl('texture', { path = path })
    return e
end
function dxCreateShader(path, prio, maxdist, layered, types)
    count('dxCreateShader')
    if not T.files[path] then return false, 'file not found: ' .. tostring(path) end
    if T.shaderMode == 'fail' then return false, 'compile error (test)' end
    local e = newEl('shader', { path = path, values = {} })
    T.shaders[path] = e
    return e, (T.shaderMode == 'fallback') and 'fallback' or 'tec0'
end
function dxSetShaderValue(sh, name, ...)
    if not (type(sh) == 'table' and sh.kind == 'shader') then error('dxSetShaderValue: not a shader') end
    sh.values[name] = select('#', ...) > 1 and { ... } or (...)
    return true
end
function engineApplyShaderToWorldTexture(sh, name)
    if not (type(sh) == 'table' and sh.kind == 'shader') then error('not a shader') end
    T.applied[name] = true
    return true
end
function engineRemoveShaderFromWorldTexture(sh, name)
    T.applied[name] = nil
    T.removed[name] = true
    return true
end
function engineGetVisibleTextureNames()
    local out = {}
    for n in pairs(T.visible) do out[#out + 1] = n end
    return out
end
function engineGetModelTextureNames(id) return { 'snpedtest1', 'crossing_law' } end
function engineLoadTXD(path)
    if not T.files[path] then return false end
    local e = newEl('txd', { path = path })
    return e
end
function engineImportTXD(txd, modelId)
    T.imported[tostring(modelId)] = true
    return true
end

-- ---------------------------------------------------------------- screen / draw
function dxCreateScreenSource(w, h)
    if w < 1 or h < 1 then error('dxCreateScreenSource: bad size') end
    return newEl('screensource', { w = w, h = h })
end
function dxUpdateScreenSource(ss, now) return true end
function dxCreateRenderTarget(w, h, alpha) return newEl('rendertarget', { w = w, h = h }) end
function dxSetRenderTarget(rt, clear) return true end
function dxDrawImage(...) count('dxDrawImage') return true end
function dxDrawText(...) count('dxDrawText') return true end
function dxDrawMaterialLine3D(...) count('dxDrawMaterialLine3D') return true end
function dxDrawLine3D(...) count('dxDrawLine3D') return true end

-- ---------------------------------------------------------------- audio
function playSound(path, looped)
    if not T.files[path] then return false end
    local e = newEl('sound', { path = path, vol = 1 })
    T.sounds[path] = e
    return e
end
function setSoundVolume(s, v) if type(s) == 'table' then s.vol = v end return true end
function getSoundLength(s) return 8 end

-- ---------------------------------------------------------------- render handler drivers
function T.fireClient(ev, ...)
    local l = T.handlers.client[ev] or {}
    for _, fn in ipairs(l) do
        local ok, err = pcall(fn, ...)
        if not ok then table.insert(T.log, ev .. ' error: ' .. tostring(err)) end
    end
end
function T.frame(dt)
    T.now = T.now + dt
    -- fire due timers (a copy so timers can add timers)
    local due = {}
    for _, t in ipairs(T.timers) do
        if t.alive and t.next <= T.now then due[#due + 1] = t end
    end
    for _, t in ipairs(due) do
        if t.alive then
            local ok, err = pcall(t.fn, unpack(t.args))
            if not ok then table.insert(T.log, 'timer error: ' .. tostring(err)) end
            if t.times == 0 then
                t.next = t.next + t.interval
            else
                t.left = t.left - 1
                if t.left <= 0 then t.alive = false else t.next = t.next + t.interval end
            end
        end
    end
    T.fireClient('onClientPreRender', dt / 1000)
    T.fireClient('onClientRender', dt / 1000)
end
function T.adv(ms, dt)
    dt = dt or 50
    for _ = 1, math.floor(ms / dt) do T.frame(dt) end
end

-- ---------------------------------------------------------------- server side
_G.hasObjectPermissionTo = function(acc, perm, def) return T.aclAdmin == true end
_G.getPlayerAccount = function(p) return { acc = 'a', guest = false } end
_G.isGuestAccount = function(a) return false end
_G.getPlayerName = function(p) return 'tester' end
_G.triggerClientEvent = function(el, ev, src, ...)
    T.log[#T.log + 1] = 'toClient:' .. ev
    return true
end
