# import AccessLog from envoy

def AccessLog(path):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/filter/accesslog/accesslog.proto.html#envoy-api-msg-filter-accesslog-accesslog
    return {
        "name": "envoy.file_access_log",
        # TODO: Support filters
        # "filter": filter,
        "config": {
            "path": path,
            # "format": "..."
        }
    }

http_filters=[
 
            {
                "name": "envoy.filters.http.lua",
                "typed_config": {
                                    "@type": "type.googleapis.com/envoy.config.filter.http.lua.v2.Lua",
                                    "inline_code": "\n\nfunction envoy_on_request(request_handle)\n\n\n  local message=\"=========AAAAABBBBCCCCC============\"\n  request_handle:logTrace(message..' [req]trace')\n  request_handle:logDebug(message..' [req]Debug')\n  request_handle:logInfo(message..' [req]Info')\n  request_handle:logWarn(message..' [req]Warn')\n  request_handle:logErr(message..' [req]Err')\n  request_handle:logCritical(message..'Critical')\n\n  request_handle:headers():add(\"foo----req-\",\"bar-2020\")\nend\nfunction envoy_on_response(response_handle)\n  local message1=\"=========response called============\"\n  response_handle:logTrace(message1..' [********res]Trace')\n  local body_size = response_handle:body():length()\n  response_handle:headers():add(\"response-body-size-hello\", tostring(body_size))\nresponse_handle:headers():add(\"filer1-res1\", \"bar...waf\")\nend\n"
                                    }
            },
            {
                "name": "envoy.filters.http.lua",
                "typed_config": {
                                    "@type": "type.googleapis.com/envoy.config.filter.http.lua.v2.Lua",
                                    "inline_code": "\n\nfunction envoy_on_request(request_handle)\n\n\n  local message=\"=========AAAAABBBBCCCCC============\"\n  request_handle:logTrace(message..' [req]trace')\n  request_handle:logDebug(message..' [req]Debug')\n  request_handle:logInfo(message..' [req]Info')\n  request_handle:logWarn(message..' [req]Warn')\n  request_handle:logErr(message..' [req]Err')\n  request_handle:logCritical(message..'Critical')\n\n  request_handle:headers():add(\"foo----req-\",\"bar-2020\")\nend\nfunction envoy_on_response(response_handle)\n  local message1=\"=========response called============\"\n  response_handle:logTrace(message1..' [********res]Trace')\n  local body_size = response_handle:body():length()\n  response_handle:headers():add(\"response-body-size-hello\", tostring(body_size))\nresponse_handle:headers():add(\"filter2-res1\", \"=======the second filterbar...waf\")\nend\n"
                                    }
            },
            # {
            #     "name": "envoy.filters.http.original_src",
            #     "typed_config": {
            #                         "@type": "type.googleapis.com/envoy.extensions.filters.listener.original_src.v2.OriginalSrc",
            #                         "mark": "123"
            #                         }
            # },
    #           - name: envoy.filters.http.original_src
    # typed_config:
    #   "@type": type.googleapis.com/envoy.extensions.filters.listener.original_src.v3.OriginalSrc
    #   mark: 123

            {
                "name": "envoy.router",
                "config": {
                    # "dynamic_stats": "{...}",
                    # "start_child_span": "...",
                    # TODO: Make access logs configurable
                    "upstream_log": AccessLog("upstream.log"),
                },
            },
            
        ]

def updateFilter(filter_code):
    global http_filters
    # filter_upated= {
    #             "name": "envoy.filters.http.lua",
    #             "typed_config": {
    #                                 "@type": "type.googleapis.com/envoy.config.filter.http.lua.v2.Lua",
    #                                 "inline_code": filter_code # "\n\nfunction envoy_on_request(request_handle)\n\n\n  local message=\"=========AAAAABBBBCCCCC============\"\n  request_handle:logTrace(message..' [req]trace')\n  request_handle:logDebug(message..' [req]Debug')\n  request_handle:logInfo(message..' [req]Info')\n  request_handle:logWarn(message..' [req]Warn')\n  request_handle:logErr(message..' [req]Err')\n  request_handle:logCritical(message..'Critical')\n\n  request_handle:headers():add(\"foo----req-\",\"bar-2020\")\nend\nfunction envoy_on_response(response_handle)\n  local message1=\"=========response called============\"\n  response_handle:logTrace(message1..' [********res]Trace')\n  local body_size = response_handle:body():length()\n  response_handle:headers():add(\"response-body-size-hello\", tostring(body_size))\nresponse_handle:headers():add(\"foo-response\", \"bar...waf\")\nend\n"
    #                                 }
    http_filters[0]["typed_config"]["inline_code"]=filter_code
    print(" new filters[0]:", http_filters[0])

    return  http_filters[0]

def getFilters():
    global http_filters

    return http_filters

