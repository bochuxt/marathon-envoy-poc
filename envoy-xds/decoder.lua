JSON = (loadfile "/var/lib/lua/JSON.lua")() -- one-time load of the routines
uuid = (loadfile "/var/lib/lua/uuid.lua")() -- one-time load of the routines
function envoy_on_request(request_handle)
  function urldecode(s)
    s = s:gsub('+', ' ')
        :gsub('%%(%x%x)', function(h)
                            return string.char(tonumber(h, 16))
                          end)
    return s
  end
  function parseurl(s)
    local ans = {}
    for k,v in s:gmatch('([^&=?]-)=([^&=?]+)' ) do
      ans[ k ] = urldecode(v)
    end
    return ans
  end
  local headers = request_handle:headers()
  local path = headers:get(":path")
  local method = headers:get(":method")
  local query_params = parseurl(path)
  local content_type = headers:get("content-type")
  local locale = headers:get("locale")
  local brand = headers:get("brand")
  local systemid = headers:get("systemid")
  local correlationid = headers:get("correlationid")
  local xforwardedfor = headers:get("x-forwarded-for")
  local lua_value = {}

  if content_type == "application/json" then
    request_handle:logDebug("******* The body is application json")
    local body = request_handle:body()
    local body_size = body:length()
    local body_bytes = body:getBytes(0, body_size)
    local raw_json_text = tostring(body_bytes)
    lua_value = JSON:decode(raw_json_text) -- decode example
  end
  if locale == nil then
    if query_params["locale"] ~= nil then
      request_handle:headers():replace("locale",query_params["locale"])
    else
      if lua_value.locale ~= nil then
        request_handle:headers():replace("locale",lua_value.locale)
      end
    end
  end
  if  brand == nil then
    if query_params["brand"] ~= nil then
      request_handle:headers():replace("brand",query_params["brand"])
    else
      if lua_value.brand ~= nil then
        request_handle:headers():replace("brand",lua_value.brand)
      end
    end
  end
  if systemid == nil then
    if query_params["systemid"] ~= nil then
      request_handle:headers():replace("systemid",query_params["systemid"])
    else
      if lua_value.systemid ~= nil then
        request_handle:headers():replace("systemid",lua_value.systemid)
      end
    end
  end
  if correlationid == nil then
    if method == "GET" or method == "DELETE" then
      if query_params["correlationid"] ~= nil then
        request_handle:headers():replace("correlationid",query_params["correlationid"])
      end
    else
      if lua_value.correlationid ~= nil then
        request_handle:headers():replace("correlationid",lua_value.correlationid)
      else
        -- generate a new "correlationid"
        request_handle:headers():replace("correlationid","GEN-"..uuid())
      end
    end
  end
end
