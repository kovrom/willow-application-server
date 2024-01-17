from jsonget import json_get
import logging
import requests

from datetime import datetime
from decouple import config
from pathlib import Path
import typesense

# For typesense-server when not in dev mode
import subprocess
import threading
import time

from app.internal.was import construct_url, get_config
from app.settings import get_settings


WAC_LOG_LEVEL = config('WAC_LOG_LEVEL', default="debug", cast=str).upper()
TGI_URL = config(f'TGI_URL', default=None, cast=str)

# Typesense config vars
TYPESENSE_API_KEY = config('TYPESENSE_API_KEY', default='testing', cast=str)
TYPESENSE_DATA_DIR = config('TYPESENSE_DATA_DIR', default='/app/storage/ts', cast=str)
TYPESENSE_HOST = config('TYPESENSE_HOST', default='127.0.0.1', cast=str)
TYPESENSE_PORT = config('TYPESENSE_PORT', default=8108, cast=int)
TYPESENSE_PROTOCOL = config('TYPESENSE_PROTOCOL', default='http', cast=str)
TYPESENSE_SLOW_TIMEOUT = config(
    'TYPESENSE_SLOW_TIMEOUT', default=120, cast=int)
TYPESENSE_THREADS = config('TYPESENSE_THREADS', default=8, cast=int)
TYPESENSE_TIMEOUT = config('TYPESENSE_TIMEOUT', default=1, cast=int)

# "Prod" vs "dev"
RUN_MODE = config(f'RUN_MODE', default="prod", cast=str)
if RUN_MODE == "prod":
    TYPESENSE_HOST = "127.0.0.1"
    TYPESENSE_PORT = 8108
    TYPESENSE_PROTOCOL = "http"


# Provide user feedback for learned and corrected commands
FEEDBACK = config(f'FEEDBACK', default=True, cast=bool)

# Default number of search results and attempts
CORRECT_ATTEMPTS = config(
    'CORRECT_ATTEMPTS', default=1, cast=int)

# Search distance for text string distance
SEARCH_DISTANCE = config(
    'SEARCH_DISTANCE', default=2, cast=int)

# The number of matching tokens to consider a successful WAC search
# More tokens = closer match
TOKEN_MATCH_THRESHOLD = config(
    'TOKEN_MATCH_THRESHOLD', default=3, cast=int)

# The number of matching tokens to consider a successful WAC search
# larger float = further away (less close in meaning)
# NOTE: Different models have different score mechanisms
# This will likely need to get adjusted if you use models other than all-MiniLM-L12-v2
VECTOR_DISTANCE_THRESHOLD = config(
    'VECTOR_DISTANCE_THRESHOLD', default=0.29, cast=float)

# Hybrid/fusion search threshold.
# larger float = closer (reverse of vector distance)
HYBRID_SCORE_THRESHOLD = config(
    'HYBRID_SCORE_THRESHOLD', default=0.85, cast=float)

# Typesense embedding model to use
TYPESENSE_SEMANTIC_MODEL = config(
    'TYPESENSE_SEMANTIC_MODEL', default='all-MiniLM-L12-v2', cast=str)

# Default semantic mode
TYPESENSE_SEMANTIC_MODE = config(
    'TYPESENSE_SEMANTIC_MODE', default='hybrid', cast=str)

# The typesense collection to use
COLLECTION = config(
    'COLLECTION', default='commands', cast=str)

FORCE_OPENAI_MODEL = None

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

log = logging.getLogger("WAC")
try:
    log.setLevel(WAC_LOG_LEVEL)
    log.info(f"Set log level {WAC_LOG_LEVEL}")
except Exception as e:
    log.exception(f"Set log level {WAC_LOG_LEVEL} failed with {e}")
    pass

settings = get_settings()


class WillowAutoCorrectTypesenseStartupException(Exception):
    """Raised when Typesense failed to start

    Attributes:
        msg -- error message
    """
    def __init__(self, msg="Typesense failed to start"):
        self.msg = msg
        super().__init__(self.msg)


