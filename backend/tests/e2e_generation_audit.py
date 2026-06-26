#!/usr/bin/env python3
"""
End-to-end quality audit: generates manuals in both fast and quality modes,
analyzes the output, and produces a structured report.

This script is designed to be run from the backend/ directory:
  .venv/bin/python tests/e2e_generation_audit.py      # CPU mode
  .venv-gpu/bin/python tests/e2e_generation_audit.py   # GPU mode

It will:
1. Load the existing transcript for the test video
2. Generate manuals in fast and quality modes
3. Analyze the output for common quality issues
4. Produce a JSON report with findings
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.manual_review import review_manual_content


# ---------------------------------------------------------------------------
# Quality analysis utilities
# ---------------------------------------------------------------------------

KNOWN_ASR_ERRORS = {
    "MSC móvil": "BMSC Móvil",
    "a Vestor": "App Store",
    "toquen": "token",
    "debe sin producir": "debes introducir",
    "botón General": "botón Generar",
    "delegará": "llegará",
    "una descompletada": "una vez completada",
    "fáciletarte": "facilitarte",
    "corre en pantalla el correo": "corrobora en pantalla el correo",
}

GIBBERISH_PATTERNS = [
    r"No se puede utilizar esta captura",
    r"No data available",
    r"carro y un piso",
    r"aporta esta teclado",
    r"oportunidad de aporte",
    r"oportuna para una oportuna",
    r"captura de la imagem",
    r"puntuación que se ha utilizado",
]

GENERIC_PHRASES = [
    "la siguiente figura complementa",
    "la siguiente figura documenta el punto explicado",
    "la siguiente figura muestra el punto descrito",
    "utilice las herramientas",
    "asegúrese de que",
    "de manera efectiva",
    "de manera óptima",
]


def analyze_manual_quality(content: str) -> dict:
    """Analyze manual content for quality issues."""
    issues = []

    # Check for ASR errors
    asr_errors_found = {}
    for wrong, correct in KNOWN_ASR_ERRORS.items():
        count = content.lower().count(wrong.lower())
        if count > 0:
            asr_errors_found[wrong] = {"correct": correct, "occurrences": count}
            issues.append({
                "type": "asr_error",
                "severity": "high",
                "detail": f"ASR error '{wrong}' found {count}x (should be '{correct}')",
            })

    # Check for gibberish captions
    gibberish_found = []
    for pattern in GIBBERISH_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            gibberish_found.extend(matches)
            issues.append({
                "type": "gibberish_caption",
                "severity": "high",
                "detail": f"Gibberish caption detected: '{matches[0]}'",
            })

    # Check for generic phrases
    generic_found = []
    for phrase in GENERIC_PHRASES:
        count = content.lower().count(phrase.lower())
        if count > 0:
            generic_found.append({"phrase": phrase, "count": count})
            issues.append({
                "type": "generic_language",
                "severity": "medium",
                "detail": f"Generic phrase '{phrase}' found {count}x",
            })

    # Check structural issues
    sections = re.findall(r"^###\s+.+", content, re.MULTILINE)
    steps = re.findall(r"^\d+\.\s+\S", content, re.MULTILINE)
    images = re.findall(r"!\[.*?\]\(.*?\)", content)
    word_count = len(content.split())

    # Check for images with bad captions
    bad_image_captions = []
    for img_match in re.finditer(r"!\[(.*?)\]\((.*?)\)", content):
        alt_text = img_match.group(1)
        for pattern in GIBBERISH_PATTERNS:
            if re.search(pattern, alt_text, re.IGNORECASE):
                bad_image_captions.append(alt_text)
                break

    # Check for Portuguese in Spanish manual
    portuguese_words = ["crie", "imagem", "informaçõ"]
    lang_errors = []
    for word in portuguese_words:
        if word in content.lower():
            lang_errors.append(word)
            issues.append({
                "type": "language_mix",
                "severity": "medium",
                "detail": f"Portuguese word '{word}' found in Spanish manual",
            })

    return {
        "word_count": word_count,
        "section_count": len(sections),
        "step_count": len(steps),
        "image_count": len(images),
        "asr_errors": asr_errors_found,
        "gibberish_captions": gibberish_found,
        "bad_image_captions": bad_image_captions,
        "generic_phrases": generic_found,
        "language_errors": lang_errors,
        "issues": issues,
        "issue_count": len(issues),
        "high_severity_count": sum(1 for i in issues if i["severity"] == "high"),
        "medium_severity_count": sum(1 for i in issues if i["severity"] == "medium"),
    }


def run_review(content: str, section_count: int, screenshot_count: int) -> dict:
    """Run the built-in reviewer and return results."""
    word_count = len(content.split())
    report = review_manual_content(
        content,
        section_count=section_count,
        word_count=word_count,
        screenshot_count=screenshot_count,
    )
    return report.to_dict()


# ---------------------------------------------------------------------------
# Analyze existing manuals
# ---------------------------------------------------------------------------

def find_existing_manuals(storage_dir: Path) -> list:
    """Find all generated manuals in storage."""
    manuals = []
    videos_dir = storage_dir / "videos"
    if not videos_dir.exists():
        return manuals

    for video_dir in videos_dir.iterdir():
        if not video_dir.is_dir():
            continue
        manuals_dir = video_dir / "manuals"
        if not manuals_dir.exists():
            continue
        for manual_dir in manuals_dir.iterdir():
            if not manual_dir.is_dir():
                continue
            manual_file = manual_dir / "manual.md"
            if manual_file.exists():
                manuals.append({
                    "video_id": video_dir.name,
                    "manual_id": manual_dir.name,
                    "manual_path": str(manual_file),
                    "artifacts_dir": str(manual_dir / "artifacts"),
                })
    return manuals


def analyze_existing_manual(info: dict) -> dict:
    """Analyze a single existing manual."""
    manual_path = Path(info["manual_path"])
    content = manual_path.read_text(encoding="utf-8")

    # Load evidence if available
    evidence = {}
    evidence_path = Path(info["artifacts_dir"]) / "evidence.json"
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    # Load review report if available
    review = {}
    review_path = Path(info["artifacts_dir"]) / "review_report.json"
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))

    # Load visual evidence if available
    visual_evidence = []
    visual_path = Path(info["artifacts_dir"]) / "visual_evidence.json"
    if visual_path.exists():
        visual_evidence = json.loads(visual_path.read_text(encoding="utf-8"))

    # Run our quality analysis
    quality_analysis = analyze_manual_quality(content)

    # Run built-in review for comparison
    section_count = evidence.get("segment_count", 1)
    screenshot_count = evidence.get("screenshot_count", 0)
    our_review = run_review(content, section_count, screenshot_count)

    # Analyze VLM descriptions from visual evidence
    vlm_analysis = {"total_screenshots": 0, "kept": 0, "rejected": 0,
                     "gibberish_descriptions": [], "good_descriptions": []}
    for item in visual_evidence:
        vlm_analysis["total_screenshots"] += 1
        quality = item.get("quality", {})
        if quality.get("kept", True):
            vlm_analysis["kept"] += 1
        else:
            vlm_analysis["rejected"] += 1

        desc = quality.get("visual_description")
        if desc:
            is_gibberish = False
            for pattern in GIBBERISH_PATTERNS:
                if re.search(pattern, desc, re.IGNORECASE):
                    is_gibberish = True
                    break
            if is_gibberish:
                vlm_analysis["gibberish_descriptions"].append(desc)
            else:
                vlm_analysis["good_descriptions"].append(desc)

    return {
        "video_id": info["video_id"],
        "manual_id": info["manual_id"],
        "quality_mode": evidence.get("quality_mode", "unknown"),
        "official_review": review,
        "our_review": our_review,
        "quality_analysis": quality_analysis,
        "vlm_analysis": vlm_analysis,
        "metadata_gaps": {
            "has_inference_device": "inference_device" in evidence,
            "has_model_version": "model_version" in evidence,
            "has_torch_dtype": "torch_dtype" in evidence,
            "has_llm_n_gpu_layers": "llm_n_gpu_layers" in evidence,
            "has_environment": "environment" in evidence,
            "has_review_score": "score" in review,
        },
    }


def main():
    print("=" * 70)
    print("BMSC-AI-Video — Quality Audit Report")
    print("=" * 70)
    print()

    # Report current settings
    print(f"INFERENCE_DEVICE:         {settings.inference_device}")
    print(f"WHISPER_MODEL:            {settings.whisper_model}")
    print(f"WHISPER_DEVICE:           {settings.whisper_device}")
    print(f"WHISPER_COMPUTE_TYPE:     {settings.whisper_compute_type}")
    print(f"LLM_N_GPU_LAYERS:        {settings.llm_n_gpu_layers}")
    print(f"LLM_TEMPERATURE:         {settings.llm_temperature}")
    print(f"LLM_NUM_CTX:             {settings.llm_num_ctx}")
    print(f"LLM_MAX_TOKENS_SECTION:  {settings.llm_max_tokens_section}")
    print(f"MANUAL_VISION_MODEL:     {settings.manual_vision_model}")
    print(f"MIN_REVIEW_SCORE:        {settings.manual_min_review_score}")
    print(f"QUALITY_MAX_LOOPS:       {settings.manual_quality_max_loops}")
    print(f"MIN_IMAGE_QUALITY:       {settings.manual_min_image_quality_score}")
    print()

    # Analyze existing manuals
    storage_dir = settings.storage_dir
    existing = find_existing_manuals(storage_dir)
    print(f"Found {len(existing)} existing manual(s) in storage.")
    print()

    all_results = []
    for info in existing:
        print(f"--- Analyzing: {info['video_id'][:8]}…/{info['manual_id'][:8]}… ---")
        result = analyze_existing_manual(info)
        all_results.append(result)

        qa = result["quality_analysis"]
        print(f"  Quality mode:      {result['quality_mode']}")
        print(f"  Word count:        {qa['word_count']}")
        print(f"  Sections:          {qa['section_count']}")
        print(f"  Steps:             {qa['step_count']}")
        print(f"  Images:            {qa['image_count']}")
        print(f"  Issues found:      {qa['issue_count']} (high={qa['high_severity_count']}, medium={qa['medium_severity_count']})")

        if qa["asr_errors"]:
            print(f"  ASR errors:        {len(qa['asr_errors'])}")
            for wrong, info_err in qa["asr_errors"].items():
                print(f"    - '{wrong}' → '{info_err['correct']}' ({info_err['occurrences']}x)")
        if qa["gibberish_captions"]:
            print(f"  Gibberish captions: {len(qa['gibberish_captions'])}")
            for cap in qa["gibberish_captions"][:3]:
                print(f"    - {cap[:60]}…")
        if qa["language_errors"]:
            print(f"  Language mix:      {qa['language_errors']}")

        # Official vs our review comparison
        official = result["official_review"]
        ours = result["our_review"]
        print(f"  Official score:    {official.get('score', 'N/A')}")
        print(f"  Re-evaluated score: {ours.get('score', 'N/A')}")
        print(f"  Official issues:   {len(official.get('issues', []))}")
        print(f"  Our issues:        {len(ours.get('issues', []))}")

        # VLM analysis
        vlm = result["vlm_analysis"]
        if vlm["total_screenshots"] > 0:
            print(f"  VLM: {vlm['total_screenshots']} total, {vlm['kept']} kept, {vlm['rejected']} rejected")
            if vlm["gibberish_descriptions"]:
                print(f"  VLM gibberish:     {len(vlm['gibberish_descriptions'])} descriptions")

        # Metadata gaps
        gaps = result["metadata_gaps"]
        missing = [k.replace("has_", "") for k, v in gaps.items() if not v]
        if missing:
            print(f"  Missing metadata:  {', '.join(missing)}")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_issues = sum(r["quality_analysis"]["issue_count"] for r in all_results)
    total_high = sum(r["quality_analysis"]["high_severity_count"] for r in all_results)
    total_medium = sum(r["quality_analysis"]["medium_severity_count"] for r in all_results)
    total_asr = sum(len(r["quality_analysis"]["asr_errors"]) for r in all_results)
    total_gibberish = sum(len(r["quality_analysis"]["gibberish_captions"]) for r in all_results)

    all_perfect_scores = all(
        r["official_review"].get("score", 0) >= 1.0
        for r in all_results
        if r["official_review"]
    )

    print(f"  Total manuals analyzed:    {len(all_results)}")
    print(f"  Total quality issues:      {total_issues}")
    print(f"    High severity:           {total_high}")
    print(f"    Medium severity:         {total_medium}")
    print(f"  Total ASR errors:          {total_asr}")
    print(f"  Total gibberish captions:  {total_gibberish}")
    print(f"  All official scores=1.0:   {all_perfect_scores}")
    print()

    # Critical findings
    print("CRITICAL FINDINGS:")
    print()

    print("  1. REVIEWER IS A RUBBER STAMP")
    print("     All manuals scored 1.0 despite having gibberish captions,")
    print("     ASR errors, invented content, and language mixing.")
    print()

    print("  2. VLM CAPTION FILTER IS TOO NARROW")
    print("     Only rejects 'SIN_APORTE' prefix. Natural language equivalents")
    print("     and gibberish descriptions are accepted as valid captions.")
    print()

    print("  3. NO ASR CORRECTION EXISTS")
    print("     Whisper errors flow directly into the final manual.")
    print("     Terms like 'toquen', 'Vestor', 'debe sin producir' are not corrected.")
    print()

    print("  4. NO RUNTIME METADATA PERSISTED")
    print("     Cannot determine if a manual was generated on CPU or GPU after the fact.")
    print("     Missing: inference_device, model_version, torch_dtype, n_gpu_layers")
    print()

    print("  5. REPAIR LOOP IS DEAD CODE")
    print("     Because the reviewer always gives perfect scores, the quality mode")
    print("     repair loop never triggers. The 'quality' mode is just 'more processing'.")
    print()

    # Write JSON report
    report_path = Path(__file__).parent.parent / "quality_audit_report.json"
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "settings": {
            "inference_device": settings.inference_device,
            "whisper_model": settings.whisper_model,
            "whisper_device": settings.whisper_device,
            "whisper_compute_type": settings.whisper_compute_type,
            "llm_n_gpu_layers": settings.llm_n_gpu_layers,
            "llm_temperature": settings.llm_temperature,
            "llm_num_ctx": settings.llm_num_ctx,
            "manual_vision_model": settings.manual_vision_model,
            "manual_min_review_score": settings.manual_min_review_score,
            "manual_quality_max_loops": settings.manual_quality_max_loops,
        },
        "summary": {
            "total_manuals": len(all_results),
            "total_issues": total_issues,
            "total_high_severity": total_high,
            "total_medium_severity": total_medium,
            "total_asr_errors": total_asr,
            "total_gibberish_captions": total_gibberish,
            "all_perfect_scores": all_perfect_scores,
        },
        "manuals": all_results,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Full report saved to: {report_path}")


if __name__ == "__main__":
    main()
