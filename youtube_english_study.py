#!/usr/bin/env python3
"""Create an English study pack from a YouTube transcript/caption script.

Usage examples:
  python youtube_english_study.py --input transcript.txt --top 25
  python youtube_english_study.py --input transcript.txt --quiz
  cat transcript.txt | python youtube_english_study.py --stdin --json-out pack.json
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
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


def render_web_page(pack: dict | None = None, message: str = "") -> str:
    """Render simple in-browser UI for transcript input and study output."""
    top_rows = ""
    sentence_rows = ""
    summary_html = ""

    if pack:
        summary = pack["summary"]
        summary_html = (
            f"<p><strong>Sentences:</strong> {summary['total_sentences']} "
            f"| <strong>Unique target words:</strong> {summary['total_unique_words']}</p>"
        )
        top_rows = "".join(
            f"<tr><td>{idx}</td><td>{html.escape(item['word'])}</td><td>{item['count']}</td></tr>"
            for idx, item in enumerate(pack["top_words"], start=1)
        )
        sentence_rows = "".join(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{html.escape(item['target_word'])}</td>"
            f"<td>{html.escape(item['sentence'])}</td>"
            f"<td>{html.escape(item['fill_blank'])}</td>"
            "</tr>"
            for idx, item in enumerate(pack["study_sentences"], start=1)
        )

    escaped_message = f"<p style='color:#b00020;'>{html.escape(message)}</p>" if message else ""

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube 영어 스크립트 학습기</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 24px auto; padding: 0 16px; }}
    textarea {{ width: 100%; min-height: 220px; }}
    input[type='number'] {{ width: 80px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background: #f7f7f7; text-align: left; }}
    .controls {{ display: flex; gap: 12px; align-items: center; margin: 10px 0; flex-wrap: wrap; }}
    button {{ padding: 8px 12px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>YouTube 영어 스크립트 학습기</h1>
  <p>유튜브 자막/스크립트를 붙여넣고 분석 버튼을 누르세요.</p>
  {escaped_message}
  <form method="POST">
    <textarea name="transcript" placeholder="여기에 유튜브 스크립트를 붙여넣으세요."></textarea>
    <div class="controls">
      <label>Top 단어 수: <input name="top" type="number" min="1" max="200" value="20" /></label>
      <label>최소 단어 길이: <input name="min_len" type="number" min="1" max="20" value="4" /></label>
      <button type="submit">분석하기</button>
    </div>
  </form>
  {summary_html}
  <h2>핵심 단어</h2>
  <table>
    <thead><tr><th>#</th><th>단어</th><th>빈도</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
  <h2>문장 연습</h2>
  <table>
    <thead><tr><th>#</th><th>타겟 단어</th><th>원문</th><th>빈칸 문제</th></tr></thead>
    <tbody>{sentence_rows}</tbody>
  </table>
</body>
</html>"""


def run_web_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run a lightweight web server to visualize study results in browser."""

    class Handler(BaseHTTPRequestHandler):
        def _write_html(self, page: str) -> None:
            encoded = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            self._write_html(render_web_page())

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
            form = parse_qs(raw_body)

            transcript = form.get("transcript", [""])[0]
            top = form.get("top", ["20"])[0]
            min_len = form.get("min_len", ["4"])[0]

            if not transcript.strip():
                self._write_html(render_web_page(message="스크립트 텍스트를 입력해 주세요."))
                return

            try:
                top_n = max(1, int(top))
                min_word_len = max(1, int(min_len))
            except ValueError:
                self._write_html(render_web_page(message="숫자 옵션(top, min_len)을 올바르게 입력하세요."))
                return

            pack = build_study_pack(transcript, top_n=top_n, min_len=min_word_len)
            self._write_html(render_web_page(pack=pack))

        def log_message(self, fmt: str, *args: object) -> None:
            # Keep console output concise in interactive mode.
            return

    server = HTTPServer((host, port), Handler)
    print(f"Web mode running: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learn English words and sentences from YouTube transcript text.")
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--input", type=Path, help="Path to transcript text file (txt/srt/vtt).")
    source.add_argument("--stdin", action="store_true", help="Read transcript text from stdin.")

    parser.add_argument("--top", type=int, default=20, help="How many top words to extract (default: 20).")
    parser.add_argument("--min-len", type=int, default=4, help="Minimum word length to count (default: 4).")
    parser.add_argument("--quiz", action="store_true", help="Run interactive fill-in-the-blank quiz.")
    parser.add_argument("--json-out", type=Path, help="Optional path to save study pack as JSON.")
    parser.add_argument("--web", action="store_true", help="Run browser UI mode (ignores --input/--stdin).")
    parser.add_argument("--host", default="127.0.0.1", help="Host for --web mode (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Port for --web mode (default: 8000).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.web:
        run_web_server(host=args.host, port=args.port)
        return 0

    if not (args.input or args.stdin):
        print("Either --input or --stdin is required unless --web is used.", file=sys.stderr)
        return 2

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
