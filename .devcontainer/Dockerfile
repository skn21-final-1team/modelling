FROM vllm/vllm-openai:latest
FROM runpod


ENV PYTHONUNBUFFERED=1 \
    HUGGINGFACE_HUB_CACHE=/runpod-volume/huggingface \
    TRANSFORMERS_CACHE=/runpod-volume/huggingface

RUN pip install 

COPY handler.py /handler.py

CMD ["python", "-u", "/handler.py"]