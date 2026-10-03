-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- rain.lua - the rain system: world rain, wetness integration, 3D rain streaks, lens droplets and
-- the rain sound.
--
-- Wetness is NOT the rain level.  It is an integrated state with a slow rise and a much slower
-- fall, which is what makes a road stay wet for minutes after the rain stops:
--
--     rain 0.0 -> wet 0.00  completely dry
--     rain 0.1 -> wet 0.15  slight moisture
--     rain 0.3 -> wet 0.40  damp roads
--     rain 0.5 -> wet 0.68  wet roads
--     rain 0.8 -> wet 0.90  heavy rain
--     rain 1.0 -> wet 1.00  standing water
--
-- and the wetness drives roughness, specular, reflection strength, diffuse darkening and the
-- puddle fill level (see road.fx).  Puddles start at SETTINGS.puddleFrom and are full at
-- SETTINGS.puddleFull.
-- -----------------------------------------------------------------------------
RR = RR or {}

RR.Rain = {
    level = 0.0,
    streaks = {},
    splashes = {},
    material = nil,
    splashMaterial = nil,
    sound = nil,
    shader = nil,
    enabled = true,
    savedWeather = nil,
    savedRain = nil,
    lastFrame = 0,
}

local RA = RR.Rain

-- rain level -> target wetness (the table from config/materials.lua)
local function targetWet(level)
    local t = ROAD_RAIN_TABLE
    if level <= t[1][1] then
        return t[1][2]
    end
    for i = 2, #t do
        if level <= t[i][1] then
            local a, b = t[i - 1], t[i]
            local f = (level - a[1]) / math.max(b[1] - a[1], 1e-6)
            return a[2] + (b[2] - a[2]) * f
        end
    end
    return t[#t][2]
end

--- Integrate the wetness one frame.  Rising is fast, drying is slow (a real road holds water).
function RR.Rain.integrate(dt)
    local target = targetWet(RA.level)
    local wet = RR.State.wet or 0
    local rate = (target > wet) and SETTINGS.wetRiseRate or SETTINGS.wetDryRate
    -- at rain level 1 the road floods at once, below that it creeps up
    rate = rate * (0.4 + 0.6 * RA.level)
    wet = wet + (target - wet) * math.min(1, rate * dt)
    wet = math.max(SETTINGS.wetMin, math.min(SETTINGS.wetMax, wet))
    RR.State.wet = wet
    local span = math.max(SETTINGS.puddleFull - SETTINGS.puddleFrom, 1e-6)
    RR.State.puddle = math.max(0, math.min(1, (wet - SETTINGS.puddleFrom) / span))
    return wet
end

--- Set the rain level (0..1).  Drives the engine rain, the weather and the wetness target.
function RR.Rain.set(level, silent)
    level = math.max(0, math.min(1, tonumber(level) or 0))
    RA.level = level
    setRainLevel(level)
    if SETTINGS.rainOwnWeather then
        if level >= 0.35 then
            setWeatherBlended(SETTINGS.rainWeather)
        elseif level > 0.02 then
            setWeatherBlended(SETTINGS.rainWeatherDamp)
        else
            setWeatherBlended(RA.savedWeather or 0)
        end
    end
    if level <= 0.001 then
        RR.State.wet = math.min(RR.State.wet or 0, SETTINGS.wetMax)
    end
    RR.Rain.updateSound()
    if not silent then
        RR.Say(string.format('rain %.2f -> %s', level, RR.Rain.describe(level)))
    end
    return level
end

function RR.Rain.describe(level)
    local wet = targetWet(level)
    local t = ROAD_RAIN_TABLE
    local best = t[1][3]
    for i = 1, #t do
        if level >= t[i][1] - 1e-6 then
            best = t[i][3]
        end
    end
    return string.format('%s (wetness %.2f)', best, wet)
end

--- Force a wetness directly (used by /roadwet for testing without rain).
function RR.Rain.setWet(w)
    w = math.max(0, math.min(1, tonumber(w) or 0))
    RR.State.wet = w
    local span = math.max(SETTINGS.puddleFull - SETTINGS.puddleFrom, 1e-6)
    RR.State.puddle = math.max(0, math.min(1, (w - SETTINGS.puddleFrom) / span))
    RR.Say(string.format('wetness forced to %.2f (puddles %.2f)', w, RR.State.puddle))
    return w
end

-- ---------------------------------------------------------------------------
-- 3D rain streaks.  Real billboards in the world (dxDrawMaterialLine3D), not lines on the screen:
-- they fall with a velocity, are drawn along that velocity, are recycled around the camera and are
-- lit by the same light direction as the wet road, so they read as falling water.
-- ---------------------------------------------------------------------------
function RR.Rain.initStreaks()
    RA.streaks = {}
    local q = ROAD_QUALITY[RR.State.quality] or ROAD_QUALITY.high
    local n = q.rainStreaks
    for i = 1, n do
        RA.streaks[i] = { x = 0, y = 0, z = 0, life = 0, len = 0 }
    end
    RA.maxStreaks = n
end

local function respawn(s, cx, cy, cz, spread, above)
    s.x = cx + math.random() * spread * 2 - spread
    s.y = cy + math.random() * spread * 2 - spread
    s.z = cz + above * (0.35 + math.random() * 0.9)
    s.len = 0.9 + math.random() * 1.5
    s.life = 1
end

--- One frame of streaks.  Called from onClientPreRender so they are part of the 3D world.
function RR.Rain.drawStreaks()
    if not RA.material or RA.level < 0.05 or not RR.State.fx or RR.State.fx < 1 then
        return
    end
    local cam = { getCameraMatrix() }
    if not cam[1] then
        return
    end
    local cx, cy, cz = cam[1], cam[2], cam[3]
    local spread = 26 + 20 * RA.level
    local speed = (58 + 42 * RA.level)
    local dt = math.min(0.1, (getTickCount() - RA.lastStreak) / 1000)
    RA.lastStreak = getTickCount()
    -- wind: the streaks lean with the game wind velocity so rain matches the trees
    local wx, wy = 0, 0
    local ok, a, b = pcall(getWindVelocity)
    if ok and a then
        wx, wy = a * 0.5, b * 0.5
    end
    local alpha = math.floor(70 + 150 * RA.level)
    local n = math.floor(RA.maxStreaks * math.min(1, RA.level * 1.35))
    for i = 1, n do
        local s = RA.streaks[i]
        if s then
            s.z = s.z - speed * dt
            s.x = s.x + wx * dt
            s.y = s.y + wy * dt
            if s.z < cz - 14 or math.abs(s.x - cx) > spread or math.abs(s.y - cy) > spread then
                respawn(s, cx, cy, cz, spread, 16)
            end
            local lx = s.x + wx * 0.03
            local ly = s.y + wy * 0.03
            local lz = s.z - s.len
            dxDrawMaterialLine3D(s.x, s.y, s.z, lx, ly, lz, RA.material, 0.055,
                tocolor(200, 214, 228, alpha), cx, cy, cz + 4)
        end
    end
end

--- Ground splashes: short lived flat crowns just above the ground near the camera.
function RR.Rain.spawnSplash()
    if RA.level < 0.15 or not RA.splashMaterial then
        return
    end
    if #RA.splashes >= 26 then
        return
    end
    local cam = { getCameraMatrix() }
    if not cam[1] then
        return
    end
    local x = cam[1] + math.random() * 34 - 17
    local y = cam[2] + math.random() * 34 - 17
    local z = getGroundPosition(x, y, cam[3])
    if z and z > -100 then
        RA.splashes[#RA.splashes + 1] = { x = x, y = y, z = z + 0.03, t = 0, size = 0.35 + math.random() * 0.5 }
    end
end

function RR.Rain.drawSplashes(dt)
    local cam = { getCameraMatrix() }
    if not cam[1] then
        return
    end
    local alive = {}
    for _, s in ipairs(RA.splashes) do
        s.t = s.t + dt * 3.4
        if s.t < 1 then
            local g = s.t
            local size = s.size * (0.4 + g * 1.9)
            local a = math.floor(150 * (1 - g) * math.min(1, RA.level * 1.6))
            if a > 4 then
                dxDrawMaterialLine3D(s.x - size, s.y, s.z, s.x + size, s.y, s.z, RA.splashMaterial,
                    size * 1.6, tocolor(210, 220, 230, a), cam[1], cam[2], cam[3])
            end
            alive[#alive + 1] = s
        end
    end
    RA.splashes = alive
end

-- ---------------------------------------------------------------------------
-- lens droplets + the rain sound
-- ---------------------------------------------------------------------------
function RR.Rain.setupPost(quality)
    local q = ROAD_QUALITY[quality] or ROAD_QUALITY.high
    if RA.shader and isElement(RA.shader) then
        destroyElement(RA.shader)
    end
    RA.shader = nil
    if not q.rainDrops then
        return false
    end
    local sh, tech = RR.Shaders.create('shaders/rain.fx')
    if not sh then
        return false
    end
    RA.shader = sh
    RA.tech = tech
    dxSetShaderValue(sh, 'gSource', RR.Refl.source)
    dxSetShaderValue(sh, 'gDrops', RR.Tex.shared.droplets)
    return true
end

--- Full screen rain pass, drawn last (postGUI) in onClientRender.
function RR.Rain.drawPost()
    if not (RA.shader and RR.Refl.source) or RR.State.fx < 2 or RA.level < 0.02 then
        return false
    end
    local sx, sy = guiGetScreenSize()
    dxSetShaderValue(RA.shader, 'gTexel', 1 / sx, 1 / sy, sx, sy)
    dxSetShaderValue(RA.shader, 'gRainFx', RA.level, 1.1, 0.35, 0.6 + 2.4 * RA.level)
    dxSetShaderValue(RA.shader, 'gTime', getTickCount() / 1000)
    dxDrawImage(0, 0, sx, sy, RA.shader, 0, 0, 0, tocolor(255, 255, 255, 255), true)
    return true
end

function RR.Rain.updateSound()
    if not SETTINGS.rainSound then
        return
    end
    local want = RA.level > 0.03
    if want and not (RA.sound and isElement(RA.sound)) then
        RA.sound = playSound('audio/rain_loop.wav', true)
        if RA.sound then
            setSoundVolume(RA.sound, 0)
        end
    elseif not want and RA.sound and isElement(RA.sound) then
        destroyElement(RA.sound)
        RA.sound = nil
    end
    if RA.sound and isElement(RA.sound) then
        setSoundVolume(RA.sound, SETTINGS.rainVolume * math.min(1, RA.level * 1.4))
    end
end

-- ---------------------------------------------------------------------------
-- lifecycle
-- ---------------------------------------------------------------------------
function RR.Rain.start()
    RA.savedWeather = getWeather()
    RA.savedRain = getRainLevel()
    RA.lastStreak = getTickCount()
    RA.material = dxCreateTexture(ROAD_SHARED.rainStreak, 'argb', true)
    RA.splashMaterial = dxCreateTexture(ROAD_SHARED.splash, 'argb', true)
    if not RA.material then
        RR.Warn('the rain streak texture could not be loaded - no 3D rain')
    end
    RR.Rain.initStreaks()
    RR.Rain.set(RA.level, true)
    if RA.splashTimer and isTimer(RA.splashTimer) then
        killTimer(RA.splashTimer)
    end
    RA.splashTimer = setTimer(function()
        local rate = math.floor(1 + 16 * RA.level)
        for _ = 1, rate do
            pcall(RR.Rain.spawnSplash)
        end
    end, 200, 0)
end

function RR.Rain.stop()
    if RA.splashTimer and isTimer(RA.splashTimer) then
        killTimer(RA.splashTimer)
    end
    RA.splashTimer = nil
    if RA.sound and isElement(RA.sound) then
        destroyElement(RA.sound)
    end
    RA.sound = nil
    if RA.shader and isElement(RA.shader) then
        destroyElement(RA.shader)
    end
    RA.shader = nil
    if RA.material and isElement(RA.material) then
        destroyElement(RA.material)
    end
    RA.material = nil
    if RA.splashMaterial and isElement(RA.splashMaterial) then
        destroyElement(RA.splashMaterial)
    end
    RA.splashMaterial = nil
    RA.streaks, RA.splashes = {}, {}
    if SETTINGS.preserveWeatherOnStop then
        setRainLevel(RA.savedRain or 0)
        if RA.savedWeather then
            setWeather(RA.savedWeather)
        end
    end
end
