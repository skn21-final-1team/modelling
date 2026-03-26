FROM runpod/worker-v1-vllm:v2.14.0

ENV MODEL_NAME="LGAI-EXAONE/EXAONE-4.0-32B-FP8" \
    MAX_MODEL_LEN=8192 \
    TENSOR_PARALLEL_SIZE=1 \
    GPU_MEMORY_UTILIZATION=0.90

RUN --mount=type=secret,id=HF_TOKEN \
    if [ -f /run/secrets/HF_TOKEN ]; then export HF_TOKEN=$(cat /run/secrets/HF_TOKEN); fi && \
    python3 /src/download_model.py
