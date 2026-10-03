-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- reflect.lua - the light side of the wet road.
--
--   camera -> screen source -> reflection.fx (bright pass + vertical smear) -> reflection target
--                                                                          -> sampled by road.fx
--
-- Only real light sources survive the bright pass, so a wet road reflects street lamps, vehicle
-- headlights, traffic lights, neon and bright signs - and not the buildings next to them.  The
-- smear is what turns a lamp into the long column you see on a real wet road.
--
-- This module also gathers the four nearest vehicle headlights every few hundred milliseconds and
-- hands them to the road shader as local lights: that is what makes the road answer to the car in
-- front of you instead of only to a static sun.
-- -----------------------------------------------------------------------------
RR = RR or {}

RR.Refl = {
    source = nil,            -- dxCreateScreenSource
    target = nil,            -- reflection render target
    shader = nil,            -- reflection.fx
    postShader = nil,        -- rain.fx / post.fx (owned by rain.lua / client.lua, drawn here)
    w = 640, h = 400,
    lights = { {}, {}, {}, {} },
    lightTimer = nil,
    sun = { dir = { 0.3, 0.5, 0.8 }, intensity = 0.0, color = { 1, 1, 1 } },
    ok = false,
}

local R = RR.Refl

--- Approximate sun direction from the game clock.  San Andreas does not expose a sun vector to
-- Lua, so this is the analytic path the sky uses (east at 06:00, overhead at noon, west at 18:00).
-- It is only used to place the specular highlight and to fade the night factor - nothing in the
-- resource depends on it being exact.
function RR.Refl.computeSun()
    local hour, minute = getTime()
    local t = (hour + minute / 60.0 - 6.0) / 12.0            -- 0 at 06:00, 1 at 18:00
    local elev = math.sin(math.pi * t)                       -- 1 at noon, <0 at night
    local azim = math.pi * (t - 0.5)                         -- east -> west
    local dir = { math.sin(azim) * 0.6, -math.cos(azim) * 0.6, math.max(elev, -0.2) }
    local len = math.sqrt(dir[1] * dir[1] + dir[2] * dir[2] + dir[3] * dir[3])
    if len > 0.0001 then
        dir[1], dir[2], dir[3] = dir[1] / len, dir[2] / len, dir[3] / len
    end
    local intensity = math.max(0, elev)
    local cr, cg, cb = 1.0, 1.0, 1.0
    local ok, r1, g1, b1 = pcall(getSunColor)
    if ok and r1 then
        cr, cg, cb = r1 / 255, g1 / 255, b1 / 255
    end
    R.sun.dir = dir
    R.sun.intensity = intensity
    R.sun.color = { cr, cg, cb }
    -- 0 = full day, 1 = full night (overcast rain counts as dusk)
    local night = 1.0 - math.min(1, math.max(0, elev * 2.2))
    local rain = RR.State.rain or 0
    night = math.min(1.0, night + rain * 0.25)
    RR.State.night = night
    RR.State.sun = R.sun
    return dir, intensity, night
end

--- Create the screen source, the reflection target and the reflection shader.
function RR.Refl.setup(quality)
    RR.Refl.teardown()
    local q = ROAD_QUALITY[quality] or ROAD_QUALITY.high
    R.w, R.h = q.screenW, q.screenH
    R.source = dxCreateScreenSource(R.w, R.h)
    if not R.source then
        RR.Warn('could not create the screen source - reflections are disabled')
        return false
    end
    R.target = dxCreateRenderTarget(R.w, R.h, false)
    if not R.target then
        RR.Warn('could not create the reflection target - reflections are disabled')
        destroyElement(R.source)
        R.source = nil
        return false
    end
    local sh, tech = RR.Shaders.create('shaders/reflection.fx')
    if not sh then
        RR.Warn('reflection.fx did not compile - reflections are disabled')
        return false
    end
    R.shader = sh
    R.tech = tech
    dxSetShaderValue(sh, 'gSource', R.source)
    dxSetShaderValue(sh, 'gPuddle', RR.Tex.shared.puddle)
    dxSetShaderValue(sh, 'gTexel', 1 / R.w, 1 / R.h, R.w, R.h)
    RR.Refl.applyParams()
    R.ok = true
    return true
