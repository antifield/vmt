"""deepl translation wrapper, one client lives for the whole bot's life"""

import asyncio
import logging

import deepl

from vmt.services.retry import retry_with_backoff

log = logging.getLogger(__name__)

DEEPL_FREE_SERVER_URL = "https://api-free.deepl.com"


def _should_retry_deepl(exc: Exception) -> bool:
    # deepl's own exceptions already tell us if a retry is worth it
    return isinstance(exc, deepl.DeepLException) and exc.should_retry


class Translator:
    def __init__(self, api_key: str, use_free_api: bool = False):
        if use_free_api:
            log.info("Using DeepL free API")
            self._translator = deepl.Translator(
                auth_key=api_key, server_url=DEEPL_FREE_SERVER_URL
            )
        else:
            log.info("Using DeepL paid API")
            self._translator = deepl.Translator(auth_key=api_key)

    async def translate(self, text: str, target_lang: str) -> str:
        result = await retry_with_backoff(
            lambda: asyncio.to_thread(
                self._translator.translate_text, text, target_lang=target_lang
            ),
            should_retry=_should_retry_deepl,
            label="deepl translate",
        )
        if isinstance(result, list):
            # deepl hands back a list when given a list, we only ever pass one string
            return " ".join(r.text for r in result)
        return result.text
