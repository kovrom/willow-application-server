import json
import requests


URL_WAS_API_CLIENTS = 'http://localhost:8502/api/clients'
URL_WAS_API_OTA = 'http://localhost:8502/api/ota'

URL_WAS_API_CONFIG = "http://localhost:8502/api/config"
URL_WAS_API_NVS = "http://localhost:8502/api/nvs"

def get_config():
	response = requests.get(URL_WAS_API_CONFIG)
	json = response.json()
	return json

def get_devices():
    response = requests.get(URL_WAS_API_CLIENTS)
    json = response.json()
    return json

def get_nvs():
	response = requests.get(URL_WAS_API_NVS)
	json = response.json()
	return json

def merge_dict(dict_1, dict_2):
	result = dict_1 | dict_2
	return result

def num_devices():
    return(len(get_devices()))

def ota(hostname):
    requests.post(URL_WAS_API_OTA, json={'hostname': hostname})

def post_config(json):
	requests.post(URL_WAS_API_CONFIG, json = json)

def post_nvs(json):
	requests.post(URL_WAS_API_NVS, json=json)