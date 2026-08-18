#!/usr/bin/env python3
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "approved_export.json"
MANIFEST = ROOT / "manifest.json"
PUBLISHED_IDS = ROOT / "published_ids.json"


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def find_dictionary_file(manifest):
    override = os.environ.get("SVP_DICTIONARY_FILE", "").strip()
    if override:
        p = ROOT / override
        if p.exists():
            return p

    url = str(manifest.get("dictionary_url", "") or "").strip()
    if url:
        basename = Path(urlparse(url).path).name
        if basename:
            hits = list(ROOT.rglob(basename))
            if hits:
                return hits[0]

    for p in ROOT.rglob("*.json"):
        if p.name in {"manifest.json", "approved_export.json", "published_ids.json"}:
            continue
        data = load_json(p, None)
        if isinstance(data, dict) and isinstance(data.get("translations"), dict):
            return p

    return ROOT / "economic_indicator_translations_latest.json"


def main():
    export = load_json(EXPORT, {})
    items = export.get("items", []) if isinstance(export, dict) else []
    if not isinstance(items, list) or not items:
        PUBLISHED_IDS.write_text("[]\n", encoding="utf-8")
        print("No approved items to merge.")
        return

    manifest = load_json(MANIFEST, {})
    dictionary_path = find_dictionary_file(manifest)
    dictionary = load_json(dictionary_path, {})
    if not isinstance(dictionary, dict):
        dictionary = {}
    translations = dictionary.setdefault("translations", {})
    if not isinstance(translations, dict):
        translations = {}
        dictionary["translations"] = translations

    changed = 0
    ids = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("event_name", "") or "").strip()
        ja = str(item.get("translation_ja", "") or "").strip()
        if not raw or not ja:
            continue
        entry = {
            "ja": ja,
            "stars": max(1, min(5, int(item.get("stars", 1) or 1))),
            "category": str(item.get("category", "") or "").strip(),
            "description": str(item.get("description_ja", "") or "").strip(),
            "impact_targets": str(item.get("impact_targets_ja", "") or "").strip(),
            "watch": str(item.get("watch_ja", "") or "").strip(),
            "direction": str(item.get("direction_ja", "") or "").strip(),
            "auto_generated": True,
            "generation_confidence": float(item.get("generation_confidence", 0) or 0),
            "verification_confidence": float(item.get("verification_confidence", 0) or 0),
            "source": "signalvision-dictionary-cloud"
        }
        if translations.get(raw) != entry:
            translations[raw] = entry
            changed += 1
        if isinstance(item.get("id"), int):
            ids.append(item["id"])

    dictionary["updated_at"] = datetime.now(timezone.utc).isoformat()
    dictionary["auto_managed"] = True
    dictionary_path.parent.mkdir(parents=True, exist_ok=True)
    dictionary_path.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if isinstance(manifest, dict):
        now = datetime.now(timezone.utc)
        manifest["latest_version"] = now.strftime("auto-%Y%m%d-%H%M%S")
        manifest["updated_at"] = now.isoformat()
        manifest["message"] = f"SignalVision Dictionary Cloud 自動同期: {changed}件更新"
        report_endpoint = os.environ.get("SVP_REPORT_ENDPOINT", "").strip()
        if report_endpoint:
            manifest["report_endpoint"] = report_endpoint.rstrip("/") + "/v1/report"
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    PUBLISHED_IDS.write_text(json.dumps(ids) + "\n", encoding="utf-8")
    print(f"Merged {changed} dictionary item(s) into {dictionary_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