def init_wac(app):
    app.wac_enabled = False
    user_config = get_config()
    if "wac_enabled" in user_config and user_config["wac_enabled"]:
        if RUN_MODE == "prod":
            start_typesense()
        init_typesense()

        app.wac_enabled = True


# OpenAI
if settings.openai_api_key != "undefined":
    log.info(f"Initializing OpenAI Client")
    import openai
    openai_client = openai.OpenAI(
        api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    models = openai_client.models.list()
    if len(models.data) == 1:
        FORCE_OPENAI_MODEL = models.data[0].id
        log.info(
            f"Only one model on OpenAI endpoint - forcing model '{FORCE_OPENAI_MODEL}'")
else:
    openai_client = None

# OpenAI Chat


def openai_chat(text, model=settings.openai_model):
    log.info(f"OpenAI Chat request for text '{text}'")
    response = settings.command_not_found
    if FORCE_OPENAI_MODEL is not None:
        log.info(f"Forcing model '{FORCE_OPENAI_MODEL}'")
        model = FORCE_OPENAI_MODEL
    else:
        log.info(f"Using model '{model}'")
    if openai_client is not None:
        try:
            chat_completion = openai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": settings.openai_system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    }
                ],
                model=model,
                temperature=settings.openai_temperature,
            )
            response = chat_completion.choices[0].message.content
            # Make it friendly for TTS and display output
            response = response.replace('\n', ' ').replace('\r', '').lstrip()
            log.info(f"Got OpenAI response '{response}'")
        except Exception as e:
            log.info(f"OpenAI failed with '{e}")
    return response

# Typesense


def start_typesense():
    def run(job):
        proc = subprocess.Popen(job)
        if proc.wait() != 0:
            raise WillowAutoCorrectTypesenseStartupException
        else:
            log.info('Typesense started. Waiting for ready...')
        return proc

    log.info('Starting Typesense')

    # Make sure we always have TYPESENSE_DATA_DIR
    Path(TYPESENSE_DATA_DIR).mkdir(parents=True, exist_ok=True)

    # Fix this in prod to use some kind of unique/user provided/etc key. Not that big of a deal but...
    job = ['/usr/local/sbin/typesense-server', f'--data-dir={TYPESENSE_DATA_DIR}',
           f'--api-key={TYPESENSE_API_KEY}', '--log-dir=/dev/shm', f'--thread-pool-size={TYPESENSE_THREADS}']

    # server thread will remain active as long as FastAPI thread is running
    thread = threading.Thread(name='typesense-server',
                              target=run, args=(job,), daemon=True)
    thread.start()

    time.sleep(10)


# The real WAC MVP
typesense_client = typesense.Client({
    'nodes': [{
        'host': TYPESENSE_HOST,
        'port': TYPESENSE_PORT,
        'protocol': TYPESENSE_PROTOCOL,
    }],
    'api_key': TYPESENSE_API_KEY,
    'connection_timeout_seconds': TYPESENSE_TIMEOUT
})

# For operations that take a while like initial vector schema and model download
slow_typesense_client = typesense.Client({
    'nodes': [{
        'host': TYPESENSE_HOST,
        'port': TYPESENSE_PORT,
        'protocol': TYPESENSE_PROTOCOL,
    }],
    'api_key': TYPESENSE_API_KEY,
    'connection_timeout_seconds': TYPESENSE_SLOW_TIMEOUT
})

# The schema for WAC commands - you really do not want to mess with this
wac_commands_schema = {
    'name': COLLECTION,
    'fields': [
        {'name': 'command', 'type': 'string', "sort": True},
        {'name': 'rank', 'type': 'float'},
        {'name': 'is_alias', 'type': 'bool', 'optional': True},
        {'name': 'alias', 'type': 'string', 'optional': True, "sort": True},
        {'name': 'accuracy', 'type': 'float', 'optional': True},
        {'name': 'source', 'type': 'string', 'optional': True, "sort": True},
        {'name': 'timestamp', 'type': 'int64', 'optional': True},
        {
            "name": "all-MiniLM-L12-v2",
            "type": "float[]",
            "embed": {
                "from": [
                    "command"
                ],
                "model_config": {
                    "model_name": "ts/all-MiniLM-L12-v2"
                }
            }
        },
        {
            "name": "multilingual-e5-small",
            "type": "float[]",
            "embed": {
                "from": [
                    "command"
                ],
                "model_config": {
                    "model_name": "ts/multilingual-e5-small"
                }
            }
        },
        {
            "name": "gte-small",
            "type": "float[]",
            "embed": {
                "from": [
                    "command"
                ],
                "model_config": {
                    "model_name": "ts/gte-small"
                }
            }
        },
    ],
    'default_sorting_field': 'rank',
    "token_separators": [",", ".", "-"]
}


