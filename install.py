#!/usr/bin/env python3
"""
Blockonomics Merchant Assistant — Quick Installer

Run:  python install.py
"""
import os
import shutil
import subprocess
import sys


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=True)
    if result.returncode != 0:
        sys.exit(1)


def main() -> None:
    print("\n=== Blockonomics Merchant Assistant Setup ===\n")

    # 1. Install Python dependencies
    print("Installing Python dependencies…")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    print("  ✓ Dependencies installed\n")

    # 2. Create .env from .env.example if not present
    if not os.path.exists(".env"):
        shutil.copy(".env.example", ".env")
        print("Created .env from .env.example")
        print("  ⚠  Fill in your API keys in .env before starting:\n")
        print("     ANTHROPIC_API_KEY=sk-ant-...")
        print("     BLOCKONOMICS_API_KEY=...")
        print("     BLOCKONOMICS_WEBHOOK_SECRET=<random string>")
        print("     MERCHANT_URL=https://your-domain.com\n")
    else:
        print("  ✓ .env already exists\n")

    # 3. Check required env vars
    from dotenv import load_dotenv
    load_dotenv()

    missing = []
    for key in ["ANTHROPIC_API_KEY", "BLOCKONOMICS_API_KEY", "BLOCKONOMICS_WEBHOOK_SECRET"]:
        val = os.getenv(key, "")
        if not val or val.startswith("your_"):
            missing.append(key)

    if missing:
        print("⚠  The following required keys are not set in .env:")
        for k in missing:
            print(f"   - {k}")
        print("\nEdit .env and then run:  uvicorn main:app --reload\n")
    else:
        print("  ✓ All required env vars are set\n")

        # 4. Print embed snippet
        merchant_url = os.getenv("MERCHANT_URL", "http://localhost:8000")
        print("=== Embed Snippet ===")
        print("Add this to your merchant dashboard HTML (just before </body>):\n")
        print(
            f'<script src="{merchant_url}/embed.js"'
            f' data-api="{merchant_url}"'
            f' data-position="bottom-right"'
            f' data-label="Assistant"></script>'
        )
        print("\n" + "="*40)
        print("\nStart the assistant:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
        print("Then open:            http://localhost:8000/widget  (to preview the chat panel)")
        print()


if __name__ == "__main__":
    main()
