# 리소스 모니터링 도구 작업 이력

vLLM 모델 서빙 중 하드웨어(GPU/CPU/RAM) 및 vLLM 서버 메트릭을 실시간 추적하는 CLI 모니터링 도구 구현 과정 기록.

---

## 1. 배경 및 목적

EXAONE-4.0-32B-FP8을 RTX 5090(32 GB VRAM) 단일 GPU에서 서빙할 때, VRAM이 ~31 GB로 거의 한계치까지 사용됨.
`--cpu-offload-gb 4` 옵션으로 가중치 일부를 CPU RAM으로 오프로딩하는 상황에서, 실시간으로 리소스 사용량을 추적하고 기록할 필요가 있었음.

**요구사항:**

- GPU 사용률, VRAM, 온도, 전력 실시간 확인
- CPU 사용률, RAM 사용량 확인
- vLLM 서버 상태 (요청 수, KV cache, 처리량) 확인
- CSV 로깅으로 시간에 따른 리소스 변화 추적
- 터미널 대시보드로 시각적 모니터링

---

## 2. 기술 선택

### 검토한 대안

| 방식 | 장점 | 단점 | 채택 |
|------|------|------|------|
| `nvidia-smi` + `watch` | 설치 불필요 | GPU만 모니터링, CSV 로깅 불가, vLLM 메트릭 없음 | X |
| Prometheus + Grafana | 풍부한 시각화 | 별도 서버 필요, Pod 환경에서 과도한 구성 | X |
| Python CLI (`rich` + `psutil` + `pynvml`) | 단일 파일, 경량, CSV 로깅 포함 | 직접 구현 필요 | O |

### 채택 이유

- 기존 `utils/` 스크립트 패턴(`model-calling.py`, `model-testing.py`)과 일관성 유지
- 별도 인프라 없이 `python utils/model-monitoring.py` 한 줄로 실행 가능
- `rich` 라이브러리의 `Live` 컴포넌트로 터미널 대시보드 구현이 간결함

---

## 3. 의존성 추가

`pyproject.toml`에 3개 패키지 추가:

```python
"psutil",       # CPU/RAM 메트릭 수집
"nvidia-ml-py", # NVIDIA GPU 메트릭 (NVML Python 바인딩)
"rich",         # 터미널 대시보드 UI
```

> `pynvml` 패키지는 deprecated 상태이므로 `nvidia-ml-py`를 직접 의존성으로 지정.
> `nvidia-ml-py`가 `pynvml` 모듈을 제공하므로 import 경로는 동일하게 `import pynvml` 사용.
> `psutil`과 `rich`는 vLLM의 간접 의존성으로 이미 설치되어 있었으나, 명시적 의존성으로 추가.

---

## 4. 구현 구조

### 아키텍처

```
model-monitoring.py
├── 데이터 모델 (dataclass)
│   ├── GpuMetrics      — GPU 사용률, VRAM, 온도, 전력
│   ├── SystemMetrics   — CPU 사용률, RAM 사용량
│   ├── VllmMetrics     — 요청 수, KV cache, 처리량
│   └── Snapshot        — 위 3개를 묶은 시점별 스냅샷
├── Collector (메트릭 수집)
│   ├── GpuCollector    — pynvml (NVML) 기반 GPU 메트릭
│   ├── SystemCollector — psutil 기반 CPU/RAM 메트릭
│   └── VllmCollector   — /metrics 엔드포인트 Prometheus 텍스트 파싱
├── CsvLogger           — CSV 파일 기록
├── Dashboard Renderer  — rich Live 기반 터미널 UI
└── Main Loop           — 주기적 수집 → 표시/기록
```

### GPU 메트릭 수집

`nvidia-ml-py`의 NVML API로 GPU 메트릭을 직접 수집:

- `nvmlDeviceGetUtilizationRates()` → GPU 사용률 (%)
- `nvmlDeviceGetMemoryInfo()` → VRAM 사용량/전체 (bytes → GB 변환)
- `nvmlDeviceGetTemperature()` → GPU 온도 (°C)
- `nvmlDeviceGetPowerUsage()` → 전력 소비 (mW → W 변환)
- `nvmlDeviceGetEnforcedPowerLimit()` → 전력 한도 (mW → W 변환)

> GPU 인덱스 0번만 사용 (단일 GPU Pod 환경 전제).
> `pynvml` import 실패 시 graceful fallback — GPU 섹션이 N/A로 표시됨.

### vLLM 메트릭 수집

