-- bridge.lua — mGBA Lua socket server for The Cooker
--
-- Protocol: pipe-delimited lines over TCP socket (localhost:55234)
-- No JSON library needed; all values are plain text.
--
-- Commands:
--   READ|<addr_hex>|<size>       Read <size> bytes from <addr>
--   KEY|<key_id>|<frames>        Press key for N frames
--   STATE                        Read full game state snapshot
--   FRAMES|<count>               Advance N frames
--   SCREENSHOT|<path>            Save screenshot to path
--   REGISTERS                    Read ARM7 CPU registers
--   CRASHINFO                    Full crash diagnostic dump
--   PALETTE[|BG|OBJ]            Read palette RAM (1024/512 bytes)
--   VRAM_HASH                    Fast hash of VRAM (sampled)
--   SAVESTATE|<slot_or_path>      Save state to slot (0-9) or file path
--   LOADSTATE|<slot_or_path>      Load state from slot (0-9) or file path
--   PING                         Health check
--
-- Debugger commands (mGBA >= 0.11 scripting watchpoint/breakpoint API):
--   CAP                          Report available debugger capabilities
--   WATCHPOINT|<addr>|<type>            Set watchpoint (type: W=write R=read C=change)
--   WATCHPOINT|<min>|<max>|<type>       Set range watchpoint ([min,max) exclusive end)
--   BREAKPOINT|<addr>                   Set an execution breakpoint
--   CLEARBP|<id>                        Clear watchpoint/breakpoint by returned id
--   WATCHHITS[|<max>]                   Drain up to <max> (default 200) captured hits
--   CLEARHITS                           Discard the hit buffer without draining
-- On every watchpoint/breakpoint hit the full ARM register file (r0-r15,cpsr)
-- is captured alongside the access (addr/old/new/accessType). WATCHHITS returns
-- records joined by "@@" and appends |more=<remaining> so the client can page.
--
-- Responses:
--   OK|<data>                    Success with optional data
--   ERR|<message>                Error
--
-- Install: load via mGBA Tools > Scripting > File > Load script
-- Note: uses mGBA's native socket API (NOT LuaSocket)

local LISTEN_PORT = 55234

-- Key constants (match GBA hardware key indices)
local KEY_NAMES = {
    [0] = "A", [1] = "B", [2] = "Select", [3] = "Start",
    [4] = "Right", [5] = "Left", [6] = "Up", [7] = "Down",
    [8] = "R", [9] = "L",
}

-- State
local server = nil
local client = nil
local pending_key = nil       -- {key=N, frames_left=N}
local pending_frames = nil    -- {count=N, callback=string}
local recv_buffer = ""
local peak_frame = 0

-- Debugger state (watchpoints / breakpoints)
local watch_hits = {}            -- ring of captured hit records (strings)
local WATCH_HIT_CAP = 4000       -- hard cap so a runaway watch cannot OOM
local watch_ids = {}             -- id -> {kind="wp"|"bp", label=...} for CLEARBP
-- ARM register names captured on every hit (r15 = PC at the access, r14 = LR).
local REG_NAMES = {
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "cpsr",
}

-- ============================================================================
-- Helpers
-- ============================================================================