def init_typesense():
    try:
        typesense_client.collections[COLLECTION].retrieve()
    except:
        log.info(
            f"WAC collection '{COLLECTION}' not found. Initializing with timeout {TYPESENSE_SLOW_TIMEOUT} - please wait.")
        try:
            # Hack around slow initial schema generation because of model download
            slow_typesense_client.collections.create(wac_commands_schema)
            log.info(f"WAC collection '{COLLECTION}' initialized")
        except typesense.exceptions.ObjectAlreadyExists:
            pass

    log.info(f"Connected to WAC Typesense host '{TYPESENSE_HOST}'")


# Add HA entities


def add_ha_entities():
    log.info('Adding entities from HA')
    user_config = get_config()

    if user_config["command_endpoint"] != "Home Assistant":
        raise Exception("Home Assistant Command Endpoint required!")

    base_url = construct_url(user_config["hass_host"], user_config["hass_port"], user_config["hass_tls"])
    ha_token = user_config["hass_token"]
    ha_auth_header = f"Bearer {ha_token}"
    ha_headers = {"Authorization": ha_auth_header}
    entity_types = ['cover.', 'fan.', 'light.', 'switch.']
    url = f"{base_url}/api/states"

    response = requests.get(url, headers=ha_headers)
    entities = response.json()

    devices = []

    for type in entity_types:
        for entity in entities:
            entity_id = entity['entity_id']

            if entity_id.startswith(type):
                attr = entity.get('attributes')
                friendly_name = attr.get('friendly_name')
                if friendly_name is None:
                    # in case of blank or misconfigured HA entities
                    continue
                # Add device
                if friendly_name not in devices:
                    devices.append(friendly_name.lower())

    # Make the devices unique
    devices = [*set(devices)]

    for device in devices:
        on = (f'turn on {device}')
        off = (f'turn off {device}')

        wac_add(on, rank=0.5, source='ha_entities')
        wac_add(off, rank=0.5, source='ha_entities')


# WAC Search


