from datetime import datetime
from logging import getLogger
from typing import Optional

from jsonget import json_get
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from app.internal.wac import (
    COLLECTION,
    CORRECT_ATTEMPTS,
    HYBRID_SCORE_THRESHOLD,
    OPENAI_MODEL,
    SEARCH_DISTANCE,
    TOKEN_MATCH_THRESHOLD,
    TYPESENSE_SEMANTIC_MODE,
    TYPESENSE_SEMANTIC_MODEL,
    VECTOR_DISTANCE_THRESHOLD,
    add_ha_entities,
    api_post_proxy_handler,
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


class PostProxyBody(BaseModel):
    text: Optional[str] = "How many lights are on?"
    language: Optional[str] = "en"


@router.post("/proxy", summary="Proxy Willow Requests", response_description="WAC Response")
async def api_post_proxy(
    body: PostProxyBody,
    distance: Optional[int] = SEARCH_DISTANCE,
    token_match_threshold: Optional[int] = TOKEN_MATCH_THRESHOLD,
    exact_match: Optional[bool] = False,
    semantic: Optional[str] = TYPESENSE_SEMANTIC_MODE,
    vector_distance_threshold: Optional[float] = VECTOR_DISTANCE_THRESHOLD,
    hybrid_score_threshold: Optional[float] = HYBRID_SCORE_THRESHOLD,
    semantic_model: Optional[str] = TYPESENSE_SEMANTIC_MODEL,
    llm_model: Optional[str] = OPENAI_MODEL,
):
    try:
        time_start = datetime.now()

        # Little fix for compatibility
        if semantic == "true":
            semantic = "on"
        elif semantic == "false":
            semantic = "off"

        response = api_post_proxy_handler(
            body.text,
            body.language,
            distance=distance,
            token_match_threshold=token_match_threshold,
            exact_match=exact_match,
            semantic=semantic,
            semantic_model=semantic_model,
            vector_distance_threshold=vector_distance_threshold,
            hybrid_score_threshold=hybrid_score_threshold,
            llm_model=llm_model,
        )
        time_end = datetime.now()
        search_time = time_end - time_start
        search_time_milliseconds = search_time.total_seconds() * 1000
        log.info("WAC proxy total time " + str(search_time_milliseconds) + " ms")
        return PlainTextResponse(content=response)
    except Exception as e:
        log.exception(f"Proxy failed with {e}")
        raise HTTPException(status_code=500, detail="WAC Proxy Failed")
