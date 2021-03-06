import binascii
import os

from flask import Flask, g, jsonify, request
from flask_cors import CORS
import json

from certs import (
    cert_fingerprint, fullchain_pem_str, key_pem_str, load_cert_obj,
    load_chain_objs, load_key_obj)
from envoy import (
    Cluster, ClusterLoadAssignment, CommonTlsContext, ConfigSource,
    DiscoveryResponse, Filter, FilterChain, HealthCheck, HttpConnectionManager,
    LbEndpoint, Listener, RouteConfiguration, VirtualHost)
from marathon import (
    MarathonClient, get_number_of_app_ports, get_task_ip_and_ports)
from vault import VaultClient
from filtermanager import updateFilter, getFilters
from proxyInfo import getConfig,  ProxyNode,ProxyNodeEncoder#,proxyNodeList# addProxyNode, getProxyNodeList,
# Don't name the flask app 'app' as is usually done as it's easy to mix up with
# a Marathon app
flask_app = Flask(__name__)
cors = CORS(flask_app, resources={r"/v2/monica/*": {"origins": "*"}})
# flask_app.config.from_object(
#     os.environ.get("APP_CONFIG", "marathon_envoy_poc.config.DevConfig"))


TYPE_LDS = "type.googleapis.com/envoy.api.v2.Listener"
TYPE_RDS = "type.googleapis.com/envoy.api.v2.RouteConfiguration"
TYPE_CDS = "type.googleapis.com/envoy.api.v2.Cluster"
TYPE_EDS = "type.googleapis.com/envoy.api.v2.ClusterLoadAssignment"

CLUSTER_CONNECT_TIMEOUT = 5
CLUSTER_HEALTHCHECK_TIMEOUT = 5
CLUSTER_HEALTHCHECK_INTERVAL = 30
CLUSTER_HEALTHCHECK_UNHEALTHY_THRESHOLD = 3
CLUSTER_HEALTHCHECK_HEALTHY_THRESHOLD = 1

proxyNodeList=set()#ProxyNode(None,None)
def addProxyNode(node):
    try:
        proxyNodeList.add(node)
    except Exception as e:
        print(" node add failed: ", e)
# def set_default(obj):
#     if isinstance(obj, set):
#         return list(obj)
#     raise TypeError



# def connect_marathon():
#     client = MarathonClient(flask_app.config["MARATHON"])
#     client.test()
#     return client

CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "xds_cluster")
    # Seconds between polls of our service
REFRESH_DELAY = os.environ.get("REFRESH_DELAY", 30)
def get_marathon():
    def get_app(app_id, embed=["app.tasks"]):
        return {
                                    "id": "/myapp",
                                    "args": "null",
                                    "user": "null",
                                    "env": {
                                    "LD_LIBRARY_PATH": "/usr/local/lib/myLib"
                                    },
                                    "instances": 3
                }


    def get_apps():
        apps={
                "apps": [
                                {
                                    "id": "/myapp",
                                    "args": "null",
                                    "user": "null",
                                    "env": {
                                    "LD_LIBRARY_PATH": "/usr/local/lib/myLib"
                                    },
                                    "instances": 3,

                                    "constraints": [
                                    [
                                        "hostname",
                                        "UNIQUE",
                                        ""
                                    ]
                                    ],
                                    "uris": [
                                    "https://raw.github.com/mesosphere/marathon/master/README.md"
                                    ],
                                    "ports": [
                                    10013,
                                    10015
                                    ]
                                    }
                    ]
        }
        return apps
    return  {"get_apps":get_apps,"get_app":get_app}

    
    # if not hasattr(g, "marathon"):
    #     g.marathon = connect_marathon()
    # return g.marathon
    return get_apps


def connect_vault():
    # if flask_app.config["VAULT_TOKEN"] is None:
    #     flask_app.logger.warn(
    #         "VAULT_TOKEN config option not set. Unable to create Vault client."
    #     )
    #     return None

    client = VaultClient(
        flask_app.config["VAULT"], flask_app.config["VAULT_TOKEN"],
        flask_app.config["MARATHON_ACME_VAULT_PATH"])
    client.test()
    return client


