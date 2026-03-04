# Testing Pod 실행 가이드라인

RunPod GPU Pod 에서 OpenLLM 서빙 및 모델 평가를 수행하기 위한 가이드.

## 사전 조건

| 항목 | 값 |
|---|---|
| 플랫폼 | RunPod (GPU Pod) |
| GPU | RTX 5090 이상 권장 |
| Docker 이미지 | `docker/testing/Dockerfile` 기반 빌드 |
| Network Volume | `/workspace` 에 마운트됨 |
| 프로젝트 루트 | `/workspace/modelling` |

> **주의**: RunPod Network Volume이 `/workspace`에 FUSE 마운트되므로,
> Docker 빌드 시 `/workspace`에 COPY한 파일(스크립트, .venv 등)은 런타임에 가려집니다.
> 반드시 git clone 또는 수동 배포로 `/workspace/modelling`에 프로젝트를 배치하세요.

---

## 디렉토리 구조

```
/workspace/modelling/
├── utils/
│   ├── config.py              # HFConfig — .env 로딩 및 Python 설정 객체
│   ├── env.sh                 # 환경변수 (HF_TOKEN, HF_HOME 등) — shell 전용
│   ├── make-data.py           # raw 데이터 → LLM-as-Judge 테스트 데이터 변환
│   ├── model-pulling.py       # HuggingFace 모델 다운로드
│   ├── model-calling.py       # vLLM API 단일 호출
│   ├── model-testing.py       # vLLM API 5종 자동 테스트
│   ├── model-validation.py    # LLM-as-a-Judge 평가 파이프라인
│   └── model-monitoring.py    # GPU/CPU/RAM + vLLM 리소스 모니터링
├── data/
│   ├── raw/                   # 크롤링 원본 데이터
│   ├── processed/             # 전처리된 Q&A 데이터셋
│   └── monitoring/            # 리소스 모니터링 CSV 로그
├── .env                       # 시크릿 (HF_TOKEN 등) — git 미추적
├── pyproject.toml             # 프로젝트 의존성 정의
├── uv.lock                    # 의존성 잠금 파일
└── .python-version            # Python 3.12
```

---

## Step 0. 프로젝트 루트 이동

모든 명령은 프로젝트 루트에서 실행합니다.

```bash
cd /workspace/modelling
```

## Step 1. 의존성 설치

최초 1회 또는 의존성 변경 시 실행합니다.

```bash
uv sync --frozen --no-dev
```

## Step 2. 환경변수 설정

### 2-1. .env 파일 준비

프로젝트 루트에 `.env` 파일을 생성하고 HuggingFace 토큰을 기입합니다.

```bash
# /workspace/modelling/.env
HF_TOKEN=hf_YOUR_TOKEN_HERE
```

> `.env`는 `.gitignore`에 추가하여 토큰이 원격 저장소에 올라가지 않도록 합니다.

### 2-2. Shell 환경변수 적용

```bash
source utils/env.sh
```

`env.sh`는 프로젝트 루트의 `.env`를 자동으로 로딩한 뒤 아래 변수를 export 합니다.

| 변수 | 값 | 설명 |
|---|---|---|
| `HF_TOKEN` | `.env` 또는 RunPod 환경변수 | HuggingFace 인증 토큰 |
| `HUGGING_FACE_HUB_TOKEN` | `HF_TOKEN`과 동일 | 구버전 라이브러리 호환용 |
| `HF_HUB_ENABLE_HF_TRANSFER` | `1` | Rust 기반 고속 다운로더 활성화 |
| `HF_HOME` | `/workspace/.cache/huggingface` | 모델 캐시 루트 디렉토리 |
| `TRANSFORMERS_CACHE` | `$HF_HOME/hub` | transformers 모델 캐시 |
| `HF_DATASETS_CACHE` | `$HF_HOME/datasets` | datasets 캐시 |

> RunPod에서 Pod 환경변수로 `HF_TOKEN`을 주입한 경우, `.env` 없이도 동작합니다.

### 2-3. Python에서 설정 사용

Python 스크립트에서는 `utils/config.py`의 `hf_config` 객체로 동일한 설정을 가져올 수 있습니다.

```python
from utils.config import hf_config

print(hf_config.HF_TOKEN)               # HuggingFace 토큰
print(hf_config.HF_HOME)                # 캐시 디렉토리 경로
print(hf_config.HF_HUB_ENABLE_HF_TRANSFER)  # True
```

`HFConfig`는 `pydantic_settings.BaseSettings` 기반으로, 아래 순서로 값을 결정합니다.

```
환경변수 (export) > .env 파일 > 클래스 기본값
```

따라서 RunPod 환경변수 주입, `.env` 파일, 코드 기본값 세 가지 방식 모두 지원합니다.

## Step 3. 모델 다운로드

```bash
python utils/model-pulling.py --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
```

옵션:
- `--model` (필수): HuggingFace 모델 ID
- `--revision` (선택): 브랜치/태그 (기본값: `main`)

## Step 4. vLLM 서버 시작

```bash
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 \
    --port 8000 \
    --cpu-offload-gb 4 \
    --max-model-len 4096 \
    --enforce-eager \
    --gpu-memory-utilization 0.95 &
```

