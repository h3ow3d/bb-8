# BB-8 Model Strategy

## Overview

BB-8 uses [Ollama](https://ollama.com/) as its local LLM runtime. No model weights are committed to the repository or baked into the application container.

## Default model

The default model is **`qwen2.5:7b-instruct`**.

- Well-suited for instruction-following and structured reasoning tasks
- Approximately 4-5 GB download (Q4 quantized)
- Runs on CPU (slow) or GPU (fast)
- RTX 3070 class GPUs (8 GB VRAM) handle 7B quantized models comfortably

## Alternative models

Set `OLLAMA_MODEL` in `deploy/compose/.env` to change the model. Compatible alternatives:

| Model | Notes |
|-------|-------|
| `qwen2.5:7b-instruct` | Default. Good instruction following. |
| `llama3.1:8b-instruct` | Meta LLaMA 3.1 8B instruction model |
| `mistral:7b-instruct` | Mistral 7B instruction model |
| `phi3:medium-instruct` | Microsoft Phi-3 medium |

Any Ollama-compatible instruction model can be used. Larger models (13B, 70B) require more VRAM and are slower.

## GPU acceleration

The Docker Compose configuration includes NVIDIA GPU reservation:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Requirements:
- NVIDIA GPU with 8+ GB VRAM for 7B models
- NVIDIA Container Toolkit installed on the host
- Docker configured with the `nvidia` runtime

Remove the `deploy` section from `docker-compose.yml` to force CPU-only inference.

## Pulling models

```bash
scripts/pull-model.sh
```

This script reads `OLLAMA_MODEL` from `.env` and pulls the model via the Ollama API.

For air-gapped environments:
1. Pull the model on a machine with internet access.
2. Export the `bb8_ollama_data` Docker volume.
3. Transfer to the air-gapped host.
4. Import the volume before starting the stack.

## What happens if the model is missing

If Ollama is running but the configured model is not pulled, BB-8 returns:

```json
{
  "warnings": ["Local LLM explanation unavailable: model 'qwen2.5:7b-instruct' not found. Run scripts/pull-model.sh to download it."]
}
```

Deterministic findings are still returned. The LLM explanation is empty.

## What happens if Ollama is unavailable

If the Ollama container is not running, BB-8 returns:

```json
{
  "warnings": ["Local LLM explanation unavailable: could not reach Ollama at http://ollama:11434."]
}
```

Deterministic findings are always returned regardless of Ollama availability.

## Future options

- **llama.cpp** as an alternative runtime for systems without Docker GPU support
- **vLLM** for higher throughput on multi-GPU systems
- **Offline bundle** mode: export model weights alongside the release bundle for fully offline deployment