local function hex_bytes(data)
    -- Convert binary data to space-separated hex string
    local parts = {}
    for i = 1, #data do
        parts[#parts + 1] = string.format("%02X", string.byte(data, i))
    end
    return table.concat(parts, " ")
end

local function send_response(msg)
    if client then
        client:send(msg .. "\n")
    end
end

local function parse_hex(s)
    return tonumber(s, 16) or tonumber(s)
end

-- ============================================================================
-- Command handlers
-- ============================================================================

local function handle_read(args)
    -- args: "addr_hex|size"
    local addr_str, size_str = args:match("^([^|]+)|([^|]+)$")
    if not addr_str or not size_str then
        return "ERR|READ requires addr|size"
    end
    local addr = parse_hex(addr_str)
    local size = tonumber(size_str)
    if not addr or not size then
        return "ERR|Invalid addr or size"
    end
    if size > 4096 then
        return "ERR|Max read size is 4096"
    end

    -- Read bytes from memory
    local bytes_list = {}
    for i = 0, size - 1 do
        local ok, val = pcall(function() return emu:read8(addr + i) end)
        if ok then
            bytes_list[#bytes_list + 1] = string.format("%02X", val)
        else
            return "ERR|Read failed at " .. string.format("%08X", addr + i)
        end
    end

    return "OK|" .. table.concat(bytes_list, " ")
end

local function handle_write(args)
    -- args: "addr_hex|hex_bytes" (space-separated hex bytes)
    local addr_str, data_str = args:match("^([^|]+)|(.+)$")
    if not addr_str or not data_str then
        return "ERR|WRITE requires addr|hex_bytes"
    end
    local addr = parse_hex(addr_str)
    if not addr then
        return "ERR|Invalid addr"
    end

    -- Parse hex bytes (space-separated or concatenated pairs)
    local bytes = {}
    -- Try space-separated first
    for hex_byte in data_str:gmatch("%x%x") do
        bytes[#bytes + 1] = tonumber(hex_byte, 16)
    end

    if #bytes == 0 then
        return "ERR|No valid hex bytes"
    end
    if #bytes > 4096 then
        return "ERR|Max write size is 4096"
    end

    for i = 1, #bytes do
        local ok, err = pcall(function() emu:write8(addr + i - 1, bytes[i]) end)
        if not ok then
            return "ERR|Write failed at " .. string.format("%08X", addr + i - 1) .. ": " .. tostring(err)
        end
    end

    return "OK|wrote=" .. #bytes
end

local function handle_key(args)
    -- args: "key_id|frames"
    local key_str, frames_str = args:match("^([^|]+)|([^|]+)$")
    if not key_str then
        -- Default: 2 frames
        key_str = args
        frames_str = "2"
    end
    local key_id = tonumber(key_str)
    local frames = tonumber(frames_str) or 2
    if not key_id or not KEY_NAMES[key_id] then
        return "ERR|Invalid key id"
    end

    pending_key = { key = key_id, frames_left = frames }
    return "OK"
end

local function handle_state()
    local frame = emu:currentFrame()

    -- Track peak frame
    if frame > peak_frame then peak_frame = frame end

    -- Read 32-bit values from memory
    local function read32(addr)
        local ok, val = pcall(function() return emu:read32(addr) end)
        return ok and val or 0
    end

    local function read8(addr)
        local ok, val = pcall(function() return emu:read8(addr) end)
        return ok and val or 0
    end

    local pc = read32(0x03007FF4)           -- Approximate: IRQ return address
    local cb1 = read32(0x030022C0)          -- gMain.callback1
    local cb2 = read32(0x030022C4)          -- gMain.callback2
    local fade = read8(0x02037AB8)          -- gPaletteFade active flag
    local map_group = read8(0x02031DBC)
    local map_num = read8(0x02031DBD)

    local parts = {
        "frame=" .. frame,
        "peak=" .. peak_frame,
        "pc=" .. string.format("%08X", pc),
        "cb1=" .. string.format("%08X", cb1),
        "cb2=" .. string.format("%08X", cb2),
        "fade=" .. fade,
        "map=" .. map_group .. "." .. map_num,
    }

    return "OK|" .. table.concat(parts, "|")
end

local function handle_frames(args)
    local count = tonumber(args)
    if not count or count <= 0 then
        return "ERR|FRAMES requires positive count"
    end
    if count > 36000 then  -- 10 minutes at 60fps
        return "ERR|Max 36000 frames"
    end

    pending_frames = { count = count }
    -- Response will be sent after frames complete
    return nil  -- deferred
end

local function handle_keyframes(args)
    -- args: "key_id|frames" — hold key and advance frames atomically
    local key_str, frames_str = args:match("^([^|]+)|([^|]+)$")
    if not key_str or not frames_str then
        return "ERR|KEYFRAMES requires key_id|frames"
    end
    local key_id = tonumber(key_str)
    local frames = tonumber(frames_str)
    if not key_id or not KEY_NAMES[key_id] then
        return "ERR|Invalid key id"
    end
    if not frames or frames <= 0 then
        return "ERR|KEYFRAMES requires positive frames"
    end
    if frames > 36000 then
        return "ERR|Max 36000 frames"
    end

    pending_key = { key = key_id, frames_left = frames }
    pending_frames = { count = frames }
    return nil  -- deferred
end

local function handle_screenshot(args)
    local path = args
    if not path or path == "" then
        return "ERR|SCREENSHOT requires path"
    end

    local ok, err = pcall(function()
        emu:screenshot(path)
    end)

    if ok then
        return "OK"
    else
        return "ERR|Screenshot failed: " .. tostring(err)
    end
end

local function handle_ping()
    return "OK|pong"
end

local function handle_registers()
    -- Try mGBA 0.10+ emu:readRegister() API first
    local use_api = false
    if emu.readRegister then
        local ok, _ = pcall(function() return emu:readRegister("r0") end)
        use_api = ok
    end

    local reg_names = {
        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
        "cpsr", "spsr",
    }

    local parts = {}

    if use_api then
        for _, name in ipairs(reg_names) do
            local ok, val = pcall(function() return emu:readRegister(name) end)
            if ok and val then
                parts[#parts + 1] = name .. "=" .. string.format("%08X", val)
            end
        end
    else
        -- Fallback: read from IWRAM (IRQ-saved registers)
        local function read32(addr)
            local ok, val = pcall(function() return emu:read32(addr) end)
            return ok and val or 0
        end

        -- 0x03007FF4 = IRQ return address (approximate PC)
        -- gMain struct at 0x030022C0 has callback1/callback2
        -- SP is typically around 0x03007E00-0x03007F00
        parts[#parts + 1] = "r13=" .. string.format("%08X", read32(0x03007F00))  -- SP approx
        parts[#parts + 1] = "r14=" .. string.format("%08X", read32(0x03007FF0))  -- LR approx
        parts[#parts + 1] = "r15=" .. string.format("%08X", read32(0x03007FF4))  -- PC from IRQ
        parts[#parts + 1] = "cpsr=" .. string.format("%08X", read32(0x03007FF8)) -- SPSR saved
        parts[#parts + 1] = "fallback=1"
    end

    if #parts == 0 then
        return "ERR|No registers readable"
    end
    return "OK|" .. table.concat(parts, "|")
end

local function handle_crashinfo()
    -- Collect all diagnostic info in one call
    local function read32(addr)
        local ok, val = pcall(function() return emu:read32(addr) end)
        return ok and val or 0
    end
    local function read8(addr)
        local ok, val = pcall(function() return emu:read8(addr) end)
        return ok and val or 0
    end

    -- Get registers (reuse handler, parse the result)
    local reg_resp = handle_registers()
    local regs_str = ""
    if reg_resp:sub(1, 3) == "OK|" then
        regs_str = reg_resp:sub(4)
    end

    -- Parse PC, LR, SP from register data
    local pc_val = "00000000"
    local lr_val = "00000000"
    local sp_val = "00000000"
    for part in regs_str:gmatch("[^|]+") do
        local k, v = part:match("^(%w+)=(.+)$")
        if k == "r15" then pc_val = v
        elseif k == "r14" then lr_val = v
        elseif k == "r13" then sp_val = v
        end
    end

    -- Read stack: 64 bytes from SP
    local sp_num = tonumber(sp_val, 16) or 0x03007E00
    local stack_hex = {}
    if sp_num >= 0x03000000 and sp_num < 0x03008000 then
        local bytes_to_read = math.min(64, 0x03008000 - sp_num)
        for i = 0, bytes_to_read - 1 do
            stack_hex[#stack_hex + 1] = string.format("%02X", read8(sp_num + i))
        end
    end

    -- Callbacks
    local cb1 = read32(0x030022C0)
    local cb2 = read32(0x030022C4)

    -- Frame
    local frame = emu:currentFrame()

    local parts = {
        "pc=" .. pc_val,
        "lr=" .. lr_val,
        "sp=" .. sp_val,
        "regs=" .. regs_str:gsub("|", ","),  -- comma-separate for sub-field
        "stack=" .. table.concat(stack_hex, ""),
        "cb1=" .. string.format("%08X", cb1),
        "cb2=" .. string.format("%08X", cb2),
        "frame=" .. frame,
    }

    return "OK|" .. table.concat(parts, "|")
end

local function handle_watchdog()
    local frame = emu:currentFrame()
    if frame > peak_frame then peak_frame = frame end

    local rebooted = 0
    if peak_frame > 0 and frame < peak_frame then
        rebooted = 1
    end

    local parts = {
        "frame=" .. frame,
        "peak=" .. peak_frame,
        "rebooted=" .. rebooted,
    }

    return "OK|" .. table.concat(parts, "|")
end

local function handle_palette(args)
    -- Read palette RAM (0x05000000).
    -- args: "" (full 1024 bytes) or "BG" (first 512) or "OBJ" (last 512)
    local base = 0x05000000
    local size = 1024
    if args == "BG" then
        size = 512
    elseif args == "OBJ" then
        base = 0x05000200
        size = 512
    end

    local bytes_list = {}
    for i = 0, size - 1 do
        local ok, val = pcall(function() return emu:read8(base + i) end)
        if ok then
            bytes_list[#bytes_list + 1] = string.format("%02X", val)
        else
            return "ERR|Palette read failed at " .. string.format("%08X", base + i)
        end
    end

    return "OK|" .. table.concat(bytes_list, " ")
end

local function handle_vram_hash()
    -- Fast hash of VRAM (96KB at 0x06000000), sampling every 4th byte.
    -- Uses djb2 hash for speed.
    local base = 0x06000000
    local vram_size = 96 * 1024
    local hash = 5381

    for i = 0, vram_size - 1, 4 do
        local ok, val = pcall(function() return emu:read8(base + i) end)
        if ok then
            -- djb2: hash = hash * 33 + val
            hash = ((hash * 33) + val) % 0x100000000
        end
    end

    return "OK|hash=" .. string.format("%08X", hash)
end

local function handle_savestate(args)
    if not args or args == "" then
        return "ERR|SAVESTATE requires slot (0-9) or file path"
    end

    local slot = tonumber(args)
    if slot then
        if slot < 0 or slot > 9 then
            return "ERR|Slot must be 0-9"
        end
        local ok, err = pcall(function() emu:saveStateSlot(slot) end)
        if ok then
            return "OK|slot=" .. slot
        else
            return "ERR|Save failed: " .. tostring(err)
        end
    else
        -- File path
        local ok, err = pcall(function() emu:saveStateFile(args) end)
        if ok then
            return "OK|path=" .. args
        else
            return "ERR|Save failed: " .. tostring(err)
        end
    end
end

local function handle_loadstate(args)
    if not args or args == "" then
        return "ERR|LOADSTATE requires slot (0-9) or file path"
    end

    local slot = tonumber(args)
    if slot then
        if slot < 0 or slot > 9 then
            return "ERR|Slot must be 0-9"
        end
        local ok, err = pcall(function() emu:loadStateSlot(slot) end)
        if ok then
            -- Reset peak_frame to current frame after load to avoid false reboot detection
            peak_frame = emu:currentFrame()
            return "OK|slot=" .. slot
        else
            return "ERR|Load failed: " .. tostring(err)
        end
    else
        -- File path
        local ok, err = pcall(function() emu:loadStateFile(args) end)
        if ok then
            peak_frame = emu:currentFrame()
            return "OK|path=" .. args
        else
            return "ERR|Load failed: " .. tostring(err)
        end
    end
end

-- ============================================================================
-- Debugger: watchpoints / breakpoints (mGBA >= 0.11 scripting API)
-- ============================================================================

-- Resolve a watchpoint type letter (W/R/C) to the emulator's enum value.
-- Prefer the exported constants table (C.WATCHPOINT_TYPE.*); fall back to the
-- fixed enum from mgba/debugger/debugger.h (WRITE=1, READ=2, WRITE_CHANGE=5).
local function resolve_wp_type(letter)
    letter = (letter or "W"):upper()
    local names = { W = "WRITE", R = "READ", C = "WRITE_CHANGE" }
    local nums  = { W = 1, R = 2, C = 5 }
    local name = names[letter]
    if not name then return nil end
    -- luacheck: globals C
    if C and C.WATCHPOINT_TYPE and C.WATCHPOINT_TYPE[name] ~= nil then
        return C.WATCHPOINT_TYPE[name]
    end
    return nums[letter]
end

local function capture_registers()
    local parts = {}
    for _, n in ipairs(REG_NAMES) do
        local ok, v = pcall(function() return emu:readRegister(n) end)
        parts[#parts + 1] = n .. "=" .. string.format("%08X", (ok and v) or 0)
    end
    return table.concat(parts, ",")
end

-- Build a hit-capture callback. Buffers a single-line record per hit; never
-- touches the socket (fires mid-frame on the CPU thread).
local function make_hit_cb(kind, label)
    return function(info)
        if #watch_hits >= WATCH_HIT_CAP then return end
        local addr = tonumber(info and info.address) or 0
        local acc  = tonumber(info and info.accessType) or 0
        local oldv = tonumber(info and info.oldValue) or 0
        local newv = tonumber(info and info.newValue) or 0
        local width = tonumber(info and info.width) or 0
        local frame = 0
        pcall(function() frame = emu:currentFrame() end)
        watch_hits[#watch_hits + 1] = string.format(
            "kind=%s,label=%s,f=%d,addr=%08X,width=%d,acc=%d,old=%08X,new=%08X,%s",
            kind, label, frame, addr, width, acc, oldv, newv, capture_registers())
    end
end

local function debugger_available()
    return emu ~= nil and type(emu.setWatchpoint) == "function"
        and type(emu.setBreakpoint) == "function"
end

local function handle_cap()
    local wp = (emu and type(emu.setWatchpoint) == "function") and 1 or 0
    local bp = (emu and type(emu.setBreakpoint) == "function") and 1 or 0
    local rwp = (emu and type(emu.setRangeWatchpoint) == "function") and 1 or 0
    local rr = (emu and type(emu.readRegister) == "function") and 1 or 0
    return string.format("OK|setWatchpoint=%d|setRangeWatchpoint=%d|setBreakpoint=%d|readRegister=%d",
        wp, rwp, bp, rr)
end

local function handle_watchpoint(args)
    if not debugger_available() then
        return "ERR|Watchpoints unsupported by this mGBA build (need >= 0.11 scripting)"
    end
    -- args: "addr|type"  OR  "min|max|type"
    local a, b, c = args:match("^([^|]+)|([^|]+)|([^|]+)$")
    local id, err
    if a then
        local mn = parse_hex(a)
        local mx = parse_hex(b)
        local t = resolve_wp_type(c)
        if not mn or not mx or not t then return "ERR|WATCHPOINT bad range/type" end
        if not emu.setRangeWatchpoint then return "ERR|setRangeWatchpoint unsupported" end
        local label = string.format("%08X-%08X:%s", mn, mx, c:upper())
        local cb = make_hit_cb("wp", label)
        local ok, res = pcall(function() return emu:setRangeWatchpoint(cb, mn, mx, t) end)
        if not ok then return "ERR|setRangeWatchpoint failed: " .. tostring(res) end
        id = res
    else
        local addr_str, type_str = args:match("^([^|]+)|([^|]+)$")
        if not addr_str then
            addr_str, type_str = args, "W"
        end
        local addr = parse_hex(addr_str)
        local t = resolve_wp_type(type_str)
        if not addr or not t then return "ERR|WATCHPOINT bad addr/type" end
        local label = string.format("%08X:%s", addr, type_str:upper())
        local cb = make_hit_cb("wp", label)
        local ok, res = pcall(function() return emu:setWatchpoint(cb, addr, t) end)
        if not ok then return "ERR|setWatchpoint failed: " .. tostring(res) end
        id = res
    end
    if id == nil then return "ERR|setWatchpoint returned nil id" end
    watch_ids[id] = { kind = "wp" }
    return "OK|id=" .. tostring(id)
end

local function handle_breakpoint(args)
    if not debugger_available() then
        return "ERR|Breakpoints unsupported by this mGBA build (need >= 0.11 scripting)"
    end
    local addr = parse_hex(args)
    if not addr then return "ERR|BREAKPOINT requires addr" end
    local label = string.format("bp@%08X", addr)
    local cb = make_hit_cb("bp", label)
    local ok, res = pcall(function() return emu:setBreakpoint(cb, addr) end)
    if not ok then return "ERR|setBreakpoint failed: " .. tostring(res) end
    if res == nil then return "ERR|setBreakpoint returned nil id" end
    watch_ids[res] = { kind = "bp" }
    return "OK|id=" .. tostring(res)
end

local function handle_clearbp(args)
    if not emu or type(emu.clearBreakpoint) ~= "function" then
        return "ERR|clearBreakpoint unsupported"
    end
    local id = tonumber(args)
    if id == nil then return "ERR|CLEARBP requires numeric id" end
    local ok, err = pcall(function() emu:clearBreakpoint(id) end)
    if not ok then return "ERR|clearBreakpoint failed: " .. tostring(err) end
    watch_ids[id] = nil
    return "OK|cleared=" .. id
end

local function handle_watchhits(args)
    local max = tonumber(args) or 200
    if max <= 0 then max = 200 end
    local n = math.min(max, #watch_hits)
    if n == 0 then
        return "OK||more=0"
    end
    local out = {}
    for i = 1, n do out[i] = watch_hits[i] end
    -- Drop the drained prefix.
    local rest = {}
    for i = n + 1, #watch_hits do rest[#rest + 1] = watch_hits[i] end
    watch_hits = rest
    return "OK|" .. table.concat(out, "@@") .. "|more=" .. #watch_hits
end

local function handle_clearhits()
    local n = #watch_hits
    watch_hits = {}
    return "OK|dropped=" .. n
end

-- ============================================================================
-- Command dispatcher
-- ============================================================================

local HANDLERS = {
    READ = handle_read,
    WRITE = handle_write,
    KEY = handle_key,
    KEYFRAMES = handle_keyframes,
    STATE = handle_state,
    FRAMES = handle_frames,
    SCREENSHOT = handle_screenshot,
    REGISTERS = handle_registers,
    CRASHINFO = handle_crashinfo,
    WATCHDOG = handle_watchdog,
    PALETTE = handle_palette,
    VRAM_HASH = handle_vram_hash,
    SAVESTATE = handle_savestate,
    LOADSTATE = handle_loadstate,
    PING = handle_ping,
    CAP = handle_cap,
    WATCHPOINT = handle_watchpoint,
    BREAKPOINT = handle_breakpoint,
    CLEARBP = handle_clearbp,
    WATCHHITS = handle_watchhits,
    CLEARHITS = handle_clearhits,
}

local function process_command(line)
    line = line:gsub("%s+$", "")  -- trim trailing whitespace/newline
    if line == "" then return end

    -- Split command from args: "CMD|args..."
    local cmd, args = line:match("^([^|]+)|?(.*)$")
    cmd = cmd:upper()

    local handler = HANDLERS[cmd]
    if not handler then
        send_response("ERR|Unknown command: " .. cmd)
        return
    end

    local response = handler(args)
    if response then
        send_response(response)
    end
    -- nil response means deferred (e.g., FRAMES)
end

-- ============================================================================
-- Socket management (mGBA native event-based socket API)
-- ============================================================================

local function on_client_received()
    if not client then return end
    while true do
        local data, err = client:receive(4096)
        if data then
            recv_buffer = recv_buffer .. data
            -- Process complete lines
            while true do
                local nl = recv_buffer:find("\n")
                if not nl then break end
                local line = recv_buffer:sub(1, nl - 1)
                recv_buffer = recv_buffer:sub(nl + 1)
                process_command(line)
            end
        else
            if err ~= socket.ERRORS.AGAIN then
                console:log("bridge.lua: client disconnected")
                client:close()
                client = nil
                recv_buffer = ""
            end
            return
        end
    end
end

local function on_client_error()
    console:log("bridge.lua: client error")
    if client then
        client:close()
        client = nil
        recv_buffer = ""
    end
end

local function on_accept()
    local sock, err = server:accept()
    if err then
        console:error("bridge.lua: accept error: " .. tostring(err))
        return
    end
    -- Close previous client if any
    if client then
        client:close()
        client = nil
        recv_buffer = ""
    end
    client = sock
    recv_buffer = ""
    client:add("received", on_client_received)
    client:add("error", on_client_error)
    console:log("bridge.lua: client connected")
end

local function setup_server()
    if not socket then
        console:error("bridge.lua: socket library not available")
        return false
    end

    local err
    server, err = socket.bind(nil, LISTEN_PORT)
    if err then
        console:error("bridge.lua: failed to bind: " .. tostring(err))
        return false
    end

    local ok
    ok, err = server:listen()
    if err then
        server:close()
        console:error("bridge.lua: failed to listen: " .. tostring(err))
        return false
    end

    -- Event-based accept: mGBA fires "received" on server when a client connects
    server:add("received", on_accept)
    console:log("bridge.lua: listening on port " .. LISTEN_PORT)
    return true
end

-- ============================================================================
-- Frame callback (runs every frame)
-- ============================================================================

local function on_frame()
    -- Handle pending key presses
    if pending_key then
        emu:addKey(pending_key.key)
        pending_key.frames_left = pending_key.frames_left - 1
        if pending_key.frames_left <= 0 then
            emu:clearKey(pending_key.key)
            pending_key = nil
        end
    end

    -- Handle pending frame advance
    if pending_frames then
        pending_frames.count = pending_frames.count - 1
        if pending_frames.count <= 0 then
            local frame = emu:currentFrame()
            send_response("OK|frame=" .. frame)
            pending_frames = nil
        end
    end
end

-- ============================================================================
-- Initialization
-- ============================================================================

if setup_server() then
    callbacks:add("frame", on_frame)
    console:log("bridge.lua: Cooker bridge active")
else
    console:error("bridge.lua: failed to initialize")
end
