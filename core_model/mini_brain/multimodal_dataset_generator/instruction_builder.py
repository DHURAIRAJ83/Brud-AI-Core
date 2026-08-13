"""MB-16: Instruction Builder -- pure. Builds instruction/input/output
triples only from real, already-computed data -- an OCR transcription
is a real instruction-following example; a caption or an object list
is real structured output. No summarization or generation model
exists anywhere in this codebase, so nothing here is synthesized text
beyond what an earlier phase already produced. Always `verified: false`.
"""

from __future__ import annotations

from typing import Any


def build_instructions(*, merged_metadata: dict[str, Any]) -> dict[str, Any]:
    instructions: list[dict[str, Any]] = []

    ocr_text = merged_metadata["text"].get("ocr_text", "")
    if ocr_text.strip():
        instructions.append({
            "instruction": "Transcribe the text visible in this document.",
            "input": None, "output": ocr_text, "verified": False,
        })

    images = merged_metadata["images"]
    caption = images.get("caption", {})
    caption_text = caption.get("long_description") or caption.get("dataset_caption")
    if caption_text:
        instructions.append({
            "instruction": "Describe what is shown in this image.",
            "input": None, "output": caption_text, "verified": False,
        })

    objects = images.get("objects", [])
    if objects:
        labels = sorted({o["label"] for o in objects})
        instructions.append({
            "instruction": "List the objects visible in this image.",
            "input": None, "output": ", ".join(labels), "verified": False,
        })

    return {
        "instructions": instructions, "instruction_count": len(instructions),
        "disclosure": "every output is reused from an already-computed upstream field -- no summarization or generation model exists in this codebase",
    }
