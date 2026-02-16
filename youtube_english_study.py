#!/usr/bin/env python3
"""Create an English study pack from a YouTube transcript/caption script.

Usage examples:
  python youtube_english_study.py --input transcript.txt --top 25
  python youtube_english_study.py --input transcript.txt --quiz
  cat transcript.txt | python youtube_english_study.py --stdin --json-out pack.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

# Compact but practical stopword list for transcript-based vocabulary extraction.
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "you", "your", "yours", "yourself",
    "yourselves", "um", "uh", "like", "okay", "yeah", "really", "get", "got", "going",
    "one", "two", "three", "also", "don", "didn", "isn", "it", "let", "lets",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z']+")
TIMESTAMP_RE = re.compile(r"^\s*(\d+:)?\d{1,2}:\d{2}(\.\d+)?\s*$")
SRT_INDEX_RE = re.compile(r"^\s*\d+\s*$")
SRT_ARROW_RE = re.compile(r"-->")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class StudySentence:
    sentence: str
    target_word: str


def clean_transcript(raw: str) -> str:
    """Remove common subtitle artifacts while keeping natural text."""
    cleaned_lines: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if SRT_INDEX_RE.match(stripped):
            continue
        if TIMESTAMP_RE.match(stripped):
            continue
        if SRT_ARROW_RE.search(stripped):
            continue

        # Remove bracketed speaker tags/noise markers.
        stripped = re.sub(r"\[(.*?)\]|\((.*?)\)", "", stripped)
        stripped = stripped.strip("- ")
        if stripped:
            cleaned_lines.append(stripped)

    # Convert line-by-line subtitles into readable paragraph form.
    paragraph = " ".join(cleaned_lines)
    paragraph = re.sub(r"\s+", " ", paragraph).strip()
    return paragraph


def split_sentences(text: str) -> List[str]:
    # If punctuation is weak in captions, fallback to pseudo sentences by length.
    by_punc = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(by_punc) >= 2:
        return by_punc

    words = text.split()
    chunk_size = 18
    chunks = [" ".join(words[i : i + chunk_size]).strip() for i in range(0, len(words), chunk_size)]
    return [c for c in chunks if c]


def extract_word_stats(text: str, min_len: int = 4) -> Counter:
    words = [w.lower() for w in TOKEN_RE.findall(text)]
    filtered = [w for w in words if len(w) >= min_len and w not in STOPWORDS]
    return Counter(filtered)


def pick_study_sentences(sentences: Iterable[str], top_words: List[str], per_word: int = 1) -> List[StudySentence]:
    index = defaultdict(list)
    for sentence in sentences:
        sentence_l = sentence.lower()
        for word in top_words:
            if re.search(rf"\b{re.escape(word)}\b", sentence_l):
                index[word].append(sentence)

    chosen: List[StudySentence] = []
    for word in top_words:
        options = index.get(word, [])
        if not options:
            continue
        unique = []
        seen = set()
        for option in options:
            if option not in seen:
                unique.append(option)
                seen.add(option)
        random.shuffle(unique)
        for sent in unique[:per_word]:
            chosen.append(StudySentence(sentence=sent, target_word=word))
    return chosen


def make_blank(sentence: str, target_word: str) -> str:
    return re.sub(
        rf"\b{re.escape(target_word)}\b",
        "_____",
        sentence,
        count=1,
        flags=re.IGNORECASE,
    )


def build_study_pack(raw_text: str, top_n: int = 20, min_len: int = 4) -> dict:
    cleaned = clean_transcript(raw_text)
    sentences = split_sentences(cleaned)
    stats = extract_word_stats(cleaned, min_len=min_len)
    top_words = [word for word, _ in stats.most_common(top_n)]
    study_sentences = pick_study_sentences(sentences, top_words)

    pack = {
        "summary": {
            "total_sentences": len(sentences),
            "total_unique_words": len(stats),
            "top_n": top_n,
            "min_word_length": min_len,
        },
        "top_words": [{"word": w, "count": stats[w]} for w in top_words],
        "study_sentences": [
            {
                "target_word": ss.target_word,
                "sentence": ss.sentence,
                "fill_blank": make_blank(ss.sentence, ss.target_word),
            }
            for ss in study_sentences
        ],
    }
    return pack


def print_pack(pack: dict) -> None:
    print("\n=== YouTube English Study Pack ===")
    summary = pack["summary"]
    print(f"Sentences: {summary['total_sentences']} | Unique target words: {summary['total_unique_words']}")
    print("\n[Top Vocabulary]")
    for i, item in enumerate(pack["top_words"], start=1):
        print(f"{i:2d}. {item['word']} ({item['count']})")

    print("\n[Sentence Practice]")
    for i, item in enumerate(pack["study_sentences"], start=1):
        print(f"{i:2d}. [{item['target_word']}] {item['sentence']}")
        print(f"    Fill-in: {item['fill_blank']}")


def run_quiz(pack: dict) -> None:
    print("\n=== Mini Quiz (press Enter to skip) ===")
    score = 0
    questions = pack["study_sentences"]
    random.shuffle(questions)
    for i, item in enumerate(questions, start=1):
        print(f"\nQ{i}. {item['fill_blank']}")
        answer = input("Your answer: ").strip().lower()
        target = item["target_word"].lower()
        if not answer:
            print(f"Skipped. Correct answer: {target}")
            continue
        if answer == target:
            print("Correct!")
            score += 1
        else:
            print(f"Not quite. Correct answer: {target}")

    total = len(questions)
    print(f"\nFinal score: {score}/{total}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learn English words and sentences from YouTube transcript text.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Path to transcript text file (txt/srt/vtt).")
    source.add_argument("--stdin", action="store_true", help="Read transcript text from stdin.")

    parser.add_argument("--top", type=int, default=20, help="How many top words to extract (default: 20).")
    parser.add_argument("--min-len", type=int, default=4, help="Minimum word length to count (default: 4).")
    parser.add_argument("--quiz", action="store_true", help="Run interactive fill-in-the-blank quiz.")
    parser.add_argument("--json-out", type=Path, help="Optional path to save study pack as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.stdin:
        raw_text = sys.stdin.read()
    else:
        if not args.input.exists():
            print(f"Input file not found: {args.input}", file=sys.stderr)
            return 1
        raw_text = args.input.read_text(encoding="utf-8", errors="ignore")

    if not raw_text.strip():
        print("Transcript text is empty.", file=sys.stderr)
        return 1

    pack = build_study_pack(raw_text, top_n=args.top, min_len=args.min_len)
    print_pack(pack)

    if args.json_out:
        args.json_out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved JSON study pack to: {args.json_out}")

    if args.quiz:
        run_quiz(pack)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
