from logging import getLogger

from app.settings import get_settings


FORCE_OPENAI_MODEL = None

log = getLogger("WAS")
settings = get_settings()

if settings.openai_api_key is not None:
    log.info("Initializing OpenAI Client")
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
