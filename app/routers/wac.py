from datetime import datetime
from logging import getLogger
from typing import Optional

import httpx

from jsonget import json_get
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.internal.wac import (
    COLLECTION,
    CORRECT_ATTEMPTS,
    SEARCH_DISTANCE,
    TYPESENSE_API_KEY,
    TYPESENSE_HOST,
    TYPESENSE_PORT,
    TYPESENSE_PROTOCOL,
    TYPESENSE_SEMANTIC_MODE,
    TYPESENSE_SEMANTIC_MODEL,
    add_ha_entities,
    init_typesense,
    typesense_client,
    wac_search,
)

log = getLogger("WAS")

router = APIRouter(
    prefix="/api/wac",
    tags=["WAC"],
)


@router.get("/add_ha_entities", summary="Add Entities from HA", response_description="Status")
async def api_add_ha_entities():
    try:
        add_ha_entities()
        return JSONResponse(content={"success": True})
    except Exception as e:
        log.exception(f"Add HA Entities failed with {e}")
        raise HTTPException(status_code=500, detail="WAC Add HA Entities Failed")


@router.get("/re_init", summary="Wipe DB and Start Over", response_description="Status")
async def api_reinitialize():
    try:
        log.info("Re-initializing...")
        typesense_client.collections[COLLECTION].delete()
        init_typesense()
        return JSONResponse(content={"success": True})
    except Exception as e:
        log.exception(f"Re-init failed with {e}")
        raise HTTPException(status_code=500, detail="WAC Re-init Failed")


@router.get("/delete", summary="Delete command")
async def api_delete(id: int):
    try:
        log.info(f"Attempting to delete command ID {id}")
        delete = typesense_client.collections[COLLECTION].documents[id].delete()
        command = json_get(delete, "/command")
        log.info(f"Successfully deleted command '{command}' with id {id}")
        response = {"success": True, "deleted": command}
    except Exception:
        log.info(f"Failed to deleted command with id {id}")
        response = {"success": False}

    return JSONResponse(content=response)


@router.get("/search", summary="WAC Search", response_description="WAC Search")
async def api_get_wac(
    command,
    distance: Optional[str] = SEARCH_DISTANCE,
    num_results: Optional[str] = CORRECT_ATTEMPTS,
    exact_match: Optional[bool] = False,
    semantic: Optional[str] = TYPESENSE_SEMANTIC_MODE,
    semantic_model: Optional[str] = TYPESENSE_SEMANTIC_MODEL,
):
    try:
        time_start = datetime.now()

        # Little fix for compatibility
        if semantic == "true":
            semantic = "on"
        elif semantic == "false":
            semantic = "off"

        results = wac_search(
            command,
            exact_match=exact_match,
            distance=distance,
            num_results=num_results,
            raw=True,
            semantic=semantic,
            semantic_model=semantic_model,
        )

        time_end = datetime.now()
        search_time = time_end - time_start
        search_time_milliseconds = search_time.total_seconds() * 1000
        log.info("WAC search took " + str(search_time_milliseconds) + " ms")
        return JSONResponse(content=results)
    except Exception as e:
        log.exception(f"Search failed with {e}")
        raise HTTPException(status_code=500, detail="WAC Search Failed")


TS_URL = f"{TYPESENSE_PROTOCOL}://{TYPESENSE_HOST}:{TYPESENSE_PORT}"
ts_client = httpx.AsyncClient(base_url=TS_URL)


async def ts_proxy(request: Request):
    path = request.url.path.replace("/api/wac/typesense", "")
    url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
    log.debug(f"WAC Typesense API proxy: url: {url}")
    headers = request.headers.mutablecopy()
    headers["Accept-Encoding"] = "none"
    headers["X-TYPESENSE-API-KEY"] = TYPESENSE_API_KEY
    proxy_req = ts_client.build_request(request.method, url, headers=headers, content=await request.body())
    proxy_res = await ts_client.send(proxy_req, stream=True)

    return StreamingResponse(
        proxy_res.aiter_raw(),
        background=BackgroundTask(proxy_res.aclose),
        headers=proxy_res.headers,
        status_code=proxy_res.status_code,
    )

router.add_api_route("/typesense/{path:path}", ts_proxy, methods=["GET", "POST"])
