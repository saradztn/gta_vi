-- Client-only rain and wet-road graphics for the ORIGINAL GTA: San Andreas world.
-- This resource does not create, move, replace, or remove map objects/models.

local DEFAULT_INTENSITY = 0.78
local REFLECTION_STRENGTH = 0.48
local SCREEN_CAPTURE_INTERVAL = 100 -- ms; keeps the screen-space sheen inexpensive
local ROAD_SHADER_DISTANCE = 700
local FORCE_RAINY_SKY = true
local RAINY_WEATHER_ID = 8 -- GTA:SA rainy preset; set FORCE_RAINY_SKY=false to keep server weather
local FORCE_NIGHT = true
local NIGHT_HOUR = 0
local NIGHT_MINUTE = 30 -- NightCity's neon/reflection look is most visible after dark

-- GTA:SA uses many area-specific texture names, so bind once to the world wildcard.
-- Generated normals in the shader restrict the visible effect to upward-facing
-- surfaces near the player (roads, pavements and flat roofs).
local ROAD_TEXTURES = {
    "*",
}

local enabled = false
local intensity = DEFAULT_INTENSITY
local wetness = 0
local shader = nil
local screenSource = nil
local previousWeather = nil
local previousHour = nil
local previousMinute = nil
local lastScreenCapture = 0
local appliedPatterns = {}

local function chat(message)
    outputChatBox("[RainFX] " .. message, 225, 235, 255)
end

local function clamp01(value)
    return math.max(0, math.min(1, value))
end

local function applyLocalAtmosphere()
    if intensity > 0 then
        if FORCE_RAINY_SKY then
            setWeather(RAINY_WEATHER_ID)
        end
        if FORCE_NIGHT then
            setTime(NIGHT_HOUR, NIGHT_MINUTE)
        end
    else
        if FORCE_RAINY_SKY and previousWeather ~= nil then
            setWeather(previousWeather)
        end
        if FORCE_NIGHT and previousHour ~= nil then
            setTime(previousHour, previousMinute or 0)
        end
    end
end

local function destroyWetShader()
    if isElement(shader) then
        for _, textureName in ipairs(appliedPatterns) do
            engineRemoveShaderFromWorldTexture(shader, textureName)
        end
        destroyElement(shader)
    end
    shader = nil
    appliedPatterns = {}

    if isElement(screenSource) then
        destroyElement(screenSource)
    end
    screenSource = nil
end

local function createWetShader()
    local createdShader, techniqueOrError = dxCreateShader(
        "wet_road.fx", 5, ROAD_SHADER_DISTANCE, false, "world"
    )

    if not isElement(createdShader) then
        outputDebugString("[RainFX] wet_road.fx could not be created: " .. tostring(techniqueOrError or "shader compilation failed or is unsupported"), 2)
        return false
    end

    shader = createdShader
    local screenWidth, screenHeight = guiGetScreenSize()
    screenSource = dxCreateScreenSource(screenWidth, screenHeight)

    if isElement(screenSource) then
        dxSetShaderValue(shader, "gScreenSource", screenSource)
        dxSetShaderValue(shader, "uScreenValid", 1)
    else
        -- The rain still works and the shader falls back to a wet specular sheen.
        dxSetShaderValue(shader, "uScreenValid", 0)
        outputDebugString("[RainFX] Screen source unavailable; using the wet-surface fallback.", 2)
    end

    dxSetShaderValue(shader, "uWetness", wetness)
    dxSetShaderValue(shader, "uReflectionStrength", REFLECTION_STRENGTH)
    dxSetShaderValue(shader, "uTime", getTickCount() / 1000)

    for _, textureName in ipairs(ROAD_TEXTURES) do
        if engineApplyShaderToWorldTexture(shader, textureName) then
            appliedPatterns[#appliedPatterns + 1] = textureName
        end
    end

    if #appliedPatterns == 0 then
        outputDebugString("[RainFX] Shader loaded, but MTA rejected the world texture wildcard.", 2)
    end

    return true
end

local function enableRainFX()
    if enabled then
        return
    end

    enabled = true
    wetness = 0
    previousWeather = getWeather()
    previousHour, previousMinute = getTime()

    -- These alter only the local client's atmosphere/time; the server map is untouched.
    applyLocalAtmosphere()
    setRainLevel(intensity)

    local shaderReady = createWetShader()
    if shaderReady and #appliedPatterns > 0 then
        chat(string.format("rain, midnight and wet-road reflections enabled (%d world texture binding).", #appliedPatterns))
    elseif shaderReady then
        chat("rain enabled, but the world shader did not bind to any texture. Check debugscript 3.")
    else
        chat("rain enabled, but the graphics shader failed to load. Check debugscript 3.")
    end
end

local function disableRainFX(showMessage)
    if not enabled then
        return
    end

    enabled = false
    destroyWetShader()
    resetRainLevel()

    if FORCE_RAINY_SKY and previousWeather ~= nil then
        setWeather(previousWeather)
    end
    if FORCE_NIGHT and previousHour ~= nil then
        setTime(previousHour, previousMinute or 0)
    end
    previousWeather = nil
    previousHour = nil
    previousMinute = nil
    wetness = 0

    if showMessage then
        chat("disabled; the original weather and world textures are restored.")
    end
end

local function setIntensity(value)
    local parsed = tonumber(value)
    if not parsed then
        chat("usage: /rainfx intensity 0-1")
        return
    end

    intensity = clamp01(parsed)
    if enabled then
        setRainLevel(intensity)
        applyLocalAtmosphere()
    end
    chat(string.format("intensity set to %.2f", intensity))
end

addEventHandler("onClientResourceStart", resourceRoot, function()
    enableRainFX()
end)

addEventHandler("onClientPreRender", root, function(timeSlice)
    if not enabled then
        return
    end

    local elapsed = math.min(tonumber(timeSlice) or 16, 100)
    local targetWetness = intensity
    local rate = (wetness < targetWetness) and 0.00022 or 0.000035
    local step = elapsed * rate

    if wetness < targetWetness then
        wetness = math.min(targetWetness, wetness + step)
    else
        wetness = math.max(targetWetness, wetness - step)
    end

    if isElement(shader) then
        dxSetShaderValue(shader, "uWetness", wetness)
        dxSetShaderValue(shader, "uTime", getTickCount() / 1000)
    end
end)

-- Capture after the world has rendered; the shader uses this previous-frame image
-- for its distorted screen-space reflection.
addEventHandler("onClientHUDRender", root, function()
    if not enabled or not isElement(screenSource) then
        return
    end

    local now = getTickCount()
    if now - lastScreenCapture >= SCREEN_CAPTURE_INTERVAL then
        dxUpdateScreenSource(screenSource, true)
        lastScreenCapture = now
    end
end)

addCommandHandler("rainfx", function(_, action, value)
    action = action and string.lower(action) or "toggle"

    if action == "on" then
        enableRainFX()
    elseif action == "off" then
        disableRainFX(true)
    elseif action == "toggle" then
        if enabled then
            disableRainFX(true)
        else
            enableRainFX()
        end
    elseif action == "intensity" then
        setIntensity(value)
    elseif action == "status" then
        chat(string.format("%s | shader %s | screen source %s | intensity %.2f | wetness %.2f | bindings %d", enabled and "on" or "off", isElement(shader) and "ready" or "off", isElement(screenSource) and "ready" or "fallback", intensity, wetness, #appliedPatterns))
    else
        chat("commands: /rainfx [on|off|toggle|status] or /rainfx intensity 0-1")
    end
end)

addEventHandler("onClientResourceStop", resourceRoot, function()
    disableRainFX(false)
end)
