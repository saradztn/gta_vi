-- Server-side visit and room navigation. Scene geometry is client-local and does not replace GTA map assets.
local returnState = {}

local function tell(player, text, r, g, b)
    outputChatBox("[Royal Citadel] " .. text, player, r or 232, g or 222, b or 205, true)
end

local function remember(player)
    if returnState[player] then return end
    local x, y, z = getElementPosition(player)
    local rx, ry, rz = getElementRotation(player)
    returnState[player] = {
        x=x, y=y, z=z, rx=rx, ry=ry, rz=rz,
        interior=getElementInterior(player), dimension=getElementDimension(player)
    }
end

local function moveTo(player, x, y, z, rz, message)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    remember(player)
    setElementInterior(player, 0)
    setElementDimension(player, 0)
    setElementPosition(player, RC_WORLD.x + x, RC_WORLD.y + y, RC_WORLD.z + z)
    setElementRotation(player, 0, 0, rz or 0)
    if message then tell(player, message, 235, 220, 174) end
end

addCommandHandler("royalcastle", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    moveTo(player, RC_START.x, RC_START.y, RC_START.z, RC_START.rz,
        "Welcome to the royal court. The Great Hall is ahead; use /royalenter for direct entry. /royalexit returns you.")
end)

addCommandHandler("royalenter", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    local room = RC_ROOMS and RC_ROOMS[1]
    if not room then tell(player, "Room layout is unavailable.", 255, 150, 90) return end
    moveTo(player, room.x, room.y, room.z, room.rz, "Entered the Great Hall. Use /royalrooms to browse the palace.")
end)

addCommandHandler("royalrooms", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    tell(player, "Accessible rooms (use /royalroom <id>):")
    for _, room in ipairs(RC_ROOMS or {}) do
        tell(player, "  " .. room.id .. " — " .. room.name, 218, 218, 204)
    end
end)

addCommandHandler("royalroom", function(player, _, roomId)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    if not roomId then tell(player, "Usage: /royalroom <id>   (see /royalrooms)", 255, 190, 110) return end
    local wanted = string.lower(roomId)
    for _, room in ipairs(RC_ROOMS or {}) do
        if string.lower(room.id) == wanted then
            moveTo(player, room.x, room.y, room.z, room.rz, "Room: " .. room.name .. ". /royalexit returns to your saved location.")
            return
        end
    end
    tell(player, "Unknown room. Use /royalrooms for the room list.", 255, 160, 110)
end)

addCommandHandler("royalexit", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    local saved = returnState[player]
    if not saved then
        tell(player, "No saved visit position. Use /royalcastle first.", 255, 180, 100)
        return
    end
    setElementInterior(player, saved.interior)
    setElementDimension(player, saved.dimension)
    setElementPosition(player, saved.x, saved.y, saved.z)
    setElementRotation(player, saved.rx, saved.ry, saved.rz)
    returnState[player] = nil
    tell(player, "Returned to your previous position.")
end)

addEventHandler("onPlayerQuit", root, function() returnState[source] = nil end)
