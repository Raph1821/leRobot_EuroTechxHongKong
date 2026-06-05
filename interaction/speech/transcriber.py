"""
Speech-to-text transcription — pluggable backend.

Supports:
  - "whisper" (OpenAI Whisper, local) — default
  - "aws_transcribe" (Amazon Transcribe, cloud)

Usage:
    from interaction.speech.transcriber import create_transcriber
    t = create_transcriber()  # auto-detects from env
    text = t.transcribe(audio_bytes, format="webm")
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes, format: str = "webm", language: str | None = None) -> str:
        """Transcribe audio bytes to text."""
        ...


class WhisperTranscriber(Transcriber):
    """Local OpenAI Whisper transcription (github.com/openai/whisper)."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    def _get_model(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_size)
            logger.info(f"Loaded Whisper model: {self.model_size}")
        return self._model

    def transcribe(self, audio: bytes, format: str = "webm", language: str | None = None) -> str:
        import tempfile
        model = self._get_model()

        # Write audio to temp file (whisper expects file path)
        suffix = f".{format}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            tmp_path = f.name

        try:
            kwargs = {}
            if language:
                kwargs["language"] = language
            result = model.transcribe(tmp_path, **kwargs)
            return result.get("text", "").strip()
        finally:
            os.unlink(tmp_path)


class AWSTranscribeTranscriber(Transcriber):
    """Amazon Transcribe (batch job via S3)."""

    def __init__(self, bucket: str | None = None, region: str | None = None):
        self.bucket = bucket or os.environ.get("S3_BUCKET", "robohack-map")
        self.region = region or os.environ.get("AWS_REGION", "us-west-2")

    def transcribe(self, audio: bytes, format: str = "webm", language: str | None = None) -> str:
        import time
        import uuid
        import boto3
        import httpx

        lang = language or os.environ.get("AWS_TRANSCRIBE_LANGUAGE", "en-US")
        job = f"speech-{uuid.uuid4().hex}"
        key = f"speech/{job}.{format}"
        s3_uri = f"s3://{self.bucket}/{key}"

        content_types = {"webm": "audio/webm", "mp4": "audio/mp4", "wav": "audio/wav"}
        ct = content_types.get(format, "audio/webm")

        s3 = boto3.client("s3", region_name=self.region)
        transcribe = boto3.client("transcribe", region_name=self.region)

        try:
            s3.put_object(Bucket=self.bucket, Key=key, Body=audio, ContentType=ct)
            transcribe.start_transcription_job(
                TranscriptionJobName=job,
                Media={"MediaFileUri": s3_uri},
                MediaFormat=format,
                LanguageCode=lang,
            )

            for _ in range(45):
                info = transcribe.get_transcription_job(TranscriptionJobName=job)["TranscriptionJob"]
                status = info["TranscriptionJobStatus"]
                if status == "COMPLETED":
                    uri = info["Transcript"]["TranscriptFileUri"]
                    data = httpx.get(uri, timeout=10).json()
                    return (data.get("results", {}).get("transcripts") or [{}])[0].get("transcript", "")
                if status == "FAILED":
                    raise RuntimeError(info.get("FailureReason", "Transcribe failed"))
                time.sleep(1.0)

            raise TimeoutError("Transcription timed out")
        finally:
            try:
                s3.delete_object(Bucket=self.bucket, Key=key)
            except Exception:
                pass


def create_transcriber(backend: str | None = None, **kwargs) -> Transcriber:
    """Factory — create transcriber from config.

    Args:
        backend: "whisper" or "aws_transcribe". Auto-detects if None.
    """
    b = backend or os.environ.get("SPEECH_BACKEND", "whisper").lower()
    if b == "whisper":
        return WhisperTranscriber(model_size=kwargs.get("model_size", "base"))
    elif b in ("aws", "aws_transcribe"):
        return AWSTranscribeTranscriber(**kwargs)
    else:
        raise ValueError(f"Unknown speech backend: {b!r}. Use 'whisper' or 'aws_transcribe'.")