| 옵션 | 값 | 설명 |
|---|---|---|
| `--cpu-offload-gb` | `4` | 모델 가중치 4 GB를 CPU RAM으로 오프로드하여 VRAM 확보 |
| `--max-model-len` | `4096` | 최대 컨텍스트 길이 제한 (KV cache 메모리 절약) |
| `--enforce-eager` | - | CUDA graph 비활성화 (그래프 캡처용 추가 메모리 절약) |
| `--gpu-memory-utilization` | `0.95` | GPU 메모리 사용 비율 상향 (기본값 0.9) |

> **왜 이 옵션이 필요한가?**
> EXAONE-4.0-32B-FP8은 FP8 양자화 상태에서도 가중치가 ~31 GB입니다.
> RTX 5090(32 GB VRAM) 한 장에서는 가중치만으로 VRAM이 거의 꽉 차므로,
> CPU 오프로딩 없이는 모델 로딩 자체가 실패합니다 (`torch.OutOfMemoryError`).

서버가 `Ready` 로그를 출력할 때까지 대기합니다 (약 1~3분).

## Step 5. 단일 추론 호출

```bash
# 기본 호출
python utils/model-calling.py --prompt "인공지능이란 무엇인가요?"

# 옵션 지정
python utils/model-calling.py \
    --prompt "양자 컴퓨팅을 설명해주세요" \
    --max-tokens 512 \
    --temperature 0.3
```

옵션:
- `--prompt` (필수): 입력 프롬프트
- `--base-url` (선택): vLLM 서버 URL (기본값: `http://localhost:8000`)
- `--model` (선택): 모델 이름 (미지정 시 자동 감지)
- `--max-tokens` (선택): 최대 생성 토큰 수 (기본값: `256`)
- `--temperature` (선택): 샘플링 온도 (기본값: `0.7`)

## Step 6. API 자동 테스트 (5종)

```bash
python utils/model-testing.py
```

테스트 항목:
1. Health Check (`/health`)
2. Model Listing (`/v1/models`)
3. Chat Completion (`/v1/chat/completions`)
4. Text Completion (`/v1/completions`)
5. Streaming Chat Completion

## Step 7. LLM-as-a-Judge 모델 평가

```bash
# 전체 데이터셋 평가
python utils/model-validation.py

# 샘플 10건만 평가
python utils/model-validation.py --sample-size 10
```

평가 파이프라인:
1. `data/processed/processed_v3.csv`에서 Q&A 쌍 로드
2. context + question → 모델 답변 생성
3. (question, reference_answer, model_answer) → 같은 모델이 Judge로 채점
4. correctness / relevance / completeness 각 1~5점 집계
5. 결과 저장: `data/processed/validation_results.csv`

옵션:
- `--base-url` (선택): vLLM 서버 URL (기본값: `http://localhost:8000`)
- `--sample-size` (선택): 평가할 테스트 케이스 수 (`0` = 전체)

---

## 트러블슈팅: CUDA Out of Memory

### 증상

`vllm serve` 실행 시 아래와 같은 에러가 발생하며 서버가 기동되지 않음:

```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate X MiB.
```

### 원인

EXAONE-4.0-32B-FP8은 FP8(1 byte/param) 양자화에도 가중치가 ~31 GB를 차지합니다.
단일 GPU의 VRAM이 이를 수용하지 못하면 모델 로딩 단계에서 OOM이 발생합니다.

### GPU별 권장 설정

| GPU (VRAM) | `--cpu-offload-gb` | `--max-model-len` | `--enforce-eager` | `--gpu-memory-utilization` | 비고 |
|---|---|---|---|---|---|
| RTX 5090 (32 GB) | `4` | `4096` | 필수 | `0.95` | CPU 오프로딩 필수, v1 엔진 패치 필요 |
| A100 (40 GB) | `0` | `16384` | 선택 | `0.9` | 오프로딩 없이 서빙 가능 |
| A100 (80 GB) | `0` | `131072` | 불필요 | `0.9` | 풀 컨텍스트 사용 가능 |
| H100 (80 GB) | `0` | `131072` | 불필요 | `0.9` | 풀 컨텍스트 사용 가능 |

> `--max-model-len`을 줄이면 KV cache 메모리가 줄어들어 동시 처리 가능한 토큰 수가 감소합니다.
> 평가 목적이라면 `4096`~`8192`로도 충분합니다.

### vLLM 0.11.0 v1 엔진 cpu-offload 패치

vLLM 0.11.0의 v1 엔진은 `--cpu-offload-gb`와 함께 사용 시 아래 에러가 발생할 수 있습니다:

```
AssertionError: Cannot re-initialize the input batch when CPU weight offloading is enabled.
```

이 경우 `gpu_model_runner.py`의 assertion을 warning으로 전환하는 패치가 필요합니다:

