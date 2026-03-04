# 0. 프로젝트 루트로 이동
cd /workspace/modelling

# 1. 환경변수 설정
source utils/env.sh

# 2. 모델 다운로드
python utils/model-pulling.py --model meta-llama/Llama-3.1-8B-Instruct
python utils/model-pulling.py --model meta-llama/Llama-3.1-8B-Instruct --revision main

# 3. vLLM 서버 시작 (백그라운드)
vllm serve meta-llama/Llama-3.1-8B-Instruct --host 0.0.0.0 --port 8000 &

# 4. 단일 호출
python utils/model-calling.py --prompt "Hello world"
python utils/model-calling.py --prompt "Explain AI" --max-tokens 512 --temperature 0.3
python utils/model-calling.py --prompt "Hi" --model meta-llama/Llama-3.1-8B-Instruct

# 5. 자동 테스트 (health, models, chat, completion, streaming 5개 테스트)
python utils/model-testing.py
python utils/model-testing.py --base-url http://localhost:8000