def get_vault():
    if not hasattr(g, "vault"):
        g.vault = connect_vault()
    return g.vault


def own_config_source():
    """
    The config to connect to this API. For specifying the EDS and RDS
    endpoints.
    """
    return ConfigSource(CLUSTER_NAME,#flask_app.config["CLUSTER_NAME"],
                        REFRESH_DELAY)#flask_app.config["REFRESH_DELAY"])


def truncate_object_name(object_name):
    """ Truncate an object name if it is too long. """
    max_len = flask_app.config["MAX_OBJECT_NAME_LENGTH"]
    if len(object_name) > max_len:
        flask_app.logger.warn(
            "Object name '%s' is too long (%d > %d). It will be truncated.",
            object_name, len(object_name), max_len)
        prefix = "[...]"
        object_name = prefix + object_name[-(max_len - len(prefix)):]
    return object_name


def app_cluster(app_id, port_index):
    service_name = "{}_{}".format(app_id, port_index)
    return truncate_object_name(service_name), service_name


def port_label(app_labels, port_index, label, prefix=None, default=None):
    """
    Get a label for a given port index.

    :param app_labels: All the labels for the app.
    :param port_index: The port index.
    :param label: The label to get.
    :param prefix:
        The prefix for the label key. If not specified, the config value for
        LABEL_PREFIX_MARATHON_LB will be used.
    :param default: Default value to return if the label is not found.
    """
    if prefix is None:
        prefix = flask_app.config["LABEL_PREFIX_MARATHON_LB"]

    port_label_key = "{}_{}_{}".format(prefix, port_index, label)
    return app_labels.get(port_label_key, default)


def app_label(app_labels, label, prefix=None, default=None):
    """
    Get a label for the app.

    :param app_labels: All the labels for the app.
    :param label: The label to get.
    :param prefix:
        The prefix for the label key. If not specified, the config value for
        LABEL_PREFIX_MARATHON_LB will be used.
    :param default: Default value to return if the label is not found.
    """
    if prefix is None:
        prefix = flask_app.config["LABEL_PREFIX_MARATHON_LB"]

    app_label_key = "{}_{}".format(prefix, label)
    return app_labels.get(app_label_key, default)


def is_port_in_group(app_labels, port_index):
    """
    Does the given port index have labels that indicate it is in the correct
    HAPROXY_GROUP.
    """
    port_group = port_label(app_labels, port_index, "GROUP",
                            default=app_label(app_labels, "GROUP"))

    return port_group == flask_app.config["HAPROXY_GROUP"]


def default_healthcheck():
    health= HealthCheck(
        CLUSTER_HEALTHCHECK_TIMEOUT,#,flask_app.config["CLUSTER_HEALTHCHECK_TIMEOUT"],
        CLUSTER_HEALTHCHECK_INTERVAL,#flask_app.config["CLUSTER_HEALTHCHECK_INTERVAL"],
        CLUSTER_HEALTHCHECK_UNHEALTHY_THRESHOLD,#flask_app.config["CLUSTER_HEALTHCHECK_UNHEALTHY_THRESHOLD"],
        CLUSTER_HEALTHCHECK_HEALTHY_THRESHOLD)#flask_app.config["CLUSTER_HEALTHCHECK_HEALTHY_THRESHOLD"])
    print(" halth", health)
    return health


@flask_app.route("/v2/discovery:clusters", methods=["POST"])
def clusters():
    clusters = []
    max_version = "0"
    # for app in get_marathon()["get_apps"]():
    #     print("app:",app)
    #     for port_index in range(get_number_of_app_ports(app)):
    #         if not is_port_in_group(app["labels"], port_index):
    #             continue

    #         max_version = max(
    #             max_version, app["versionInfo"]["lastConfigChangeAt"])

    #         cluster_name, service_name = app_cluster(app["id"], port_index)

    cluster_name="my-cluster"
    service_name="svc1"


    MAX_OBJECT_NAME_LENGTH = 60

    clusters.append(Cluster(
        cluster_name, service_name, own_config_source(),
        CLUSTER_CONNECT_TIMEOUT,#flask_app.config["CLUSTER_CONNECT_TIMEOUT"],
        health_checks=[default_healthcheck()]))
    print(" =========get cluster success......")

    return jsonify(DiscoveryResponse(max_version, clusters, TYPE_CDS))