def wac_search(command, exact_match=False, distance=SEARCH_DISTANCE, num_results=CORRECT_ATTEMPTS, raw=False, token_match_threshold=TOKEN_MATCH_THRESHOLD, semantic=TYPESENSE_SEMANTIC_MODE, semantic_model=TYPESENSE_SEMANTIC_MODEL, vector_distance_threshold=VECTOR_DISTANCE_THRESHOLD, hybrid_score_threshold=HYBRID_SCORE_THRESHOLD):
    log.info(f"Searching for command '{command}' with distance {distance} token match threshold {token_match_threshold} exact match {exact_match} semantic {semantic} with vector distance threshold {vector_distance_threshold} and hybrid threshold {hybrid_score_threshold}")
    # Set fail by default
    success = False
    wac_command = command

    # Absurd values to always lose if something goes wrong
    tokens_matched = 0
    vector_distance = 10.0
    hybrid_score = 0.0

    # Do not change these unless you know what you are doing
    wac_search_parameters = {
        'q': command,
        'query_by': 'command',
        'sort_by': '_text_match:desc,rank:desc,accuracy:desc',
        'text_match_type': 'max_score',
        'prioritize_token_position': False,
        'drop_tokens_threshold': 1,
        'typo_tokens_threshold': 1,
        'split_join_tokens': 'fallback',
        'num_typos': distance,
        'min_len_1typo': 3,
        'min_len_2typo': 6,
        'per_page': num_results,
        'limit_hits': num_results,
        'prefix': False,
        'use_cache': False,
        'exclude_fields': 'all-MiniLM-L12-v2,gte-small,multilingual-e5-small',
        'search_cutoff_ms': 100,
        'max_candidates': 4,
    }
    if exact_match is True:
        log.info(f"Doing exact match WAC Search")
        wac_search_parameters.update({'filter_by': f'command:={command}'})

    # Support per request semantic or hybrid semantic search
    if semantic == "hybrid":
        log.info(
            f"Doing hybrid semantic WAC Search with model {semantic_model}")
        wac_search_parameters.update(
            {'query_by': f'command,{semantic_model}'})
    elif semantic == "on":
        log.info(
            f"Doing semantic WAC Search with model {semantic_model}")
        wac_search_parameters.update(
            {'query_by': f'{semantic_model}'})

    # Try WAC search
    try:
        log.info(
            f"Doing WAC Search for command '{command}' with distance {distance}")
        wac_search_result = typesense_client.collections[COLLECTION].documents.search(
            wac_search_parameters)
        # For management API
        if raw:
            log.info(f"Returning raw results")
            return wac_search_result

        try:
            id = json_get(wac_search_result, "/hits[0]/document/id")
            text_score = json_get(wac_search_result, "/hits[0]/text_match")
            tokens_matched = json_get(
                wac_search_result, "/hits[0]/text_match_info/tokens_matched")
            wac_command = json_get(
                wac_search_result, "/hits[0]/document/command")
            source = json_get(wac_search_result, "/hits[0]/document/source")
        except:
            log.info(f"Command '{command}' not found")
            return success, command

        if exact_match and wac_command:
            log.info(
                f"Returning exact command '{wac_command}' match with id {id}")
            success = True
            return success, wac_command

        log.info(
            f"Trying scoring evaluation with top match '{wac_command}' with id {id} from source {source}")
        # Semantic handling
        if semantic == "on":
            vector_distance = json_get(
                wac_search_result, "/hits[0]/vector_distance")

            if vector_distance <= vector_distance_threshold:
                log.info(
                    f"WAC Semantic Search passed vector distance threshold {vector_distance_threshold} with result {vector_distance}")
                success = True
            else:
                log.info(
                    f"WAC Semantic Search didn't meet vector distance threshold {vector_distance_threshold} with result {vector_distance}")
        elif semantic == "hybrid":
            hybrid_score = json_get(
                wac_search_result, "/hits[0]/hybrid_search_info/rank_fusion_score")
            if hybrid_score >= hybrid_score_threshold:
                log.info(
                    f"WAC Semantic Hybrid Search passed hybrid score threshold {hybrid_score_threshold} with result {hybrid_score}")
                success = True
            else:
                log.info(
                    f"WAC Semantic Hybrid Search didn't meet hybrid score threshold {hybrid_score_threshold} with result {hybrid_score}")
        # Regular old token match
        else:
            if tokens_matched >= token_match_threshold:
                log.info(
                    f"WAC Search passed token threshold {token_match_threshold} with result {tokens_matched}")
                success = True
            else:
                log.info(
                    f"WAC Search didn't meet threshold {token_match_threshold} with result {tokens_matched}")

    except Exception as e:
        log.exception(f"WAC search for command '{command}' failed with {e}")

    return success, wac_command

# WAC Add


def wac_add(command, rank=0.9, source='autolearn'):
    log.info(f"Doing WAC add for command '{command}'")
    learned = False
    try:
        log.info(f"Searching WAC before adding command '{command}'")
        wac_exact_search_status, wac_command = wac_search(
            command, exact_match=True)
        if wac_exact_search_status is True:
            log.info('Refusing to add duplicate command')
            return learned

        # Get current time as int
        curr_dt = datetime.now()
        timestamp = int(round(curr_dt.timestamp()))
        log.debug(f"Current timestamp: {timestamp}")
        command_json = {
            'command': command,
            'rank': rank,
            'accuracy': 1.0,
            'source': source,
            'timestamp': timestamp,
        }
        # Use create to update in real time
        typesense_client.collections[COLLECTION].documents.create(command_json)
        log.info(f"Added WAC command '{command}'")
        learned = True
    except Exception as e:
        log.exception(f"WAC add for command '{command}' failed with {e}")

    return learned
