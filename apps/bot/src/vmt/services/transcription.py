"""speech-to-text providers, all hidden behind one shared shape (transcribe -> text)"""

import asyncio
import io
import logging
from typing import Protocol

import httpx
import pydub
import speech_recognition as sr
from elevenlabs.core.api_error import ApiError

from vmt.services.retry import retry_with_backoff
from vmt.settings import Settings

log = logging.getLogger(__name__)

# status codes worth trying again, rate limited or the server is just having a bad time
_ELEVENLABS_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EmptyTranscriptionError(Exception):
    """the provider gave us nothing usable back for this audio"""


class TranscriptionProvider(Protocol):
    name: str

    async def transcribe(self, audio_bytes: bytes) -> str: ...


def _should_retry_elevenlabs(exc: Exception) -> bool:
    # retry rate limits, server hiccups and dropped connections, never bad auth or bad input
    if isinstance(exc, ApiError):
        return (
            exc.status_code is None
            or exc.status_code in _ELEVENLABS_RETRYABLE_STATUS_CODES
        )
    return isinstance(
        exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
    )


class ElevenLabsProvider:
    """elevenlabs scribe stt via the official v2 sdk"""

    name = "elevenlabs"

    def __init__(self, api_key: str):
        from elevenlabs import ElevenLabs

        self._client = ElevenLabs(api_key=api_key)

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        # no language_code means elevenlabs auto-detects the language for us
        result = self._client.speech_to_text.convert(
            model_id="scribe_v1",
            file=io.BytesIO(audio_bytes),
        )
        text = getattr(result, "text", None)
        if not text or not text.strip():
            raise EmptyTranscriptionError("ElevenLabs returned an empty transcript")
        return text.strip()

    async def transcribe(self, audio_bytes: bytes) -> str:
        return await retry_with_backoff(
            lambda: asyncio.to_thread(self._transcribe_sync, audio_bytes),
            should_retry=_should_retry_elevenlabs,
            label="elevenlabs transcribe",
        )


class GoogleProvider:
    """free fallback, google's web speech api via the speechrecognition lib"""

    name = "google"

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        audio_segment = pydub.AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_bytes = io.BytesIO()
        audio_segment.export(wav_bytes, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_bytes) as source:
            audio_data = recognizer.record(source)

        try:
            # speech_recognition wires this method up dynamically, pyright can't see it
            return recognizer.recognize_google(audio_data)  # pyright: ignore[reportAttributeAccessIssue]
        except sr.UnknownValueError as exc:
            raise EmptyTranscriptionError(
                "Google returned an empty transcript"
            ) from exc

    async def transcribe(self, audio_bytes: bytes) -> str:
        # free and fast, so no retry here - one shot is fine
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes)


def get_provider(settings: Settings) -> TranscriptionProvider:
    if settings.elevenlabs_api_key:
        log.info("Using ElevenLabs Scribe for transcription")
        return ElevenLabsProvider(settings.elevenlabs_api_key)
    log.info("ELEVENLABS_API_KEY not set, using Google Web Speech for transcription")
    return GoogleProvider()
