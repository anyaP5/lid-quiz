"""
Convert the BAMF LiD catalog PDF into src/data/questions.json (+ images).

Correct answers come from the LpB flashcards PDF ("Lernkarten"), which has an
answer key for the 300 general questions. Because the flashcards are older
(2017) than the catalog, answers are matched by *text*, not by letter, and
anything uncertain is written to tools/review.txt.

Usage (needs: pip install pymupdf):
    python tools/convert_catalog.py <catalog.pdf> <flashcards.pdf>
"""

import difflib
import json
import re
import sys
from pathlib import Path

import pymupdf

STATE = "Nordrhein-Westfalen"   # only this Bundesland's questions are kept
STATE_ID = "NRW"

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "src" / "data" / "questions.json"
OUT_IMAGES = ROOT / "public" / "images"
OUT_REVIEW = ROOT / "tools" / "review.txt"

# Answers set by hand, for questions the flashcards can't answer (new since 2017 or facts changed).
# catalog number -> (correct option index 0–3, reason). These win over the flashcard answer.
MANUAL_ANSWERS: dict[int, tuple[int, str]] = {
    # Facts that changed since 2017
    14: (1, "option reworded: 'Leserbriefen' -> 'Internet'"),
    72: (3, "chancellor since May 2025: Friedrich Merz"),
    213: (2, "population now ~84 million"),
    236: (3, "27 EU members since Brexit (2020)"),
    # New questions (Jewish life / Israel / antisemitism), not in the 2017 flashcards
    59: (3, "first Jewish community: Cologne, 321 AD"),
    66: (0, "Berlin und München"),
    96: (3, "§ 130 StGB: up to 5 years or fine"),
    111: (3, "public call to destroy Israel"),
    118: (3, "Makkabi clubs are open to everyone"),
    149: (2, "Holocaust denial"),
    182: (2, "Synagoge"),
    184: (0, "UN resolution 181 (1947)"),
    206: (1, "Stolpersteine: victims of National Socialism"),
    288: (1, "Nazi crimes against Jews"),
}

# Answers for the state questions: question number (1–10) -> correct option index (0 = first, 3 = last).
STATE_ANSWERS: dict[int, int] = {}

# Questions whose answer depends on current events: always listed for checking.
TIME_SENSITIVE = re.compile(r"\bjetzig|\bheutiges\b|zurzeit|aktuell|derzeit|momentan", re.IGNORECASE)

CHECKBOXES =("", "□")  # ☐ glyph (Wingdings2) in front of each option; a few pages use "□"
MAX_IMAGE_WIDTH = 1000        # px, keeps photos small enough for the phone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    """Collapse whitespace and remove soft hyphens."""
    text = text.replace("­", "").replace("\t", " ")
    return re.sub(r"\s+", " ", text).strip()


def join_lines(lines: list[str]) -> str:
    """
    Join wrapped lines with spaces, except at a hyphen at the line end:
    'Baden-' + 'Württemberg' -> 'Baden-Württemberg', 'Bundesverfassungs-' + 'gericht' -> 'Bundesverfassungsgericht'.
    """
    result = ""
    for line in (l.strip() for l in lines):
        if not line:
            continue
        if result.endswith("-") and line[:1].isupper():
            result += line
        elif result.endswith("-") and line[:1].islower():
            result = result[:-1] + line
        else:
            result = f"{result} {line}" if result else line
    return clean(result)


def page_spans(page) -> list[dict]:
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans.extend(s for s in line["spans"] if s["text"].strip())
    return spans


def group_into_lines(spans: list[dict]) -> list[list[dict]]:
    """
    Group spans that sit on the same visual line, each line sorted left to right.
    Uses vertical overlap rather than equal baselines, because symbols in a
    different font size (checkboxes) sit a bit higher or lower than the text.
    """
    center = lambda s: (s["bbox"][1] + s["bbox"][3]) / 2
    lines: list[list[dict]] = []
    for s in sorted(spans, key=center):
        if lines:
            ref = lines[-1][0]
            if ref["bbox"][1] <= center(s) <= ref["bbox"][3] or s["bbox"][1] <= center(ref) <= s["bbox"][3]:
                lines[-1].append(s)
                continue
        lines.append([s])
    for line in lines:
        line.sort(key=lambda s: s["bbox"][0])
    return lines


def visual_lines(page) -> list[dict]:
    return [
        {"y": min(s["bbox"][1] for s in line), "spans": line, "text": "".join(s["text"] for s in line)}
        for line in group_into_lines(page_spans(page))
    ]


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9äöüß]+", text.lower())


