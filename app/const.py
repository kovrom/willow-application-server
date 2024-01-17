DIR_ASSET = '/app/storage/asset'
DIR_OTA = '/app/storage/ota'
URL_WILLOW_RELEASES = 'https://worker.heywillow.io/api/release?format=was'
URL_WILLOW_CONFIG = 'https://worker.heywillow.io/api/config'
URL_WILLOW_TZ = 'https://worker.heywillow.io/api/asset?type=tz'

STORAGE_USER_CLIENT_CONFIG = 'storage/user_client_config.json'
STORAGE_USER_CONFIG = 'storage/user_config.json'
STORAGE_USER_MULTINET = 'storage/user_multinet.json'
STORAGE_USER_NVS = 'storage/user_nvs.json'
STORAGE_USER_WAS = 'storage/user_was.json'
STORAGE_TZ = 'storage/tz.json'

# order will be reflected on /docs
OPENAPI_TAGS = [
    {
        "name": "WAS",
        "description": "Willow Application Server",
    },
    {
        "name": "WAC",
        "description": "Willow Auto Correct",
    },
]
