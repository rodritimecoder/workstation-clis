#!/usr/bin/env bash
set -e

CONTAINER_NAME="vllm-rocm"
IMAGE="docker.io/rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0"
MODELS_DIR="/run/media/rodri/AI/models"

# Clean up existing container with same name if already running/stopped
if podman container exists "$CONTAINER_NAME" 2>/dev/null; then
    echo "Cleaning up previous $CONTAINER_NAME instance..."
    podman rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

echo "=========================================================="
echo " Starting vLLM ROCm container"
echo " Models directory: $MODELS_DIR -> /app/models"
echo " Dual AMD Radeon RX 9060 XT (ROCm 10.1.0)"
echo " To exit: type 'exit' or press Ctrl+D"
echo "=========================================================="

CMD=("bash")
if [ "$#" -gt 0 ]; then
    CMD=("$@")
fi

podman run -it --rm \
  --name "$CONTAINER_NAME" \
  --device /dev/kfd \
  --device /dev/dri \
  --network=host \
  --ipc=host \
  --group-add keep-groups \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v "$MODELS_DIR":/app/models \
  -e HF_HOME="/app/models" \
  "$IMAGE" \
  "${CMD[@]}"

echo ""
read -p "Container exited. Press [Enter] to close..."
