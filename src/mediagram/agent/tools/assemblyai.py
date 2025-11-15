import os
import json
import time
from pathlib import Path

import assemblyai as aai

from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from . import tool, get_tool_subdir


def get_subdir_root() -> Path:
    """Get the root directory for tool operations."""
    subdir = get_tool_subdir()
    if not subdir:
        raise ValueError("Tool subdir not set in context")
    return subdir.resolve()


def ensure_contained(path: Path) -> Path:
    """Ensure path is contained within the subdir root."""
    root = get_subdir_root()
    resolved = (root / path).resolve()

    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path {path} escapes subdir containment")

    return resolved


@tool
async def transcribe(
    audio_file: str,
    output_file: str,
    format: str | None = None,
    language: str | None = None,
    speaker_labels: bool = False,
    speakers_expected: int | None = None,
    sentiment_analysis: bool = False,
    entity_detection: bool = False,
    auto_highlights: bool = False,
    iab_categories: bool = False,
    speech_model: str = "universal",
    audio_start_from: int | None = None,
    audio_end_at: int | None = None,
):
    """Transcribe audio file using AssemblyAI with optional analysis features.

    Transcribes audio to text with support for speaker identification, sentiment
    analysis, entity detection, keyword extraction, and topic classification.

    Args:
        audio_file: Relative path to input audio file (mp3, wav, m4a, etc.)
        output_file: Relative path to output file
        format: Output format - "txt" (plain text), "json" (structured data with all
            metadata), "srt" (SubRip subtitles), or "vtt" (WebVTT subtitles). If None,
            auto-detected from output_file extension. Must match file extension.
        language: ISO-639-1 code; None auto-detects. Common options include zh, es, en, hi,
            ar, bn, pt, he, fa, tr.
        speaker_labels: Enable speaker diarization to identify different speakers
        speakers_expected: Expected number of speakers (helps improve accuracy when known)
        sentiment_analysis: Analyze sentiment (positive/neutral/negative) of sentences
        entity_detection: Detect and extract named entities (people, places, organizations)
        auto_highlights: Extract important keywords and phrases with relevance scores
        iab_categories: Classify content by IAB taxonomy topics (e.g., "Technology>AI")
        speech_model: Transcription model - "universal" (recommended: multi-language, balanced
            accuracy/latency) or "slam-1" (highest accuracy, high-cost, English only)
        audio_start_from: Start transcription at this millisecond offset (e.g., 30000 for 30s)
        audio_end_at: Stop transcription at this millisecond offset (e.g., 120000 for 2m)
    """
    try:
        audio_path = ensure_contained(Path(audio_file))
        output_path = ensure_contained(Path(output_file))

        if not audio_path.exists():
            yield ErrorMessage(text=f"Audio file not found: {audio_file}")
            return

        if not audio_path.is_file():
            yield ErrorMessage(text=f"Audio path is not a file: {audio_file}")
            return

        detected_format = output_path.suffix.lstrip(".").lower()
        if detected_format not in ("txt", "json", "srt", "vtt"):
            detected_format = "txt"

        if format is None:
            format = detected_format
        else:
            format = format.lower()
            if format not in ("txt", "json", "srt", "vtt"):
                yield ErrorMessage(
                    text=f"Invalid format '{format}'. Must be: txt, json, srt, or vtt"
                )
                return

            if format != detected_format:
                yield ErrorMessage(
                    text=f"Format mismatch: specified '{format}' but filename suggests '{detected_format}'"
                )
                return

        if speech_model not in ("universal", "slam-1"):
            yield ErrorMessage(
                text=f"Invalid speech_model '{speech_model}'. Must be 'universal' or 'slam-1'"
            )
            return

        api_key = os.getenv("ASSEMBLY_AI_KEY")
        if not api_key:
            yield ErrorMessage(
                text="ASSEMBLY_AI_KEY environment variable not set. Configure it in .env file."
            )
            return

        aai.settings.api_key = api_key

        yield ProgressMessage(
            text=f"Uploading audio file: {audio_file}",
            completion_ratio=0.1,
        )

        config = aai.TranscriptionConfig(
            language_code=language,
            speaker_labels=speaker_labels,
            speakers_expected=speakers_expected,
            sentiment_analysis=sentiment_analysis,
            entity_detection=entity_detection,
            auto_highlights=auto_highlights,
            iab_categories=iab_categories,
            speech_model=aai.SpeechModel(speech_model),
            audio_start_from=audio_start_from,
            audio_end_at=audio_end_at,
        )

        transcriber = aai.Transcriber(config=config)

        yield ProgressMessage(
            text="Submitting transcription job",
            completion_ratio=0.2,
        )

        start_time = time.time()
        transcript = transcriber.submit(str(audio_path))

        last_status = None
        while transcript.status not in (
            aai.TranscriptStatus.completed,
            aai.TranscriptStatus.error,
        ):
            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60

            if transcript.status != last_status:
                yield ProgressMessage(
                    text=f"Status: {transcript.status.value} ({elapsed_min:.1f}m elapsed)"
                )
                last_status = transcript.status

            time.sleep(3)
            transcript = aai.Transcript.get_by_id(transcript.id)

        if transcript.status == aai.TranscriptStatus.error:
            yield ErrorMessage(text=f"Transcription failed: {transcript.error}")
            return

        yield ProgressMessage(
            text="Formatting output",
            completion_ratio=0.9,
        )

        if format == "txt":
            if speaker_labels and transcript.utterances:
                lines = []
                for utt in transcript.utterances:
                    lines.append(f"Speaker {utt.speaker}: {utt.text}")
                output_content = "\n\n".join(lines)
            else:
                output_content = transcript.text

        elif format == "srt":
            output_content = transcript.export_subtitles_srt()

        elif format == "vtt":
            output_content = transcript.export_subtitles_vtt()

        elif format == "json":
            data = {
                "id": transcript.id,
                "text": transcript.text,
                "audio_duration": transcript.audio_duration,
            }

            if hasattr(transcript, "language_code") and transcript.language_code:
                data["language"] = transcript.language_code
            elif hasattr(transcript, "language_codes") and transcript.language_codes:
                data["languages"] = transcript.language_codes

            if speaker_labels and transcript.utterances:
                data["speakers"] = [
                    {
                        "speaker": utt.speaker,
                        "text": utt.text,
                        "start": utt.start,
                        "end": utt.end,
                    }
                    for utt in transcript.utterances
                ]

            if sentiment_analysis and transcript.sentiment_analysis:
                data["sentiment"] = [
                    {
                        "text": sent.text,
                        "sentiment": sent.sentiment.value,
                        "confidence": sent.confidence,
                        "start": sent.start,
                        "end": sent.end,
                    }
                    for sent in transcript.sentiment_analysis
                ]

            if entity_detection and transcript.entities:
                data["entities"] = [
                    {
                        "text": ent.text,
                        "type": ent.entity_type.value,
                        "start": ent.start,
                        "end": ent.end,
                    }
                    for ent in transcript.entities
                ]

            if auto_highlights and transcript.auto_highlights:
                data["highlights"] = [
                    {
                        "text": hl.text,
                        "count": hl.count,
                        "rank": hl.rank,
                        "timestamps": [
                            {"start": ts.start, "end": ts.end} for ts in hl.timestamps
                        ],
                    }
                    for hl in transcript.auto_highlights.results
                ]

            if iab_categories and transcript.iab_categories:
                data["topics"] = {
                    label: relevance
                    for label, relevance in transcript.iab_categories.summary.items()
                }

            output_content = json.dumps(data, indent=2)

        output_path.write_text(output_content)

        duration_sec = (
            transcript.audio_duration / 1000 if transcript.audio_duration else 0
        )
        elapsed = time.time() - start_time

        yield SuccessMessage(
            text=f"Transcribed {audio_file} ({duration_sec:.1f}s) -> {output_file} in {elapsed:.1f}s"
        )

    except ValueError as e:
        yield ErrorMessage(text=str(e))
    except Exception as e:
        yield ErrorMessage(text=f"Transcription error: {e}")
