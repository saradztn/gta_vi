-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource
-- -----------------------------------------------------------------------------
-- tools/material_report.lua - turns what the scanner found into a text report and writes it to
-- disk with the client file API.  The file lands in the resource folder of the CLIENT:
--     <MTA>/mods/deathmatch/resources/RoadRealism/road_texture_report.txt
-- which is exactly where you look when you want to extend the whitelist: every texture the game
-- really uses is listed with its material, its tier and the models that reference it.
-- -----------------------------------------------------------------------------
RR = RR or {}
RR.Report = {}

local function line(t, s)
    t[#t + 1] = s or ''
end

--- Build the whole report as a string.
function RR.Report.build()
    local t = {}
    local rt = getRealTime()
    line(t, 'RoadRealism - road texture report')
    line(t, string.format('generated %04d-%02d-%02d %02d:%02d:%02d',
        rt.year + 1900, rt.month + 1, rt.monthday, rt.hour, rt.minute, rt.second))
    line(t, 'client ' .. tostring(getVersion and getVersion().name or 'MTA') .. ' ' ..
        tostring(getVersion and getVersion().number or '') .. ', resource ' .. getResourceName(getThisResource()))
    local sx, sy = guiGetScreenSize()
    line(t, string.format('screen %dx%d, quality preset: %s', sx, sy, tostring(RR.State and RR.State.quality or '?')))
    line(t, string.format('wetness %.2f, rain %.2f, night %.2f, reflection %.2f',
        RR.State and RR.State.wet or 0, RR.State and RR.State.rain or 0,
        RR.State and RR.State.night or 0, RR.State and RR.State.reflection or 0))
    line(t, '')

    local total, road, applied = RR.Scan.count()
    line(t, string.format('textures discovered %d   road related %d   currently replaced %d', total, road, applied))
    line(t, string.format('models inspected %d   pattern matches %d   blacklisted hits %d',
        RR.Scan.stats.models, RR.Scan.stats.patterns, RR.Scan.stats.banned))
    line(t, '')

    -- applied / applicable, grouped by material
    line(t, '==================================================================')
    line(t, ' ROAD MATERIALS IN USE')
    line(t, '==================================================================')
    local groups = RR.Scan.byMaterial()
    local keys = {}
    for k in pairs(groups) do
        keys[#keys + 1] = k
    end
    table.sort(keys)
    for _, k in ipairs(keys) do
        local m = ROAD_MATERIALS[k]
        local g = groups[k]
        table.sort(g, function(a, b) return a.lower < b.lower end)
        line(t, string.format('%-22s %-28s rough %.2f  worldScale %.1f m  marking %s',
            k, m and m.label or '(unknown material)', m and m.rough or 0, m and m.worldScale or 0,
            tostring(g[1].mark or '-')))
        for _, r in ipairs(g) do
            local models = RR.Scan.modelsFor(r.name)
            line(t, string.format('    %-28s tier %-8s replaced %-5s models %s',
                r.name, r.tier, r.applied and 'yes' or 'no', models ~= '' and models or '-'))
        end
        line(t, '')
    end

    line(t, '==================================================================')
    line(t, ' AMBIGUOUS ("review") - apply one with:  /roadapply <name>')
    line(t, '==================================================================')
    local any = false
    for _, lower in ipairs(RR.Scan.order) do
        local r = RR.Scan.found[lower]
        if r.tier == 'review' then
            any = true
            line(t, string.format('    %-28s would use %-20s (%s)', r.name, tostring(r.mat), r.why))
        end
    end
    if not any then
        line(t, '    none')
    end
    line(t, '')

    line(t, '==================================================================')
    line(t, ' BLACKLISTED (matched a road word but must not be touched)')
    line(t, '==================================================================')
    any = false
    for _, lower in ipairs(RR.Scan.order) do
        local r = RR.Scan.found[lower]
        if r.tier == 'banned' then
            any = true
            line(t, string.format('    %-28s %s', r.name, r.why))
        end
    end
    if not any then
        line(t, '    none')
    end
    line(t, '')

    line(t, '==================================================================')
    line(t, string.format(' MATERIAL LIBRARY (%d materials, %d markings)', RR.Count.materials, RR.Count.markings))
    line(t, '==================================================================')
    local mkeys = {}
    for k in pairs(ROAD_MATERIALS) do
        mkeys[#mkeys + 1] = k
    end
    table.sort(mkeys)
    for _, k in ipairs(mkeys) do
        local m = ROAD_MATERIALS[k]
        line(t, string.format('    %-22s %-9s rough %.2f wetRough %.2f f0 %.3f refl %.2f puddle %.2f %s',
            k, m.cat, m.rough, m.wetRough, m.f0, m.reflection, m.puddle, m.label))
        line(t, string.format('        albedo %s', m.albedo))
        line(t, string.format('        mask   %s   (R rough, G ao, B damage, A contamination)', m.mask))
    end
    line(t, '')
    for k, mk in pairs(ROAD_MARKINGS) do
        line(t, string.format('    marking %-20s rough %.2f retro %.2f  %s', k, mk.rough, mk.retro, mk.label))
    end
    line(t, '')
    line(t, 'Shaders:')
    for _, f in ipairs(RR.Order.shaderFiles) do
        local sh = RR.Shaders.get(f)
        line(t, string.format('    %-24s %s', f, sh and ('ok, technique ' .. tostring(sh.tech)) or 'FAILED / not created'))
    end
    line(t, '')
    line(t, 'End of report.')
    return table.concat(t, '\n')
end

--- Write the report into the resource folder.
-- @param filename string (default road_texture_report.txt)
-- @return boolean ok, string filename or error
function RR.Report.save(filename)
    filename = filename or 'road_texture_report.txt'
    local text = RR.Report.build()
    if fileExists(filename) then
        fileDelete(filename)
    end
    local f = fileCreate(filename)
    if not f then
        return false, 'fileCreate failed (is the resource folder writable?)'
    end
    fileWrite(f, text)
    fileClose(f)
    return true, filename, #text
end

--- Print a compact summary to the chat box and the console.
function RR.Report.dump()
    local total, road, applied = RR.Scan.count()
    local groups = RR.Scan.byMaterial()
    local n = 0
    for _ in pairs(groups) do
        n = n + 1
    end
    RR.Say(string.format('textures %d, road related %d, replaced %d, materials in use %d, models %d',
        total, road, applied, n, RR.Scan.stats.models))
    local keys = {}
    for k in pairs(groups) do
        keys[#keys + 1] = k
    end
    table.sort(keys)
    for _, k in ipairs(keys) do
        local names = {}
        for _, r in ipairs(groups[k]) do
            names[#names + 1] = r.name .. (r.applied and '' or ' (?)')
        end
        table.sort(names)
        RR.Say('  ' .. k .. ': ' .. table.concat(names, ', '))
    end
end
