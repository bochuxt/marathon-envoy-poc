import requests
from requests.exceptions import HTTPError
from requests.exceptions import Timeout
from requests.exceptions import ConnectionError
import json
#from sets import Set
# >>> engineers = Set(['John', 'Jane', 'Jack', 'Janice'])
# >>> programmers = Set(['Jack', 'Sam', 'Susan', 'Janice'])
# >>> managers = Set(['Jane', 'Jack', 'Susan', 'Zack'])
# >>> employees = engineers | programmers | managers           # union
# >>> engineering_management = engineers & managers            # intersection
# >>> fulltime_management = managers - engineers - programmers # difference
# >>> engineers.add('Marvin')                                  # add element

proxy_host="localhost"
proxy_admin_port=8001
proxy_clusters_url="http://localhost:8001/clusters"
proxy_config_url="http://localhost:%s/config_dump"
proxy_certs_url ="http://localhost:8001/certs"
proxy_linteners_url="http://localhost:8001/listeners"
proxy_serverInfo_url="http://localhost:8001/server_info"




# %(proxy_host,proxy_admin_port)
class ProxyNode(object):
    def __init__(self,id,cluster,metadata):
        #   id: customerId
        #   cluster: customerId-cluser-1
        self.id = id
        self.cluster = cluster
        self.metadata = metadata

    def __hash__(self):
        return hash((self.id, self.cluster))

    def __eq__(self, other):
        if not isinstance(other, type(self)): return NotImplemented
        return self.id == other.id and self.cluster == other.cluster 
#proxyNodeList=set([])#ProxyNode(None,None)

class ProxyNodeEncoder(json.JSONEncoder):
     def default(self, obj):
         if isinstance(obj, ProxyNode):
             #print(" >>>>>obj.metadata", type(obj.metadata),obj.metadata.get("https_port"))
             return {
             "id": obj.id, 
             "cluster": obj.cluster,
             "metadata":{
                'https_port': obj.metadata.get("https_port"), 
                'http_port': obj.metadata.get("http_port"), 
                'description': obj.metadata.get("description"), 
                'stage': obj.metadata.get("stage"), 
                'admin_port':obj.metadata.get("admin_port")}
             }
             #
         # Let the base class default method raise the TypeError
         return json.JSONEncoder.default(self, obj)

# for url in ['https://api.github.com', 'https://api.github.com/invalid']:
def fetchProxyInfo(url,timeout=10):
    try:
        response = requests.get(url)#,timeout)



        #print(" >>>>>route descovery service", discovery_request)
        #response.encoding = 'utf-8' # Optional: requests infers this internally
        rt=None
        tag=None
        if "text/plain" in response.headers['Content-Type'] : 
            #print(response.text)
            response.encoding = 'utf-8'
            rt=response.text
            tag='text'

        #print(response.headers['Content-Type'])
        if "json" in response.headers['Content-Type'] :
            #print("JSON:",response.json())
            rt=response.json()
            tag='json'


        # If the response was successful, no Exception will be raised
        #response.raise_for_status()
        #data_request = response.get_json()#force=True)
        #print(data_request)
        return tag,rt
    except HTTPError as http_err:
        print("HTTPERR:",http_err)
        #print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except ConnectionError as ce:
        print("connection err:", ce)
    except Exception as e:
        print("ERR: ",str(e))
        #print(f'Other error occurred: {err}')  # Python 3.6
    except Timeout as t:
        print('The request timed out', t)
    else:
        print('Success!')

def getConfig(admin_port):
    print(">>>> admin url: ",proxy_config_url%(admin_port))
    tag, rt=fetchProxyInfo(proxy_config_url%(admin_port))
    #print(rt)
    return rt
# def getProxyNodeList():
#     #global proxyNodeList
#     return proxyNodeList




if __name__ == "__main__":
    print(" ====== start fetch proxyinfo")
    tag, rt=fetchProxyInfo(proxy_clusters_url)
    print("\n", rt)
    print("----- \n server info \n")
    tag, rt=fetchProxyInfo(proxy_serverInfo_url)
    print("\n ",rt)

    print(" \n ---config dump--- \n")

    tag, rt=fetchProxyInfo(proxy_config_url%(proxy_admin_port))
    print(rt)
    print(" ======done")