end

function RR.Refl.teardown()
    if R.shader and isElement(R.shader) then
        RR.Shaders.destroy('shaders/reflection.fx')
    end
    R.shader = nil
    if R.target and isElement(R.target) then
        destroyElement(R.target)
    end
    R.target = nil
    if R.source and isElement(R.source) then
        destroyElement(R.source)
    end
    R.source = nil
    R.ok = false
end

function RR.Refl.applyParams()
    if not R.shader then
        return
    end
    local s = SETTINGS
    local st = RR.State
    dxSetShaderValue(R.shader, 'gReflParams', 0.28, 3.0 + 6.0 * (st.wet or 0), 0.35, s.reflectStrength)
    dxSetShaderValue(R.shader, 'gTime', getTickCount() / 1000)
end

--- The reflection texture the road shaders sample.  Falls back to the raw screen source so the
-- road still reflects something if reflection.fx is missing.
function RR.Refl.texture()
    if R.ok and R.target then
        return R.target
    end
    return R.source
end

--- Once per frame: refresh the screen capture and rebuild the reflection target.
function RR.Refl.frame()
    if not R.source then
        return
    end
    dxUpdateScreenSource(R.source)
    if not (R.ok and R.shader and R.target) then
        return
    end
    dxSetShaderValue(R.shader, 'gTime', getTickCount() / 1000)
    dxSetRenderTarget(R.target, true)
    dxDrawImage(0, 0, R.w, R.h, R.shader)
    dxSetRenderTarget()
end

--- The four nearest lit vehicle headlights, as { x, y, z, intensity } records.
-- Called on a timer, not per frame: the road shader keeps the last values between updates.
function RR.Refl.updateLights()
    local cx, cy, cz = getElementPosition(localPlayer)
    local cam = { getCameraMatrix() }
    if cam[1] then
        cx, cy, cz = cam[1], cam[2], cam[3]
    end
    local list = {}
    local vehicles = getElementsByType('vehicle')
    for i = 1, math.min(#vehicles, 60) do
        local v = vehicles[i]
        if isElement(v) then
            local on = false
            local ok, lit = pcall(areVehicleLightsOn, v)
            if ok then
                on = lit and true or false
            end
            if on then
                local m = getElementMatrix(v)
                if m then
                    -- headlight position: forward 2.1 m, sideways 0.7 m, up 0.55 m from the centre
                    local px = m[4][1] + m[1][1] * 2.1 + m[2][1] * 0.7
                    local py = m[4][2] + m[1][2] * 2.1 + m[2][2] * 0.7
                    local pz = m[4][3] + m[1][3] * 2.1 + m[2][3] * 0.7 + 0.55
                    local d = getDistanceBetweenPoints3D(cx, cy, cz, px, py, pz)
                    if d < 90 then
                        list[#list + 1] = { px, py, pz, 2.6 / (1 + d * 0.035), d }
                    end
                end
            end
        end
    end
    table.sort(list, function(a, b) return a[5] < b[5] end)
    for i = 1, 4 do
        R.lights[i] = list[i] or { 0, 0, 0, 0 }
    end
    RR.State.lights = R.lights
    if RR.Shaders then
        RR.Shaders.pushLights()
    end
end

function RR.Refl.start()
    if R.lightTimer and isTimer(R.lightTimer) then
        killTimer(R.lightTimer)
    end
    R.lightTimer = setTimer(function()
        local ok, err = pcall(RR.Refl.updateLights)
        if not ok then
            RR.Warn('light update failed: ' .. tostring(err))
        end
    end, 220, 0)
    RR.Refl.updateLights()
end

function RR.Refl.stop()
    if R.lightTimer and isTimer(R.lightTimer) then
        killTimer(R.lightTimer)
    end
    R.lightTimer = nil
    RR.Refl.teardown()
end
