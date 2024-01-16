import json

from jsonget import json_get, json_get_default

from . import CommandEndpointResponse, CommandEndpointResult
from .rest import RestAuthType, RestConfig, RestEndpoint


class HomeAssistantRestEndpoint(RestEndpoint):
    name = "WAS Home Assistant REST Endpoint"

    def __init__(self, host, port, tls, token):
        self.host = host
        self.port = port
        self.token = token
        self.tls = tls
        self.url = self.construct_url(ws=False)
        self.config = RestConfig(auth_type=RestAuthType.HEADER, auth_header=f"Bearer {token}")

    def construct_url(self, ws):
        ha_url_scheme = ""
        if ws:
            ha_url_scheme = "wss://" if self.tls else "ws://"
        else:
            ha_url_scheme = "https://" if self.tls else "http://"

        return f"{ha_url_scheme}{self.host}:{self.port}/api/conversation/process"

    def get_speech(self, data):
        speech = json_get_default(data, "/response/speech/plain/speech", None)
        return speech

    def parse_response(self, response):
        self.log.debug(f"{self.name}: parsing response {response.text}")
        res = CommandEndpointResult()

        response_type = json_get(response.json(), "/response/response_type")
        speech = self.get_speech(response.json())

        if speech:
            res.speech = speech

        if response_type in ["action_done", "query_answer"]:
            res.ok = True

        command_endpoint_response = CommandEndpointResponse(result=res)
        return command_endpoint_response

    def send(self, data=None, jsondata=None, ws=None):
        out = {'text': jsondata["text"], 'language': jsondata["language"]}
        return super().send(jsondata=out)
