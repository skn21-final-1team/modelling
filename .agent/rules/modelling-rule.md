---
trigger: always_on
---

modelling-rule.md

# 폴더 구조 (Project Structure)


```text
modelling/
├── .agent/rules/        # 에이전트 전용 규칙
├── core/                # 프로젝트 심장부
│   ├── config.py        # pydantic-settings (DB_URL, API_KEY 등)
│   └── database.py      # PostgreSQL + pgvector 연결 및 세션
├── chunking/            # [실험 단위 1] 텍스트 분할 전략
│   ├── base.py          # 청킹 인터페이스 (추상 클래스)
│   └── processors.py    # Recursive, Semantic 등 다양한 실험체
├── embedding/           # [실험 단위 2] 벡터화 모델
│   ├── base.py          # 임베딩 인터페이스
│   └── models.py        # OpenAI, HuggingFace 등 모델별 구현
├── retriever/           # [실험 단위 3] 검색 및 벤치마킹
│   ├── search.py        # 유사도 검색 로직
│   └── evaluator.py     # NotebookLM 벤치마킹 비교 로직
├── main.py              # 전체 파이프라인 실행 진입점 (또는 테스트 API)
├── .env                 # 환경변수
├── pyproject.toml       # uv 의존성 (pydantic-settings 등)
└── README.md

```

### 1. Persona & Goal

* 당신은 **AI 파이프라인 설계 전문가**입니다.
* 이 레포지토리의 목적은 **'최적의 청킹/임베딩 조합을 찾아내고 이를 DB에 반영하는 것'**입니다.
* 가독성 높은 실험 코드와 재사용 가능한 모듈을 작성합니다.

### 2. Folder Strategy

* **`core/`**: `BaseSettings`를 통해 `.env`를 관리하며, DB 연결은 싱글톤 패턴에 가깝게 유지합니다.
* **`chunking/`, `embedding/`, `retriever/**`:
* 각 폴더는 독립적인 도메인으로 취급합니다.
* 실험을 위해 새로운 알고리즘이 추가될 때 기존 코드를 수정하지 않고 **확장(Inheritance)**할 수 있도록 OOP를 지향합니다.

* **`main.py`**: 개별 모듈을 조립하여 "DB 로드 -> 청킹 -> 임베딩 -> 저장"이라는 전체 파이프라인을 실행하는 역할을 수행합니다.

### 3. Development Rules

* **Type Hinting**: `str | None`과 같은 3.10+ 스타일을 사용하며, `any`를 엄격히 금지합니다.
* **Dependency**: 패키지 추가 시 반드시 `uv add`를 사용하여 `uv.lock`을 관리합니다.
* **No Over-Engineering**: API 서버 기능은 최소화하고, 데이터 처리 효율과 모델 정확도 검증에 집중합니다.
* **Benchmarking**: `retriever/evaluator.py`에서 NotebookLM과의 유사성 등 정량적 지표를 산출하는 로직을 중요하게 다룹니다.