def same_text(a: str, b: str) -> bool:
    """Equal ignoring case, punctuation and word order ('der X / die Y' == 'die Y/der X')."""
    return sorted(words(a)) == sorted(words(b))


def similarity(a: str, b: str, ordered: bool = True) -> float:
    """0..1. With ordered=False, word order is ignored."""
    wa, wb = words(a), words(b)
    if not ordered:
        wa, wb = sorted(wa), sorted(wb)
    return difflib.SequenceMatcher(None, " ".join(wa), " ".join(wb)).ratio()


def find_answer(answer: str, options: list[str]) -> tuple[int | None, bool]:
    """
    Find which option is the given answer text. Tries the strictest test first:
    returns (index, exact) — exact=False means it's a fuzzy match worth a look — or (None, False).
    """
    def unique(hits: list[int]) -> int | None:
        return hits[0] if len(hits) == 1 else None

    a = words(answer)
    tests = [
        lambda o: words(o) == a,                          # same words, same order
        lambda o: sorted(words(o)) == sorted(a),          # same words, other order ("der X/die Y" vs "die Y/der X")
    ]
    for test in tests:
        hit = unique([i for i, o in enumerate(options) if test(o)])
        if hit is not None:
            return hit, True

    # Catalog option = flashcard answer plus extra words (e.g. a note in brackets)
    hit = unique([i for i, o in enumerate(options) if " ".join(words(o)).startswith(" ".join(a))])
    if hit is not None:
        return hit, False

    for ordered in (True, False):
        scores = [similarity(answer, o, ordered) for o in options]
        best = max(range(len(options)), key=lambda i: scores[i])
        runner_up = sorted(scores)[-2]
        if scores[best] >= 0.8 and scores[best] - runner_up >= 0.1:
            return best, False
    return None, False


# ---------------------------------------------------------------------------
# 1. Catalog: questions, options, images
# ---------------------------------------------------------------------------

def parse_catalog(path: str) -> list[dict]:
    doc = pymupdf.open(path)
    questions: list[dict] = []
    current = None
    state = None

    for page_no, page in enumerate(doc):
        for line in visual_lines(page):
            text = line["text"]
            for box in CHECKBOXES:
                text = text.replace(box, " ")
            text = clean(text)
            first_span = line["spans"][0]
            is_bold = "Bold" in first_span["font"]

            if re.fullmatch(r"Seite \d+ von \d+", text) or text in ("Teil I", "Teil II", "Allgemeine Fragen"):
                continue
            m = re.fullmatch(r"Fragen für das Bundesland (.+)", text)
            if m and is_bold:
                state = m.group(1)
                continue
            m = re.fullmatch(r"Aufgabe ?(\d+)", text)   # a few headings are written "Aufgabe16"
            if m and is_bold:
                current = {
                    "number": int(m.group(1)),
                    "state": state,
                    "page": page_no,
                    "y": line["y"],
                    "question_lines": [],
                    "credit_lines": [],
                    "options": [],
                    "images": [],
                }
                questions.append(current)
                continue
            if current is None:
                continue  # title page

            if first_span["text"].strip() in CHECKBOXES:
                current["options"].append([text])
            elif current["options"]:
                current["options"][-1].append(text)       # wrapped option text
            elif text.startswith("©") or text.startswith("In Anlehnung"):
                current["credit_lines"].append(text)
            elif re.fullmatch(r"(Bild [1-4] ?)+", text):
                pass                                       # captions under picture options ("Bild 1 Bild 2 ...")
            else:
                current["question_lines"].append(text)

        # Assign this page's images to the question whose heading is the last one above the image.
        for info in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            if y1 < 125:
                continue  # BAMF logo in the page header
            owner = None
            for q in questions:
                if (q["page"], q["y"]) < (page_no, y0):
                    owner = q
            if owner:
                owner["images"].append({"page": page_no, "bbox": pymupdf.Rect(info["bbox"]), "px_width": info["width"]})

    for q in questions:
        # A few questions repeat their number in the text ("184. Auf welcher ...")
        q["question"] = re.sub(rf"^{q['number']}\.\s*", "", join_lines(q.pop("question_lines")))
        q["options"] = [join_lines(o) for o in q["options"]]
        q["credit"] = clean(" ".join(q.pop("credit_lines")))
    return questions, doc