def get_cluster_load_assignment(cluster_name, app, tasks, port_index):
    endpoints = []
    for task in tasks:
        ip, ports = get_task_ip_and_ports(app, task)
        if ip is None:
            flask_app.logger.warn("Couldn't find IP for task %s", task["id"])
            continue
        if ports is None:
            flask_app.logger.warn(
                "Couldn't find ports for task %s", task["id"])
            continue

        if port_index >= len(ports):
            flask_app.logger.warn(
                "Somehow task '%s' doesn't have port with index %d, it only "
                "has %d ports", task["id"], port_index, len(ports))
            continue

        endpoints.append(LbEndpoint(ip, ports[port_index]))
    return ClusterLoadAssignment(cluster_name, endpoints)


@flask_app.route("/v2/discovery:endpoints", methods=["POST"])
def endpoints():
    # Envoy does not send a 'content-type: application/json' header in this
    # request so we must set force=True
    discovery_request = request.get_json(force=True)
    resource_names = discovery_request["resource_names"]

    cluster_load_assignments = []
    max_version = "0"
    for cluster_name in resource_names:
        app_id, port_index = cluster_name.rsplit("_", 1)
        port_index = int(port_index)

        app = get_marathon["get_app"](app_id, embed=["app.tasks"])

        # We have to check these things because they may have changed since the
        # CDS request was made--this is normal behaviour.
        # App could've gone away
        if not app:
            flask_app.logger.debug(
                "App '%s' endpoints requested but the app doesn't exist "
                "anymore",  app["id"])
            continue

        # Port could've gone away
        if port_index >= get_number_of_app_ports(app):
            flask_app.logger.debug(
                "App '%s' port %d endpoints requested but the port doesn't "
                "exist anymore", app["id"], port_index)
            continue

        # Port labels could've changed
        if not is_port_in_group(app["labels"], port_index):
            flask_app.logger.debug(
                "App '%s' port %d endpoints requested but the port isn't in "
                "the correct group anymore", app["id"], port_index)
            continue

        tasks = app["tasks"]
        cluster_load_assignments.append(
            get_cluster_load_assignment(cluster_name, app, tasks, port_index))

        for task in tasks:
            max_version = max(max_version, task.get("startedAt", "0"))

    return jsonify(
        DiscoveryResponse(max_version, cluster_load_assignments, TYPE_EDS))


def default_http_conn_manager_filters(name):
    print(" default_http_conn_manager_filters called.")
    return [
        Filter("envoy.http_connection_manager",
               # Params are: name, stats_prefix, api_config_source
               HttpConnectionManager(name, name, own_config_source()))
    ]

# def default_http_conn_manager_filters_lua(name):
#     print(" default_http_conn_manager_filters called.")
#      #"name": "envoy.filters.http.lua",
#     return [
#         Filter("envoy.filters.http.lua",
#                # Params are: name, stats_prefix, api_config_source
#                HttpConnectionManager(name, name, own_config_source()))
#     ]

def http_filter_chains():
    return [FilterChain(default_http_conn_manager_filters("http"))]
#curl -X POST localhost:5000/v2/discovery:listeners
def https_filter_chains():
    # NOTE: Filters must be identical across FilterChains for a given listener.
    # Currently, Envoy only supports multiple FilterChains in order to support
    # SNI.
    filters = default_http_conn_manager_filters("https")

    # Fetch the certs from Vault
    filter_chains = []
    # certificates = get_certificates()
    # for domain, (cert_chain, private_key) in sorted(certificates.items()):
    #     # TODO: Read domains from certificate to support SAN
    #     tls_context = CommonTlsContext(cert_chain, private_key)
    domain="com"
    tls_context={}
    filter_chains.append(FilterChain(filters, sni_domains=[domain]))# common_tls_context=tls_context))
    return filter_chains

