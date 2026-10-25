#!/usr/bin/env python3
"""
Reproducible generator for FlyGuard AI submission deliverables:
- deliverables/FlyGuard_AI_Pitch_Deck.pdf   (10-slide 16:9 HD PDF Pitch Deck)
- deliverables/FlyGuard_AI_Pitch_Deck.pptx  (10-slide 16:9 PowerPoint PPTX)
- deliverables/FlyGuard_AI_Demo_Video.mp4   (75-second 1080p Full HD Product Walkthrough Video)
"""
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES_DIR = PROJECT_ROOT / "deliverables"
DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_GENERATOR = Path(
    "/home/that-coder-guy/.gemini/antigravity/brain/1d7e1ef7-ffe0-47bb-af6f-f429fbd48e24/scratch/generate_submission_assets.py"
)

if __name__ == "__main__":
    if ARTIFACT_GENERATOR.exists():
        subprocess.run([sys.executable, str(ARTIFACT_GENERATOR)], check=True)
        src_dir = ARTIFACT_GENERATOR.parents[1]
        for fname in [
            "FlyGuard_AI_Pitch_Deck.pdf",
            "FlyGuard_AI_Pitch_Deck.pptx",
            "FlyGuard_AI_Demo_Video.mp4",
        ]:
            src = src_dir / fname
            if src.exists():
                shutil.copy2(src, DELIVERABLES_DIR / fname)
                print(f"[OK] Copied {fname} -> {DELIVERABLES_DIR / fname}")

