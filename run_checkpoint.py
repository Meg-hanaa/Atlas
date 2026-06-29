"""Run checkpoint 6: ingest → retain → reflect → search → chat."""

from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from config import get_subject
from ingest.leetcode_ingest import ingest_leetcode
from ingest.pdf_ingest import ingest_pdf
from ingest.photo_ocr_ingest import ingest_photo
from ingest.youtube_ingest import ingest_youtube
import config  # noqa: F401 — SSL certs bootstrap

from memory.bank import consolidated_notes, ensure_bank, retain_ingested, search_memories
from routing.models import cascade_run, chat_agent, run_async
from sample_sources import (
    DEMO_PDF_PATH,
    DEMO_PHOTO_PATHS,
    DEMO_YOUTUBE_URLS,
    SAMPLE_LEETCODE,
)

SUBJECT = get_subject()
USER_ID = os.getenv("ATLAS_CHECKPOINT_USER", "checkpoint-user")


def ingest_all():
    chunks = []
    errors = []

    for url in DEMO_YOUTUBE_URLS:
        try:
            c = ingest_youtube(url, SUBJECT)
            chunks.append(c)
            print(f"  OK youtube: {c['source']} ({len(c['content'])} chars)")
        except Exception as e:
            errors.append(f"YouTube {url}: {e}")
            print(f"  FAIL youtube: {e}")

    try:
        c = ingest_pdf(DEMO_PDF_PATH, SUBJECT)
        chunks.append(c)
        print(f"  OK pdf: {c['source']} ({len(c['content'])} chars)")
    except Exception as e:
        errors.append(f"PDF: {e}")
        print(f"  FAIL pdf: {e}")

    for path in DEMO_PHOTO_PATHS:
        full = os.path.join(ROOT, path)
        try:
            result = ingest_photo(full, SUBJECT, USER_ID)
            if result["status"] == "ok":
                c = result["chunk"]
                chunks.append(c)
                print(
                    f"  OK photo: {c['source']} ({len(c['content'])} chars, "
                    f"conf={result['confidence']:.0%})"
                )
            else:
                print(
                    f"  QUEUED photo: {result['source']} "
                    f"(conf={result['confidence']:.0%}, review #{result['queue_id']})"
                )
        except Exception as e:
            errors.append(f"Photo {path}: {e}")
            print(f"  FAIL photo {path}: {e}")

    for item in SAMPLE_LEETCODE:
        c = ingest_leetcode(item["prompt"], SUBJECT, title=item["title"])
        chunks.append(c)
        print(f"  OK leetcode: {c['source']}")

    return chunks, errors


def retain_chunks(chunks):
    ensure_bank(USER_ID, SUBJECT)
    retained = 0
    for chunk in chunks:
        retained += retain_ingested(USER_ID, chunk)
    return retained


def chat_test(question: str):
    memories = search_memories(USER_ID, question, subject=SUBJECT, max_results=5)
    context = "\n".join(f"- {m}" for m in memories)
    prompt = f"""Answer using ONLY these recalled notes:
{context}

Question: {question}
"""
    result = run_async(cascade_run(chat_agent(), prompt, max_tokens=300))
    return memories, result


def main():
    print("=== CHECKPOINT 6 ===\n")

    print("1. Ingesting sources...")
    chunks, errors = ingest_all()
    print(f"   Chunks: {len(chunks)}, Errors: {len(errors)}\n")

    print("2. Retaining to Hindsight...")
    try:
        n = retain_chunks(chunks)
        print(f"   Retained {n} chunks\n")
    except Exception as e:
        print(f"   FAIL retain: {e}")
        traceback.print_exc()
        return 1

    print("3. Reflect -> consolidated notes...")
    try:
        notes = consolidated_notes(USER_ID, SUBJECT)
        print(f"   OK ({len(notes)} chars)")
        print(notes[:500], "...\n")
    except Exception as e:
        print(f"   FAIL reflect: {e}")
        traceback.print_exc()
        return 1

    print("4. Recall search...")
    try:
        hits = search_memories(USER_ID, "gradient descent cost function", subject=SUBJECT)
        print(f"   OK — {len(hits)} hits")
        for h in hits[:3]:
            print(f"   - {h[:120]}...")
        print()
    except Exception as e:
        print(f"   FAIL recall: {e}")
        traceback.print_exc()
        return 1

    print("5. Chat (cascadeflow)...")
    try:
        hits, result = chat_test("What is linear regression?")
        print(f"   Model: {result.model_used}, Cost: ${result.total_cost:.6f}")
        print(f"   Answer: {result.content[:300]}...")
        print()
    except Exception as e:
        print(f"   FAIL chat: {e}")
        traceback.print_exc()
        return 1

    if errors:
        print("Warnings:")
        for e in errors:
            print(f"  - {e}")

    print("\n=== CHECKPOINT 6 PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
