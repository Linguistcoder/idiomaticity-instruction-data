#!/usr/bin/env python3
import json
import os
import shutil
import textwrap

INPUT  = "magpie_swe_annotation.json"
OUTPUT = "magpie_swe_comments.json"

CATEGORIES = {
    "g": "grammar",
    "a": "awkward phrasing",
    "p": "punctuation",
    "w": "word choice",
    "f": "flow",
    "s": "spelling",
    "t": "translationese",
}

RESPONSE_PREVIEW_LINES = 10


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_annotations():
    if not os.path.exists(OUTPUT):
        return {}
    with open(OUTPUT, encoding="utf-8") as f:
        return json.load(f)

def save_annotations(annotations):
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)


def cols():
    return shutil.get_terminal_size((80, 24)).columns

def hr(char="─"):
    return char * cols()

def wrap(text, indent="  "):
    w = max(cols() - len(indent), 40)
    out = []
    for paragraph in text.splitlines():
        if paragraph.strip() == "":
            out.append("")
        else:
            out.append(textwrap.fill(paragraph, w,
                                     initial_indent=indent,
                                     subsequent_indent=indent))
    return "\n".join(out)

def clear():
    os.system("cls" if os.name == "nt" else "clear")


class Quit(Exception):
    pass


def ask(label, valid=None, allow_empty=False):
    hint = f"  [{'/'.join(valid)}]" if valid else ""
    while True:
        try:
            raw = input(f"  {label}{hint}  > ").strip()
        except (EOFError, KeyboardInterrupt):
            raise Quit
        if raw.lower() == "q":
            raise Quit
        if valid:
            if raw.lower() in valid:
                return raw.lower()
            print(f"    ✗ enter one of: {', '.join(valid)}")
            continue
        if not raw and not allow_empty:
            continue
        return raw


def print_item(item, pos, total, done, full_response=False):
    clear()
    print(hr("═"))
    print(f"  [{pos + 1}/{total}]  ID {item['id']}"
          f"  │  {item['task_category']}  │  {item['difficulty']}"
          f"  │  {done} annotated so far")
    print(hr("═"))
    print()
    print("  INSTRUCTION")
    print(wrap(item["instruction"]))
    print()
    print("  RESPONSE")
    resp_lines = wrap(item["response"]).splitlines()
    if not full_response and len(resp_lines) > RESPONSE_PREVIEW_LINES:
        print("\n".join(resp_lines[:RESPONSE_PREVIEW_LINES]))
        print(f"\n  … {len(resp_lines) - RESPONSE_PREVIEW_LINES} more lines — type r to show full")
    else:
        print("\n".join(resp_lines))
    print()
    print(hr())


def collect_issues():
    issues = []
    while True:
        print()
        print("  ── New issue ──────────────────────────────────────────")
        print("  Quote the problematic text:")
        quote = ask("", allow_empty=True)
        cat = ask("Category:\n"
                  "    g=grammar  a=awkward phrasing  p=punctuation\n"
                  "    w=word choice  f=flow  s=spelling  t=translationese",
                  valid=list(CATEGORIES.keys()))
        sev = ask("Severity  1=subtle … 5=very grave", valid=["1","2","3","4","5"])
        print("  Explain the issue:")
        comment = ask("", allow_empty=True)
        issues.append({
            "quote":    quote,
            "category": CATEGORIES[cat],
            "severity": int(sev),
            "comment":  comment,
        })
        if ask("Add another issue?", valid=["y","n"]) == "n":
            break
    return issues


def annotate_item(item, pos, total, done):
    full_response = False
    while True:
        print_item(item, pos, total, done, full_response)
        print("  Press Enter to begin  |  r = full response  |  s = skip  |  q = quit")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            raise Quit
        if choice == "q":
            raise Quit
        if choice == "r":
            full_response = True
            continue
        if choice == "s":
            return None
        break

    print()
    print(hr())
    print("  STEP 1 — Fluency issues")
    print(hr())
    issues = collect_issues() if ask("Any fluency issues?", valid=["y","n"]) == "y" else []

    print()
    print(hr())
    print("  STEP 2 — Idioms / slang & additional notes (optional, Enter to skip)")
    print("  Tag any idiomatic expressions or slang and whether they are used correctly.")
    print(hr())
    notes = ask("", allow_empty=True)

    return {"issues": issues, "notes": notes}


items       = load_json(INPUT)
annotations = load_annotations()
total       = len(items)

start = next((i for i, it in enumerate(items) if str(it["id"]) not in annotations), 0)

pos = start
try:
    while 0 <= pos < total:
        result = annotate_item(items[pos], pos, total, len(annotations))
        if result is not None:
            annotations[str(items[pos]["id"])] = result
            save_annotations(annotations)
        pos += 1
except Quit:
    pass

save_annotations(annotations)
print(f"\nSaved → {OUTPUT}  ({len(annotations)}/{total} annotated)")
