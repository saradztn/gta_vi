-- Server-side visit/return commands. The generated scene is client-local, so this
-- script only teleports the requesting player and never modifies world resources.
local WORLD_X, WORLD_Y, WORLD_Z = 2500.0, 2500.0, 0.0
local START_X, START_Y, START_Z = 0.0, -49.0, 64.0
local returnState = {}

local function tell(player, text, r, g, b)
    outputChatBox("[Royal Citadel] " .. text, player, r or 232, g or 222, b or 205, true)
end

addCommandHandler("royalcastle", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    if not returnState[player] then
        local x,y,z=getElementPosition(player)
        local rx,ry,rz=getElementRotation(player)
        returnState[player]={x=x,y=y,z=z,rx=rx,ry=ry,rz=rz,
                             interior=getElementInterior(player),dimension=getElementDimension(player)}
    end
    setElementInterior(player,0)
    setElementDimension(player,0)
    setElementPosition(player,WORLD_X+START_X,WORLD_Y+START_Y,WORLD_Z+START_Z)
    setElementRotation(player,0,0,0)
    tell(player,"Welcome to the Royal Citadel. Use /royalexit to return to your previous position.",235,220,174)
end)

addCommandHandler("royalexit", function(player)
    if not isElement(player) or getElementType(player) ~= "player" then return end
    local saved=returnState[player]
    if not saved then
        tell(player,"No saved visit position. Use /royalcastle first.",255,180,100)
        return
    end
    setElementInterior(player,saved.interior)
    setElementDimension(player,saved.dimension)
    setElementPosition(player,saved.x,saved.y,saved.z)
    setElementRotation(player,saved.rx,saved.ry,saved.rz)
    returnState[player]=nil
    tell(player,"Returned to your previous position.")
end)

addEventHandler("onPlayerQuit",root,function() returnState[source]=nil end)