vLLM은 `/metrics` 엔드포인트에서 Prometheus 텍스트 형식으로 메트릭을 노출.
정규식으로 주요 gauge 값을 파싱:

| 메트릭 이름 | 설명 |
|-------------|------|
| `vllm:num_requests_running` | 현재 처리 중인 요청 수 |
| `vllm:num_requests_waiting` | 대기 중인 요청 수 |
| `vllm:gpu_cache_usage_perc` | KV cache GPU 사용률 (0~1 → 0~100% 변환) |
| `vllm:cpu_cache_usage_perc` | KV cache CPU 사용률 (0~1 → 0~100% 변환) |
| `vllm:avg_prompt_throughput_toks_per_s` | 평균 프롬프트 처리량 |
| `vllm:avg_generation_throughput_toks_per_s` | 평균 생성 처리량 |

> vLLM 서버가 꺼져 있으면 `online: false`로 표시되고 vLLM 섹션이 Offline으로 표시됨.
> 모델 이름은 `/v1/models` 엔드포인트에서 자동 감지하여 1회만 캐싱.

### 대시보드 UI

`rich.live.Live`로 터미널에 실시간 갱신되는 대시보드 렌더링:

```
╭─────────────────────────── vLLM Resource Monitor ────────────────────────────╮
│ Uptime: 0:00:04  Interval: 2.0s  Log: data/monitoring/monitor_*.csv        │
│ ╭───────────────────── GPU (NVIDIA GeForce RTX 5090) ──────────────────────╮ │
│ │     Utilization:  ░░░░░░░░░░░░░░░░░░░░    0.0%                           │ │
│ │            VRAM:  ███████████████████░  30.9 / 31.8 GB (97%)             │ │
│ │    Temp / Power:  37°C    11W / 575W                                     │ │
│ ╰──────────────────────────────────────────────────────────────────────────╯ │
│ ╭────────────────────────────── CPU & Memory ──────────────────────────────╮ │
│ │             CPU:  █░░░░░░░░░░░░░░░░░░░    4.8%  (256 cores)              │ │
│ │             RAM:  ████░░░░░░░░░░░░░░░░  97.0 / 503.5 GB (19%)            │ │
│ ╰──────────────────────────────────────────────────────────────────────────╯ │
│ ╭────────────────────────────── vLLM Server ───────────────────────────────╮ │
│ │          Status:  Online    Model: LGAI-EXAONE/EXAONE-4.0-32B-FP8        │ │
│ │        Requests:  Running: 0  |  Waiting: 0                              │ │
│ │        KV Cache:  GPU: ░░░░░░░░░░   0.0%  |  CPU: ░░░░░░░░░░   0.0%      │ │
│ │      Throughput:  Prompt: 0.0 tok/s  |  Gen: 0.0 tok/s                   │ │
│ ╰──────────────────────────────────────────────────────────────────────────╯ │
╰──────────────────────────────────────────────────────────────────────────────╯
```

프로그레스 바 색상: <50% 녹색, 50~80% 노란색, >80% 빨간색.

### CSV 로깅

`data/monitoring/monitor_YYYYMMDD_HHMMSS.csv` 경로에 타임스탬프별 메트릭 기록:

```
timestamp,gpu_util,vram_used_gb,vram_total_gb,gpu_temp,gpu_power_w,cpu_util,ram_used_gb,ram_total_gb,vllm_online,vllm_requests_running,vllm_requests_waiting,vllm_gpu_cache_pct,vllm_cpu_cache_pct,vllm_prompt_tps,vllm_gen_tps
2026-02-23 18:44:39,0.0,30.95,31.84,37,10.9,4.5,96.29,503.51,1,0,0,0.0,0.0,0.0,0.0
```

---

## 5. 파일 변경 요약

| 파일 | 변경 |
|------|------|
| `utils/model-monitoring.py` | 신규 — 모니터링 CLI 스크립트 (559줄) |
| `pyproject.toml` | `psutil`, `nvidia-ml-py`, `rich` 의존성 추가 |

---

## 6. 관련 스크립트

| 파일 | 역할 |
|------|------|
| `utils/model-monitoring.py` | GPU/CPU/RAM + vLLM 메트릭 모니터링 |
| `utils/model-calling.py` | vLLM API 단일 추론 호출 |
| `utils/model-testing.py` | vLLM API 5종 자동 테스트 |
| `utils/model-validation.py` | LLM-as-a-Judge 평가 파이프라인 |
