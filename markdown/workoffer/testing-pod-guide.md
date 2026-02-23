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
│   ├── env.sh                 # 환경변수 (HF_TOKEN, HF_HOME 등)
│   ├── make-data.py           # raw 데이터 → LLM-as-Judge 테스트 데이터 변환
│   ├── model-pulling.py       # HuggingFace 모델 다운로드
│   ├── model-calling.py       # vLLM API 단일 호출
│   ├── model-testing.py       # vLLM API 5종 자동 테스트
│   └── model-validation.py    # LLM-as-a-Judge 평가 파이프라인
├── data/
│   ├── raw/                   # 크롤링 원본 데이터
│   └── processed/             # 전처리된 Q&A 데이터셋
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

```bash
source utils/env.sh
```

설정되는 변수:
- `HF_TOKEN` — HuggingFace 인증 토큰 (gated model 접근용)
- `HF_HUB_ENABLE_HF_TRANSFER=1` — Rust 기반 고속 다운로더 활성화
- `HF_HOME` — 모델 캐시 디렉토리 (`/workspace/.cache/huggingface`)

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
    --port 8000 &
```

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
uv sync --frozen --no-dev
source utils/env.sh

python utils/model-pulling.py --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 --host 0.0.0.0 --port 8000 &
# (서버 Ready 대기)

python utils/model-testing.py
python utils/model-validation.py --sample-size 10
```
