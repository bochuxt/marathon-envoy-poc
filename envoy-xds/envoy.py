import binascii
from filtermanager import getFilters, AccessLog
        
def Duration(seconds):
    # https://developers.google.com/protocol-buffers/docs/proto3#json
    return "{}s".format(seconds)


def ConfigSource(cluster_name, refresh_delay, api_type="REST"):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/base.proto.html#configsource
    return {
        # "path": "...",
        # TODO: Support other kinds of config sources
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/base.proto#apiconfigsource
        "api_config_source": {
            "api_type": api_type,
            # NOTE: "Multiple cluster names may be provided. If > 1 cluster is
            # defined, clusters will be cycled through if any kind of failure
            # occurs." -- we probably don't need this for a PoC.
            # NOTE: Field name pluralised in unreleased Envoy version
            "cluster_names": [cluster_name],
            "refresh_delay": Duration(refresh_delay),
        },
        # "ads": "{...}"
    }


def Payload(data):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/health_check.proto#envoy-api-msg-healthcheck-payload
    return {"text": binascii.hexlify(data).decode("utf-8")}


def HealthCheck(timeout, interval, unhealthy_threshold, healthy_threshold,
                tcp_send=b"\x00", tcp_receive=[]):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/health_check.proto#healthcheck
    return {
        "timeout": Duration(timeout),
        "interval": Duration(interval),
        # TODO: Support more of these parameters
        # "interval_jitter": "{...}",
        "unhealthy_threshold": unhealthy_threshold,
        "healthy_threshold": healthy_threshold,
        # "reuse_connection": "{...}",
        # "http_health_check": "{...}",
        # TODO: Support more than TCP checks
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/health_check.proto#healthcheck-tcphealthcheck
        "tcp_health_check": {
            "send": Payload(tcp_send),
            "receive": [Payload(r) for r in tcp_receive]
        },
        # "redis_health_check": "{...}"
    }


def Any(type_url, data):
    # https://developers.google.com/protocol-buffers/docs/reference/google.protobuf#any
    res = {"@type": type_url}
    res.update(data)
    return res


def DiscoveryResponse(version_info, resources, type_url):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/discovery.proto#discoveryresponse
    return {
        "version_info": version_info,
        "resources": [Any(type_url, r) for r in resources],
        "type_url": type_url,
    }


def Cluster(name, service_name, eds_config, connect_timeout, type="EDS",
            lb_policy="ROUND_ROBIN", health_checks=[]):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/cds.proto#cluster

    '''
    - name: web_service
    connect_timeout: 0.25s
    type: strict_dns # static
    lb_policy: round_robin
    load_assignment:
      cluster_name: web_service
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: web_service
                port_value: 80

    '''

    

    return {
       "name": "web_service",
       "type": "STRICT_DNS",
       "connect_timeout": "0.250s",
       "load_assignment": {
        "cluster_name": "web_service",
        "endpoints": [
         {
          "lb_endpoints": [
           {
            "endpoint": {
             "address": {
              "socket_address": {
               "address": "localhost",
               "port_value": 8090
              }
             }
            }
           }
          ]
         }
        ]
       }
      }
    #     return {
    #     "name": name,
    #     "type": type,
    #     "eds_cluster_config": {
    #         "eds_config": eds_config,
    #         "service_name": service_name,
    #     },
    #     "connect_timeout": Duration(connect_timeout),
    #     # "per_connection_buffer_limit_bytes": "{...}",
    #     "lb_policy": lb_policy,
    #     # "hosts": [],
    #     "health_checks": health_checks,
    #     # "max_requests_per_connection": "{...}",
    #     # "circuit_breakers": "{...}",
    #     # "tls_context": "{...}",
    #     # TODO: Support connecting to clusters with HTTP/2
    #     "http_protocol_options": {},
    #     # "http2_protocol_options": "{...}",
    #     # "dns_refresh_rate": "{...}",
    #     # "dns_lookup_family": "...",
    #     # "dns_resolvers": [],
    #     # "outlier_detection": "{...}",
    #     # "cleanup_interval": "{...}",
    #     # "upstream_bind_config": "{...}",
    #     # "lb_subset_config": "{...}",
    #     # "ring_hash_lb_config": "{...}",
    #     # "transport_socket": "{...}"
    # }


def Address(address, port):
    # FIXME: We only support socket addresses
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/address.proto.html#envoy-api-msg-address
    return {
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/address.proto.html#socketaddress
        "socket_address": {
            "address": address,
            "port_value": int(port),
            "protocol": "TCP",
        }
    }


def LbEndpoint(address, port, filter_metadata={}, load_balancing_weight=1):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/eds.proto#envoy-api-msg-lbendpoint
    return {
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/base.proto.html#envoy-api-msg-endpoint
        "endpoint": {"address": Address(address, port)},
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/base.proto.html#envoy-api-msg-metadata
        "metadata": {"filter_metadata": filter_metadata},
        "load_balancing_weight": load_balancing_weight,
    }


