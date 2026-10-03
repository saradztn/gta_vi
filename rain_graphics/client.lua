-- Client-only rain and wet-road graphics for the ORIGINAL GTA: San Andreas world.
-- This resource does not create, move, replace, or remove map objects/models.

local DEFAULT_INTENSITY = 0.78
local REFLECTION_STRENGTH = 0.16
local SCREEN_CAPTURE_INTERVAL = 100 -- ms; keeps the screen-space sheen inexpensive
local ROAD_SHADER_DISTANCE = 700
local FORCE_RAINY_SKY = true
local RAINY_WEATHER_ID = 8 -- GTA:SA rainy preset; set FORCE_RAINY_SKY=false to keep server weather

-- Intentionally limited to names that look like road/asphalt materials. Edit this list
-- if a custom map uses different texture names. The shader also masks non-horizontal faces.
local ROAD_TEXTURES = {
    "*road*",
    "*asphalt*",
    "*rway*",
}

local enabled = false
local intensity = DEFAULT_INTENSITY
local wetness = 0
local shader = nil
local screenSource = nil
local previousWeather = nil
local lastScreenCapture = 0
local appliedPatterns = {}

local function chat(message)
    outputChatBox("[RainFX] " .. message, 225, 235, 255)
end

local function clamp01(value)
    return math.max(0, math.min(1, value))
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
        outputDebugString("[RainFX] wet_road.fx could not be created: " .. tostring(techniqueOrError), 2)
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
        outputDebugString("[RainFX] No road texture patterns matched. Check ROAD_TEXTURES in client.lua.", 2)
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

    -- This changes only the local client's atmosphere; it never changes the server map.
    if FORCE_RAINY_SKY then
        setWeather(RAINY_WEATHER_ID)
    end
    setRainLevel(intensity)

    local shaderReady = createWetShader()
    if shaderReady then
        chat("rain and wet-road reflections enabled. Use /rainfx off to restore the normal view.")
    else
        chat("rain enabled, but the graphics shader failed to load. See debugscript 3.")
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
    previousWeather = nil
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
        if FORCE_RAINY_SKY and previousWeather ~= nil then
            setWeather(intensity > 0 and RAINY_WEATHER_ID or previousWeather)
        end
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
-- for a subtle, distorted screen-space reflection rather than a fake replacement map.
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
        chat(string.format("%s | intensity %.2f | wetness %.2f | %d road texture patterns", enabled and "on" or "off", intensity, wetness, #appliedPatterns))
    else
        chat("commands: /rainfx [on|off|toggle|status] or /rainfx intensity 0-1")
    end
end)

addEventHandler("onClientResourceStop", resourceRoot, function()
    disableRainFX(false)
end)