def save_image(doc, img: dict, path: Path, max_width: int) -> None:
    """Render the image's area of the page (keeps transparency/overlays right) at a sensible size."""
    page = doc[img["page"]]
    rect = img["bbox"]
    # Never larger than max_width, and never larger than the original image (upscaling only adds bytes).
    zoom = min(max_width, img["px_width"]) / rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False)
    if path.suffix == ".jpg":
        pix.save(path, jpg_quality=82)
    else:
        pix.save(path)


# ---------------------------------------------------------------------------
# 2. Flashcards: card texts + answer key
# ---------------------------------------------------------------------------

def parse_flashcards(path: str) -> tuple[dict, dict]:
    doc = pymupdf.open(path)
    cards: dict[int, dict] = {}
    answers: dict[int, int] = {}

    for page in doc:
        text = page.get_text()
        if "Lösungen zu den Testfragen" in text:
            for num, letter in re.findall(r"(\d+)\s*([a-d])\b", text):
                answers[int(num)] = "abcd".index(letter)
            continue

        spans = page_spans(page)

        # Card numbers: bold Interstate digits in the yellow header bar.
        numbers = [s for s in spans if s["font"].startswith("Interstate-Bold") and s["text"].strip().isdigit()]
        mid = page.rect.width / 2
        for n in numbers:
            col_left = n["bbox"][0] < mid
            top = n["bbox"][1] - 3
            below = [m["bbox"][1] - 3 for m in numbers
                     if (m["bbox"][0] < mid) == col_left and m["bbox"][1] > n["bbox"][1]]
            bottom = min(below) if below else page.rect.height
            x_min, x_max = (0, mid) if col_left else (mid, page.rect.width)

            inside = [s for s in spans
                      if x_min <= s["bbox"][0] < x_max and top <= s["bbox"][1] < bottom]

            question, options = [], []
            for line in group_into_lines(inside):
                first = line[0]
                if first["font"].startswith("Interstate-Regular") and first["text"].strip() == "0":
                    options.append([])                      # red "O" = new option
                    line = line[1:]
                text = clean("".join(s["text"] for s in line if s["font"].startswith("DINPro")))
                if not text:
                    continue
                if line[0]["font"].startswith("DINPro-Bold"):
                    question.append(text)
                elif options:
                    options[-1].append(text)
            cards[int(n["text"])] = {
                "question": join_lines(question),
                "options": [join_lines(o) for o in options],
            }
    return cards, answers


# ---------------------------------------------------------------------------
# 3. Put it together
# ---------------------------------------------------------------------------

