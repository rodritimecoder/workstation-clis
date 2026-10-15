#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "scripts"))
import llm_client

if __name__ == "__main__":
    llm_client.main()