def LocalityLbEndpoints(region, lb_endpoints):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/eds.proto#localitylbendpoints
    return {
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/base.proto.html#locality
        "locality": {
            "region": region,
            # TODO: Support zones e.g. region => AWS region, zone => AWS AZ
            # "zone": "...",
            # "sub_zone": "..."
        },
        "lb_endpoints": lb_endpoints,
        # Optional: load_balancing_weight
        # Optional: priority
    }


def ClusterLoadAssignment(cluster_name, lb_endpoints):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/eds.proto#clusterloadassignment
    return {
        "cluster_name": cluster_name,
        # TODO: More than one locality
        "endpoints": [LocalityLbEndpoints("default", lb_endpoints)],
        # TODO: Do we need this? I don't fully understand...
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/eds.proto#envoy-api-msg-clusterloadassignment-policy
        "policy": {
            "drop_overload": 0.0,
        },
    }


def Listener(name, address, port, filter_chains=[]):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/lds.proto#listener
    return {
        "name": name,
        "address": Address(address, port),
        "filter_chains": filter_chains,
        # "use_original_dst": "{...}",
        # "per_connection_buffer_limit_bytes": "{...}",
        # "drain_type": "..."
    }


def FilterChain(filters, sni_domains=[], common_tls_context=None):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/lds.proto#filterchain
    chain = {
        "filter_chain_match": {"sni_domains": sni_domains},
        "filters": filters,
    }
    if common_tls_context is not None:
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/sds.proto.html#downstreamtlscontext
        chain["tls_context"] = {"common_tls_context": common_tls_context}
    return chain


def Filter(name, config):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/lds.proto#filter
    return {
        "name": name,
        "config": config,
    }


def CommonTlsContext(
        certificate_chain, private_key, alpn_protocols="h2,http/1.1"):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/sds.proto.html#commontlscontext
    return {
        # "tls_params": "{...}",
        "tls_certificates": [{
            # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/sds.proto.html#tlscertificate
            # NOTE: inline_bytes in DataSource for certs is pending this PR:
            # https://github.com/envoyproxy/envoy/pull/2248
            "certificate_chain": {
                # protobuf bytes represented as base64 strings in JSON
                "inline_string": certificate_chain
            },
            "private_key": {
                "inline_string": private_key
            },
        }],
        # "validation_context": "{...}",
        "alpn_protocols": [alpn_protocols]
    }





def HttpConnectionManager(stat_prefix, route_config_name, rds_config_source):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/filter/network/http_connection_manager.proto.html#filter-network-httpconnectionmanager
    filters=getFilters()
    return {
        "codec_type": "AUTO",
        "stat_prefix": stat_prefix,
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/filter/network/http_connection_manager.proto.html#filter-network-rds
        "rds": {
            "config_source": rds_config_source,
            "route_config_name": route_config_name,
        },
        "http_filters": filters,#getFilters(),
        # "add_user_agent": "{...}",
        # "tracing": "{...}",
        # "http_protocol_options": "{...}",
        # "http2_protocol_options": "{...}",
        # "server_name": "...",
        # TODO: Do set idle_timeout
        # "idle_timeout": "{...}",
        # "drain_timeout": "{...}",
        # TODO: Make access logs configurable
        "access_log": [AccessLog("access.log")],
        # TODO: Confirm this is what we want?
        "use_remote_address": True,
        # "generate_request_id": "{...}",
        # "forward_client_cert_details": "...",
        # "set_current_client_cert_details": "{...}"
    }


def RouteConfiguration(name, virtual_hosts, internal_only_headers):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/rds.proto#routeconfiguration
    return {
        "name": name,
        "virtual_hosts": virtual_hosts,
        "internal_only_headers": internal_only_headers,
        # "response_headers_to_add": [],
        # "response_headers_to_remove": [],
        # "request_headers_to_add": [],
        # "validate_clusters": "{...}"
    }


def VirtualHost(name, domains, cluster, require_tls):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/rds.proto#virtualhost
    return {
        "name": name,
        "domains": domains,
        # TODO: Support more routes per vhost
        "routes": [Route(cluster)],
        # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/rds.proto#enum-virtualhost-tlsrequirementtype
        "require_tls": "ALL" if require_tls else "NONE",
        # "virtual_clusters": [],
        # "rate_limits": [],
        # "request_headers_to_add": [],
        # "response_headers_to_add": [],
        # "response_headers_to_remove": [],
        # "cors": "{...}"
    }


def Route(cluster):
    # https://www.envoyproxy.io/docs/envoy/v1.5.0/api-v2/rds.proto#route
    return {
        # TODO: Support path matching, header matching
        "match": {"prefix": "/"},
        "route": {"cluster": cluster},
        # "redirect": "{...}",
        # "metadata": "{...}",
        # "decorator": "{...}"
    }