def _get_cached_cert(domain, cert_id):
    if domain in g._certificates:
        cert, chain, key = g._certificates[domain]
        # We check the fingerprint only when fetching certs from the cache, not
        # when storing. Doesn't really matter if the cert we get from Vault
        # doesn't have the right ID, it will hopefully be the right cert when
        # we next try to fetch from Vault.
        # NOTE: We compare "raw" bytes here. This way, binascii will take of
        # uppercase vs lowercase hex encoding.
        if cert_fingerprint(cert) == binascii.dehexlify(cert_id):
            return cert, chain, key

    return None


def _get_vault_cert(domain):
    cert = get_vault().get("/certificates/" + domain)
    cert=True
    if cert is None:
        flask_app.logger.warn(
            "Certificate not found in Vault for domain %s", domain)
        return None

    try:
        return (load_cert_obj(cert["cert"]),
                # Chain certificates optional
                load_chain_objs(cert.get("chain", "")),
                load_key_obj(cert["privkey"]))
    except Exception as e:
        flask_app.logger.warn(
            "Error parsing Vault certificate for domain %s: %s", domain, e)
        return None

VAULT = os.environ.get("VAULT", "http://127.0.0.1:8200")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")

def get_certificates():
    if not hasattr(g, "_certificates"):
        g._certificates = {}

    vault_client = True# get_vault()
    if vault_client is None:
        flask_app.logger.warn("Unable to fetch certificates: no Vault client.")
        return {}

    # Get the mapping of domain name to x509 cert hash. This can be used to
    # check our existing cache of certificates for changes.
    live_certs = vault_client.get("/live")

    # Regenerate the set of certificates, updating if certs added/changed
    certificates = {}
    for domain, cert_id in live_certs.items():
        # First, try get the certificate from the cache
        cached_cert = _get_cached_cert(domain, cert_id)
        if cached_cert is not None:
            certificates[domain] = cached_cert
        else:
            # Otherwise, fetch it from Vault
            vault_cert = _get_vault_cert(domain)
            if vault_cert is not None:
                certificates[domain] = vault_cert
        # Removed certs are skipped

    # Update the cache
    g._certificates = certificates

    # Finally, map the certificate and key objects back into the right form for
    # use by Envoy
    return {domain: (fullchain_pem_str(certs, chain), key_pem_str(key))
            for domain, (certs, chain, key) in certificates.items()}



@flask_app.route("/v2/monica/getfilters", methods=["GET"])
def getfiler():
    filters=getFilters()
    return jsonify(filters)

@flask_app.route("/v2/monica/getproxynode", methods=["GET"])
def getProxyNodes():
    try:
        global proxyNodeList 
        #proxynodes=getProxyNodeList()
        print(" request received...", proxyNodeList)
        result = json.dumps(list(proxyNodeList),cls=ProxyNodeEncoder)#, default=set_default)
        print(" request dump received...", result)
        return result#jsonify(result)
    except Exception as e:
        print(" get nodes failed: ",e)
@flask_app.route("/v2/monica/getconfig", methods=["POST"])
def getconfig():
    print("get config called..")
    request_data = request.get_json()
    admin_port=request_data.get("admin_port",8001)
    config=getConfig(admin_port)
    return jsonify(config)
@flask_app.route("/v2/monica/updatefilters", methods=["POST"])
def updatefiler():
    try:
        print(" update filter called")
        request_data = request.get_json()
            #print(request_data)
        print(" update filter received...",request_data)
        print("\n"+request_data.get("filterCode"))
        newFilter=updateFilter(request_data.get("filterCode"))
        #filters=getFilters()
        return jsonify(newFilter)
    except Exception as e:
        print("update filters", e)


