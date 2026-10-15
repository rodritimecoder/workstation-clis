# local-hub

Workstation Local Hardware Inference Hub & Skills Gateway.

Unifies all local Dual AMD Radeon RX 9060 XT GPU inference models into a single tool:
- **`local-hub llm`**: Qwen3.6-35B-A3B Genesis on port `:8080`
- **`local-hub ocr`**: LightOnOCR-3-1B Document & Slide Vision on port `:8085`
- **`local-hub decide`**: Imajev-4B / JPT-4B Calibrated Decisions on port `:8083` / `:8090`
- **`local-hub asr`**: audio.cpp Nemotron 3.5 Speech-to-Text on port `:8081`
- **`local-hub status`**: Real-time port and Tailscale status table
- **`local-hub search` / `run`**: Uber OmniMCP skill discovery and execution gateway
