-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- server.lua - optional.  RoadRealism is a purely client side graphics resource and works with no
-- server script at all; this file only exists so an admin can drive the rain and the reload for
-- every player at once instead of typing the command on each client.
--
--     /roadrain <0-1>      set the rain (and therefore the wet road) for everybody
--     /roadrain off        stop the rain, the roads dry out on their own
--     /roadreloadall       make every client rebuild its shaders and textures
-- -----------------------------------------------------------------------------
local ADMIN_ONLY = true
local lastRain = 0.0

local function allowed(player)
    if not ADMIN_ONLY then
        return true
    end
    local account = getPlayerAccount(player)
    if not account or isGuestAccount(account) then
        return false
    end
    return hasObjectPermissionTo(getAccountName(account), 'function.setWeather', false)
end

local function reply(player, msg)
    outputChatBox('#7ec8ff[RoadRealism]#ffffff ' .. msg, player, 255, 255, 255, true)
end

local function cmdRain(player, cmd, level)
    if not allowed(player) then
        -- not an admin: the client-side command already applied the rain locally, so stay quiet
        return
    end
    if not level or string.lower(level) == 'off' then
        lastRain = 0.0
        triggerClientEvent(root, 'RoadRealism:setRain', resourceRoot, 0.0)
        reply(player, 'rain stopped for everyone - the roads will dry out')
        return
    end
    local v = tonumber(level)
    if not v then
        reply(player, 'usage: /roadrain 0-1 (or "off")')
        return
    end
    v = math.max(0, math.min(1, v))
    lastRain = v
    triggerClientEvent(root, 'RoadRealism:setRain', resourceRoot, v)
    reply(player, string.format('rain set to %.2f for everyone', v))
    outputServerLog(string.format('RoadRealism: %s set the rain to %.2f', getPlayerName(player), v))
end

local function cmdReloadAll(player)
    if not allowed(player) then
        reply(player, 'you are not allowed to reload the resource')
        return
    end
    triggerClientEvent(root, 'RoadRealism:reload', resourceRoot)
    reply(player, 'asked every client to reload the road shaders and textures')
end

addCommandHandler('roadrain', cmdRain)
addCommandHandler('roadreloadall', cmdReloadAll)

-- a joining player gets the rain the server is currently running
addEventHandler('onPlayerJoin', root, function()
    if lastRain > 0 then
        triggerClientEvent(source, 'RoadRealism:setRain', resourceRoot, lastRain)
    end
end)

addEventHandler('onResourceStart', resourceRoot, function()
    outputServerLog('RoadRealism: client side road overhaul loaded - /roadrain <0-1> on the server ' ..
                    'drives the rain for everybody')
end)
