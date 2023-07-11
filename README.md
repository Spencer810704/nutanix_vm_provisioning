Table of contents
- [安裝](#安裝)
- [使用說明](#使用說明)
- [文件用途](#文件用途)


# 安裝

1. 安裝虛擬環境
    ```
    virtualenv venv
    ```
2. 套用虛擬環境
    ```
    source venv/bin/activate
    ```
3. 安裝相依性套件
    ```
    pip install -r requirements.txt
    ```

# 使用說明

1. 使用前需要先宣告環境變數
    ```
    # Nutanix Prism URL
    export NUTANIX_URL="https://10.64.252.1:9440"
    
    # 登入帳密 (此為範例, 不是真正的密碼 , 實際密碼請參考1password)
    export NUTANIX_CREDENTIAL_USR=mskpadmakpos
    export NUTANIX_CREDENTIAL_PSW="1dnmjkslanl" 
    ```

2. 將要建立的VM清單放置在vm_list.json檔案內 , 如有多台機器要建立則在list中包多個dict

    - hostname: nutanix上顯示的主機名稱
    - ip_address: VM IP
    - netmask: 子網路遮罩
    - gateway: 預設閘道
    - service_type: 一般填寫服務名稱 , 如: nginx、redis、elasticsearch等 (白牌的服務則填寫mps)
    - category: 目前有 wl(白牌) / common(共用服務) 兩種選擇
    - cpu: VM vCPU 數量
    - memory: VM 記憶體大小


    範例：
    ```
    [
        {
            "hostname": "es-kfk-consumer04.pf",
            "ip_address": "10.64.5.124",
            "netmask": "24",
            "gateway": "10.64.5.255",
            "service_type": "logstash",
            "category": "common",
            "cpu": 1,
            "memory": 1024
        },
        {
            "hostname": "es-kfk-consumer05.pf",
            "ip_address": "10.64.5.125",
            "netmask": "24",
            "gateway": "10.64.5.255",
            "service_type": "logstash",
            "category": "common",
            "cpu": 1,
            "memory": 1024
        },
    ]
    ```

3. 執行腳本
    ```
    python nutanix_cloud_init.py
    ```

# 文件用途

- templates/cloud-config.j2: 主要做ㄧ些Provisioning的動作, 如:建立User、給予ssh_authorized_keys、設定網卡等等操作。

- vm_list.json: 如檔名一樣 , 用來定義目前主機。

- nutanix_cloud_init.py: 腳本 , 主要會依據 vm_list.json中定義的主機列表資訊透過 cloud-config.j2 去產生實際的cloud-init user_data , 並透過 Nutanix 建立VM的 API 將user_data傳入 以及修改 Subnet NIC 到指定網段 & 磁碟空間設定 , 最後發送API請求完成建立VM的動作。