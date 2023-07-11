import os
import json
import base64
import logging
import requests
import traceback

from requests.exceptions import HTTPError
from jinja2 import Environment, FileSystemLoader
from urllib3.exceptions import InsecureRequestWarning

# 設定輸出格式及日誌等級
logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] - %(message)s', 
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S',
)

def generate_cloudinit_user_data(ip_address:str, netmask:str, gateway:str) -> str:
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("cloud-config.j2")
    data = template.render({"ip_address": ip_address, "netmask": netmask, "gateway": gateway})
    base64_encode_str = base64.b64encode(data.encode("UTF-8")).decode('UTF-8')
    return base64_encode_str

def get_subnet_info(category:str) -> dict:
    """
    抓取網段名稱 , 可由nutanix api取得現有資訊 , POST /api/nutanix/v3/subnets/list , Payload : {"kind": "subnet"}
    
    Args:
        category (str): 
            - wl: 白牌
            - common: common-service

    Returns:
        dict: 對應網段資訊
    """
    if category == "wl":
        return {"name": "fet-mps", "uuid": "19e90dec-cd3a-4a3b-8ad2-7326041d173a"}
    elif category == "common":
        return {"name": "fet-common", "uuid": "043e1186-17d7-4061-b014-a4ba53c26eeb"}

def get_clouinit_payload(user_data:str, hostname:str, category:str, service_type:str, cpu:int, memory:int) -> dict:
    """
    取得建立 Nutanix VM 所需 payload
    
    Args:
        user_data (str): cloud-init 所需 user_data
        hostname (str): 主機名稱
        category (str): 種類 (目前網段分為 db、mps、common-service 三個段)
        service_type (str): 服務名稱(ex: redsi、kafka、elasticsearch )
        cpu (int): VM CPU數量
        memory (int): VM Memory大小 (單位: MB)

    Returns:
        dict: Nutanix API返回的執行結果
    """
    
    # 取得網段名稱及UUID
    subnet_info = get_subnet_info(category=category)
    
    # 設定description , 此處需定義讓 nutanix inventory 可以進行歸類 , 讓ansible可以更方便管理
    description = json.dumps({"groups": [f"{service_type}", f"{category}"],"hostvars":{"dc": "fet5f", "env": "prod", "service_type": f"{service_type}", "category": f"{category}"}})

    return  {
        "spec": {
            "name": hostname,
            "description": description,
            "resources": {
                "power_state": "ON",
                "num_vcpus_per_socket": 1,
                "num_sockets": cpu,
                "memory_size_mib": memory,
                "disk_list": [
                    {
                        "device_properties": {
                            "device_type": "DISK",
                            "disk_address": {
                                "device_index": 0,
                                "adapter_type": "SCSI"
                            }
                        },
                        "data_source_reference": {
                            "kind": "image",
                            "uuid": "12ce3b41-4854-4eb0-b17b-d13a1cb0c4eb"
                        },
                        "disk_size_mib": 30720
                    }
                ],
                "nic_list": [
                    {
                        "nic_type": "NORMAL_NIC",
                        "is_connected": True,
                        "ip_endpoint_list": [
                            {
                                "ip_type": "DHCP"
                            }
                        ],
                        "subnet_reference": {
                            "kind": "subnet",
                            "name": f"{subnet_info['name']}",
                            "uuid": f"{subnet_info['uuid']}"
                        }
                    }
                ],
                "guest_tools": {
                    "nutanix_guest_tools": {
                        "state": "ENABLED",
                        "iso_mount_state": "MOUNTED"
                    }
                },
                "guest_customization": {
                    "cloud_init": {
                        "user_data": user_data
                    },
                    "is_overridable": False
                }
            },
            "cluster_reference": {
                "kind": "cluster",
                "name": "NU-FET",
                "uuid": "0005e770-bf45-6f39-3005-7cc25507a43f"
            }
        },
        "api_version": "3.1.0",
        "metadata": {
            "kind": "vm"
        }
    }

def cloud_init():
    try:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        nutanix_url    = os.getenv("NUTANIX_URL")
        nutanix_user   = os.getenv("NUTANIX_CREDENTIAL_USR")
        nutanix_passwd = os.getenv("NUTANIX_CREDENTIAL_PSW")
        
        create_vm_api_endpoint = f"{nutanix_url}/api/nutanix/v3/vms"
        headers= {"Content-Type": "application/json", "Accept": "application/json"}

        # 列表定義機器相關資訊 , 此處考慮改成讀外部json file , 可由CSV中定義好後轉JSON格式
        with open('vm_list.json') as json_file:
            vms = json.load(json_file)
        
        # 建立VM(由上面的列表跑迴圈建立)
        for vm in vms:
            # 印出要建立的機器資訊
            logging.info(f"Ready to create vm {vm['hostname']}, ip address is {vm['ip_address']}, service_type is {vm['service_type']}, category is {vm['category']}...")
            logging.info(f"Network information : IP is {vm['ip_address']}, netmask is {vm['netmask']}, gateway is {vm['gateway']}")
            logging.info(f"Resource: {vm['cpu']} CPU, {vm['memory']} MB memory")
            
            user_data = generate_cloudinit_user_data(ip_address=vm['ip_address'], netmask=vm['netmask'], gateway=vm['gateway'])
            payload   = get_clouinit_payload(user_data=user_data, hostname=vm['hostname'], category=vm['category'], service_type=vm['service_type'], cpu=vm['cpu'], memory=vm['memory'])
            logging.info(json.dumps(payload,indent=4))


            resp = requests.post(url=create_vm_api_endpoint, json=payload, auth=(nutanix_user, nutanix_passwd), headers=headers, verify=False)
            resp.raise_for_status()
            logging.info(f"請求狀態碼: {resp.status_code}")
  

    except HTTPError as exc:
        code = exc.response.status_code
        logging.error(f"狀態碼:{code} , 請確認異常後重試")
        logging.error('error', exc_info=True)
        exit(1)

    except Exception as e:
        # 捕捉異常
        logging.error('error', exc_info=True)

        exit(1)

if __name__ == "__main__":
    cloud_init()
    

    

    