def main(catalog_pdf: str, flashcards_pdf: str) -> None:
    questions, doc = parse_catalog(catalog_pdf)
    cards, answers = parse_flashcards(flashcards_pdf)

    general = [q for q in questions if q["state"] is None]
    mine = [q for q in questions if q["state"] == STATE]

    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    for old in OUT_IMAGES.glob("*"):
        old.unlink()

    output = []
    problems = []          # technical: the PDF couldn't be read as expected
    missing = []           # (entry, reason): no correct answer yet
    from_claude = []       # (entry, reason): answer from MANUAL_ANSWERS
    time_sensitive = []    # entries whose answer depends on current events

    for q in general + mine:
        qid = str(q["number"]) if q["state"] is None else f"{STATE_ID}-{q['number']}"
        file_base = f"{q['number']:03d}" if q["state"] is None else f"{STATE_ID}-{q['number']:02d}"
        entry = {"id": qid, "question": q["question"], "options": q["options"]}

        if len(q["options"]) != 4 or not q["question"]:
            problems.append(f"[{qid}] parse problem: {len(q['options'])} options, question={q['question']!r}")

        # --- images ---
        picture_options = q["options"] == ["Bild 1", "Bild 2", "Bild 3", "Bild 4"]
        if picture_options:
            if len(q["images"]) != 4:
                problems.append(f"[{qid}] expected 4 picture options, found {len(q['images'])} images")
            names = []
            for i, img in enumerate(sorted(q["images"], key=lambda im: im["bbox"].x0), start=1):
                name = f"{file_base}-{i}.png"
                save_image(doc, img, OUT_IMAGES / name, 400)
                names.append(name)
            entry["optionImages"] = names
        elif q["images"]:
            if len(q["images"]) > 1:
                problems.append(f"[{qid}] {len(q['images'])} images found, only the first is used")
            # Photos -> jpg (small); maps/diagrams with numbered answers -> png (sharp lines)
            ext = ".png" if all(o.strip() in "1234" for o in q["options"]) or "=" in "".join(q["options"]) else ".jpg"
            name = file_base + ext
            save_image(doc, q["images"][0], OUT_IMAGES / name, MAX_IMAGE_WIDTH)
            entry["image"] = name
        if q["credit"]:
            entry["imageCredit"] = q["credit"]
        if q["state"]:
            entry["state"] = STATE_ID

        # --- correct answer ---
        # Question and option TEXT always come from the BAMF catalog. The flashcards are
        # only used to find out WHICH catalog option is correct.
        correct, missing_reason = None, "no answer source"
        if q["state"] is not None:
            missing_reason = "state question — fill in STATE_ANSWERS"
        elif len(q["options"]) != 4:
            missing_reason = "could not read the options from the PDF"
        else:
            card = cards.get(q["number"])
            letter = answers.get(q["number"])
            if card is None or letter is None:
                missing_reason = "not in the flashcards"
            elif picture_options:
                correct = letter  # "Bild 1–4": the letter is the picture number
            elif len(card["options"]) != 4:
                missing_reason = "could not read the flashcard"
            elif max(similarity(card["question"], q["question"]),
                     similarity(card["question"], q["question"], ordered=False)) < 0.6:
                missing_reason = "new question since the 2017 flashcards"
            else:
                correct, _ = find_answer(card["options"][letter], q["options"])
                if correct is None:
                    missing_reason = "the flashcard's answer is no longer one of the options"

        if q["state"] is None and q["number"] in MANUAL_ANSWERS:
            correct, reason = MANUAL_ANSWERS[q["number"]]
            from_claude.append((entry, reason))
        if q["state"] and q["number"] in STATE_ANSWERS:
            correct = STATE_ANSWERS[q["number"]]
        entry["correct"] = correct

        if correct is None:
            missing.append((entry, missing_reason))
        if q["state"] is None and TIME_SENSITIVE.search(q["question"]):
            time_sensitive.append(entry)
        output.append(entry)

    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    answered = len(output) - len(missing)
    summary = [
        f"Questions: {len(output)} ({len(general)} general + {len(mine)} {STATE_ID}), "
        f"{answered} with answer, {len(missing)} without",
        f"Images: {len(list(OUT_IMAGES.glob('*')))}",
    ]
    review = [
        "LiD quiz — review list (generated by tools/convert_catalog.py, do not edit by hand)",
        "All wording is from the BAMF catalog. ✓ marks the answer currently in questions.json.",
        *summary,
        "",
        f"=== 1. MISSING ANSWERS — please fill in ({len(missing)}) ===",
        "Questions without an answer are skipped by the app.",
        "Add answers in tools/convert_catalog.py: STATE_ANSWERS (NRW) or MANUAL_ANSWERS (general),",
        "as  number: index  with index 0 = a, 1 = b, 2 = c, 3 = d. Then re-run the script.",
        "",
        *[describe(e, reason) for e, reason in missing],
        f"=== 2. ANSWERS FROM CLAUDE — please verify ({len(from_claude)}) ===",
        "The flashcards had no usable answer for these. If one is wrong, fix it in MANUAL_ANSWERS.",
        "",
        *[describe(e, reason) for e, reason in from_claude],
        f"=== 3. TIME-SENSITIVE — check when the facts change ({len(time_sensitive)}) ===",
        "",
        *[describe(e) for e in time_sensitive],
    ]
    if problems:
        review += [f"=== TECHNICAL PROBLEMS reading the PDF ({len(problems)}) ===", *problems]
    OUT_REVIEW.write_text("\n".join(review) + "\n", encoding="utf-8", newline="\n")

    print("\n".join(summary))
    print(f"Review: {len(missing)} missing, {len(from_claude)} from Claude, {len(time_sensitive)} time-sensitive, "
          f"{len(problems)} technical problems -> {OUT_REVIEW}")


def describe(entry: dict, reason: str = "") -> str:
    """One question as a readable block for review.txt."""
    lines = [f"[{entry['id']}] {entry['question']}" + (f"   ({reason})" if reason else "")]
    for i, option in enumerate(entry["options"]):
        mark = " ✓" if entry["correct"] == i else ""
        picture = f"   -> public/images/{entry['optionImages'][i]}" if "optionImages" in entry else ""
        lines.append(f"    {'abcd'[i]}) {option}{mark}{picture}")
    if "image" in entry:
        lines.append(f"    image: public/images/{entry['image']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