@flask_app.route("/v2/discovery:listeners", methods=["POST"])
def listeners():
    discovery_request = request.get_json(force=True)
    #print(" listen request: ", discovery_request)
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("id"))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("cluster"))
    print(" >>>>>  listeners service: [metadata] ", discovery_request.get("node").get("metadata"))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("locality"))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("user_agent_build_version"))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("user_agent_name")) 
    newNode=ProxyNode(discovery_request.get("node").get("id"),discovery_request.get("node").get("cluster"), 
    discovery_request.get("node").get("metadata"))
    print(" new node: ", newNode)
    addProxyNode(newNode)  


    http_port = discovery_request.get("node").get("metadata").get("http_port",8000)#8000
    https_port= discovery_request.get("node").get("metadata").get("https_port",4430)#4430
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("metadata").get("http_port",8000))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("metadata").get("https_port",4430))
    print(" >>>>>  listeners service: ", discovery_request.get("node").get("metadata").get("admin_port",8001))
    listeners = [
        Listener(
            "http",
            "127.0.0.1",#flask_app.config["HTTP_LISTEN_ADDR"],
            http_port,#flask_app.config["HTTP_LISTEN_PORT"],
            http_filter_chains()
        ),
        Listener(
            "https",
            "127.0.0.1",#lask_app.config["HTTPS_LISTEN_ADDR"],
            https_port,#flask_app.config["HTTPS_LISTEN_PORT"],
            https_filter_chains()
        )
    ]

    print(" ========get listerner success.. ",http_port,https_port)

    return jsonify(DiscoveryResponse("0", listeners, TYPE_LDS))


def get_app_virtual_hosts(app):
    virtual_hosts = []
    app_labels = app["labels"]
    for port_index in range(get_number_of_app_ports(app)):
        if not is_port_in_group(app_labels, port_index):
            continue

        domains = parse_domains(
            port_label(app_labels, port_index, "VHOST", default=""))
        if not domains:
            flask_app.logger.debug(
                "App '%s' port %d has no domains in its HAPROXY_VHOST label. "
                "It will be ignored.", app["id"], port_index)
            continue

        cluster_name, service_name = app_cluster(app["id"], port_index)

        # TODO: Figure out how to *not* redirect marathon-acme requests to
        # HTTPS.
        require_tls = app_labels.get("REDIRECT_TO_HTTPS") == "true"

        virtual_hosts.append(
            VirtualHost(service_name, domains, cluster_name, require_tls))

    return virtual_hosts


def parse_domains(domain_str):
    # TODO: Validate domains are valid
    return domain_str.replace(",", " ").split()


@flask_app.route("/v2/discovery:routes", methods=["POST"])
def routes():
    
    # Envoy does not send a 'content-type: application/json' header in this
    # request so we must set force=True
    discovery_request = request.get_json(force=True)
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("id"))
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("cluster"))
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("metadata"))
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("locality"))
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("user_agent_name"))
    print(" >>>>>route descovery service: ", discovery_request.get("node").get("resource_names"))     
    resource_names = discovery_request["resource_names"]

    apps = get_marathon()["get_apps"]()

    route_configurations = []
    max_version = "0"
    print("=====routes processed.[route_config_name]  ",resource_names)
    for route_config_name in resource_names:
        if route_config_name not in ["http", "https"]:
            flask_app.logger.warn(
                "Unknown route config name: %s", route_config_name)
            continue

        virtual_hosts = [
                {
                 "name": "local_service",
                 "domains": [
                  "*"
                 ],
                 "routes": [
                  {
                   "match": {
                    "prefix": "/svc"
                   },
                   "route": {
                    "cluster": "web_service",
                    "prefix_rewrite": "/"
                   }
                  },
                  {
                   "match": {
                    "prefix": "/waf"
                   },
                   "route": {
                    "cluster": "waf",
                    "prefix_rewrite": "/"
                   }
                  },
                  {
                   "match": {
                    "prefix": "/app"
                   },
                   "route": {
                    "cluster": "app",
                    "prefix_rewrite": "/"
                   }
                  }
                 ]
                }
               ]
              #},
        # This part is similar to CDS
        # for app in apps:
        #     app_vhosts = get_app_virtual_hosts(app)
        #     if app_vhosts:
        #         virtual_hosts.extend(app_vhosts)
        #         max_version = max(
        #             max_version, app["versionInfo"]["lastConfigChangeAt"])

        # TODO: internal_only_headers
        route_configurations.append(
            RouteConfiguration(route_config_name, virtual_hosts, []))

    return jsonify(
        DiscoveryResponse(max_version, route_configurations, TYPE_RDS))


if __name__ == "__main__":  # pragma: no cover
    apps = get_marathon()["get_apps"]()
    app=get_marathon()["get_app"]("app1")
    print(app)
    print(" xDS running on port: ", 5000)
    flask_app.run()
