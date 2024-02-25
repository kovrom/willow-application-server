from datetime import datetime
from logging import getLogger
from typing import Optional

from jsonget import json_get
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse


from app.internal.wac import (
    COLLECTION,
    typesense_client,
    wac_search,
    wac_add_alias,
    wac_add,
)

log = getLogger("WAS")

router = APIRouter(
    prefix="/temp/wac-ui",
    tags=["WAC-UI"],
)

templates = Jinja2Templates(directory="/app/templates")
###Simple temp UI
# Route to display the search page
@router.get("/", summary="Serve Simple UI page")
async def serve_page(request: Request):
    # Initially, no search has been performed, so no results
    return templates.TemplateResponse("search.html", {"request": request, "search_result": None})

# Routes to handle the simple ui search, delete, add
@router.get("/search", summary="Handle Search for Simple UI page")
async def handle_search(request: Request,
                        query: str, 
                        distance: Optional[int] = 2, 
                        num_results: Optional[int] = 1, 
                        exact_match: Optional[bool] = False, 
                        semantic: Optional[str] = "hybrid", 
                        semantic_model: Optional[str] = "all-MiniLM-L12-v2"):
    try:
        time_start = datetime.now()

        # Little fix for compatibility
        if semantic == "true":
            semantic = "on"
        elif semantic == "false":
            semantic = "off"

        results = wac_search(query, exact_match=exact_match,
                             distance=distance, num_results=num_results, raw=True, semantic=semantic, semantic_model=semantic_model)

        time_end = datetime.now()
        search_time = time_end - time_start
        search_time_milliseconds = search_time.total_seconds() * 1000
        log.info('WAC search took ' + str(search_time_milliseconds) + ' ms')
    except Exception as e:
        log.exception(f"Search failed with {e}")
        results = f"Search failed with {e}"
    # Render the same page with the search result
    return templates.TemplateResponse("search.html", {"request": request, "search_result": results})
@router.post("/add_command", summary="Handle Add Command for Simple UI page")
async def add_command(request: Request, new_command: str = Form(...),
                                        is_alias: bool = Form(False), 
                                        alias: str = Form(None)):
    try:
        if is_alias and alias:
            added_result=wac_add_alias(new_command, alias, rank=1.0, source='manual_entry')
        else:
            added_result=wac_add(new_command, rank=1.0, source='manual_entry')
        response = "Command Added" if added_result else "Command Not Added. Refusing to add duplicate command"
    except Exception as e:
        log.exception(f"Add new command failed with {e}")
        response = f"Add new command failed with {e}"
    return templates.TemplateResponse("search.html", {"request": request, "add_message": response})

@router.post("/delete_command", summary="Handle Delete Command for Simple UI page")
async def delete_command(request: Request, command_id: int = Form(...)):
    try:
        log.info(f"Attempting to delete command ID {command_id}")
        delete = typesense_client.collections[COLLECTION].documents[command_id].delete(
        )
        command = json_get(delete, "/command")
        log.info(f"Successfully deleted command '{command}' with id {command_id}")
        response = f"Successfully deleted command '{command}' with id {command_id}"
    except:
        log.info(f"Failed to deleted command with id {command_id}")
        response = f"Failed to deleted command with id {command_id}"

    return templates.TemplateResponse("search.html", {"request": request, "delete_message": response})   

###End of Simple temp UI
