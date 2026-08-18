"""Generate a deterministic synthetic export.json for large-viewer benchmarking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_fixture(slide_count: int = 6000, slides_per_deck: int = 30, text_chars: int = 1000) -> dict:
    deck_count = (slide_count + slides_per_deck - 1) // slides_per_deck
    decks = []
    slides = []
    body = "benchmark " + ("x" * max(0, text_chars - 10))
    for deck_idx in range(deck_count):
        decks.append({
            "id": f"d{deck_idx}",
            "file_path": f"C:/Benchmark/deck-{deck_idx}.pptx",
            "file_name": f"deck-{deck_idx}.pptx",
            "folder_path": "C:/Benchmark",
            "file_size": 5_000_000,
            "modified_time": 1_755_000_000 + deck_idx,
            "modified_date": "2026-08-18",
            "slide_count": min(slides_per_deck, slide_count - deck_idx * slides_per_deck),
        })
    for idx in range(slide_count):
        deck_idx = idx // slides_per_deck
        num = idx % slides_per_deck + 1
        slides.append({
            "id": f"s{idx}", "deck_id": f"d{deck_idx}", "num": num,
            "title": f"Slide {idx}", "subtitle": "Benchmark subtitle",
            "body": body, "extra": "", "text": body, "notes": "",
            "thumb": f"assets/decks/d{deck_idx}/thumb_{num}.jpg",
            "preview": f"assets/decks/d{deck_idx}/preview_{num}.jpg",
            "w": 1600, "h": 900,
        })
    return {
        "stats": {"deck_count": deck_count, "slide_count": slide_count, "folder_count": 1},
        "decks": decks, "slides": slides, "daily": [],
        "folders": ["C:/Benchmark"], "viewer_title": "Benchmark Archive",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", type=int, default=6000)
    parser.add_argument("--slides-per-deck", type=int, default=30)
    parser.add_argument("--text-chars", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = build_fixture(args.slides, args.slides_per_deck, args.text_chars)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    print(f"slides={args.slides} decks={len(data['decks'])} json_mib={len(raw) / 1024 / 1024:.2f}")


if __name__ == "__main__":
    main()