```bash
# .venv 내 해당 파일 위치
RUNNER=".venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py"

# 패치 적용 (assertion → warning + return)
python -c "
import re, pathlib
p = pathlib.Path('$RUNNER')
src = p.read_text()
old = '''            assert self.cache_config.cpu_offload_gb == 0, (
                \"Cannot re-initialize the input batch when CPU weight \"
                \"offloading is enabled. See https://github.com/vllm-project/vllm/pull/18298 \"  # noqa: E501
                \"for more details.\")'''
new = '''            if self.cache_config.cpu_offload_gb != 0:
                logger.warning(
                    \"Skipping input batch re-initialization because CPU \"
                    \"weight offloading is enabled. \"
                    \"See https://github.com/vllm-project/vllm/pull/18298\")
                return'''
p.write_text(src.replace(old, new))
print('Patched successfully')
"
```

> `VLLM_USE_V1=0`(v0 엔진 전환)은 vLLM 0.11.0에서 지원되지 않습니다.
> 향후 vLLM 버전에서 이 제한이 해결되면 패치 없이 사용할 수 있습니다.

### 대안 모델

VRAM이 부족하여 CPU 오프로딩으로도 성능이 불만족스러운 경우, 더 작은 모델을 고려하세요.

| 모델 | 파라미터 | 필요 VRAM (추정) | 비고 |
|---|---|---|---|
| `LGAI-EXAONE/EXAONE-4.0-32B-FP8` | 32B (FP8) | ~31 GB | 현재 기본 모델 |
| `LGAI-EXAONE/EXAONE-4.0-7.8B` | 7.8B (FP16) | ~16 GB | 32 GB GPU에 여유롭게 적재 |

모델을 변경할 경우 Step 3~4의 모델 ID를 함께 수정하세요.

### 멀티 GPU 텐서 병렬화

GPU가 2장 이상인 환경에서는 `--tensor-parallel-size`로 모델을 분산 적재할 수 있습니다.

```bash
# 예시: GPU 2장 사용
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 2
```

## Step 8. 리소스 모니터링

vLLM 서빙 중 GPU/CPU/RAM 사용량과 vLLM 서버 메트릭을 실시간 모니터링합니다.

```bash
python utils/model-monitoring.py
```

대시보드 + CSV 로깅이 동시에 실행됩니다. `Ctrl+C`로 종료하면 CSV 파일 경로가 출력됩니다.

### 모니터링 항목

| 카테고리 | 메트릭 |
|---|---|
| GPU | 사용률(%), VRAM 사용량/전체(GB), 온도(°C), 전력(W) |
| CPU | 전체 사용률(%), 코어 수 |
| RAM | 사용량/전체(GB), 사용률(%) |
| vLLM | 서버 상태, 모델명, 실행/대기 요청 수, KV Cache 사용률, 처리량(tok/s) |

### 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--interval` | `2` | 폴링 간격 (초) |
| `--port` | `8000` | vLLM 서버 포트 |
| `--no-dashboard` | - | 대시보드 비활성화 (CSV 로깅만) |
| `--no-log` | - | CSV 로깅 비활성화 (대시보드만) |
| `--log-dir` | `data/monitoring` | CSV 저장 디렉토리 |
| `--duration` | `0` | 자동 종료 시간 (초, 0 = 무제한) |

### 사용 예시

```bash
# 모델 평가와 동시에 리소스 모니터링 (별도 터미널)
python utils/model-monitoring.py --duration 3600

# CSV 로깅만 (백그라운드)
python utils/model-monitoring.py --no-dashboard --interval 5 &

# 대시보드만 (로그 파일 없이)
python utils/model-monitoring.py --no-log
```

### CSV 출력

`data/monitoring/monitor_YYYYMMDD_HHMMSS.csv`에 저장됩니다.

```csv
timestamp,gpu_util,vram_used_gb,vram_total_gb,gpu_temp,gpu_power_w,cpu_util,ram_used_gb,ram_total_gb,vllm_online,vllm_requests_running,vllm_requests_waiting,vllm_gpu_cache_pct,vllm_cpu_cache_pct,vllm_prompt_tps,vllm_gen_tps
```

---

## (참고) 데이터 전처리

테스트 데이터셋을 새로 생성해야 할 경우:

```bash
python utils/make-data.py
```

입출력:
- 입력: `data/raw/raw_v2.csv` (크롤링 원본)
- 출력: `data/processed/processed_v3.csv` (LLM-as-Judge용 Q&A 쌍)

---

## 전체 실행 요약 (Quick Start)

```bash
cd /workspace/modelling

# 1. 토큰 설정 (.env 미리 준비하거나 RunPod 환경변수로 주입)
echo "HF_TOKEN=hf_YOUR_TOKEN_HERE" > .env

# 2. 의존성 설치 및 환경변수 적용
uv sync --frozen --no-dev
source utils/env.sh

# 3. 모델 다운로드 → 서버 기동
python utils/model-pulling.py --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 --port 8000 \
    --cpu-offload-gb 4 --max-model-len 4096 \
    --enforce-eager --gpu-memory-utilization 0.95 &
# (서버 Ready 로그 확인 후 진행)

# 4. 테스트 및 평가
python utils/model-testing.py
python utils/model-validation.py --sample-size 10

# 5. 리소스 모니터링 (별도 터미널 또는 백그라운드)
python utils/model-monitoring.py
```
