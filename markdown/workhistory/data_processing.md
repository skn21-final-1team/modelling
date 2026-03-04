# 데이터 처리 작업 이력 (v1 → v2 → v3)

OpenLLM 성능 테스트를 위한 합성 데이터 생성 과정 기록.
NotebookLM 웹소스 추가 시뮬레이션 — URL 크롤링 → 전처리 → LLM-as-Judge 평가용 데이터.

---

## 1. 크롤링 (Crawling)

> 관련 파일: `utils/crawling.py`
> 소스: 한국어 위키백과 AI/ML 관련 문서 15개 (인공지능, 기계학습, 딥러닝 등)

### v1 — 초기 크롤링

- `requests` + `BeautifulSoup4` 사용 (selenium 미사용)
- 위키백과 `mw-content-text` div에서 `<p>`, `<h2>`, `<h3>`, `<h4>`, `<li>` 태그 추출
- 기본 필터링: `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` 제거
- 위키 편집 링크(`mw-editsection`), 각주 번호(`[1]`), `[편집]` 텍스트 제거

**문제점:**

- `rel="mw:WikiLink"` + `class="new"` (빨간 링크) 텍스트가 본문에 혼입
- `class="reflist"` (각주/참조 목록) 전체가 본문으로 포함
- 사이드바/네비게이션 링크 나열이 본문 앞에 포함됨

**결과:** `raw_v1.csv` — 14건, 298KB

### v2 — 크롤링 예외 케이스 추가

v1의 노이즈를 제거하기 위해 `extract_text_from_html` 함수에 2개 예외 케이스 추가:

```python
# 빨간 링크 (존재하지 않는 문서 링크) 제거
for unwanted in content_div.find_all(
    "a", attrs={"rel": "mw:WikiLink", "class": "new"},
):
    unwanted.decompose()

# 각주/참조 목록 제거
for unwanted in content_div.find_all("div", class_="reflist"):
    unwanted.decompose()
```

**결과:** `raw_v2.csv` — 14건, 206KB (raw 크기 31% 감소)

### v3 — 크롤링 변경 없음

v3에서 크롤링 단계는 v2와 동일. 변경은 전처리(`make-data.py`) 단계에서만 발생.

---

## 2. 청킹 (Chunking)

> 관련 파일: `utils/make-data.py`

### v1 — 고정 크기 분할

- **방식:** 500자 단위, 50자 overlap
- 문장 경계를 탐색하되, 기본적으로 문자 수 기반 분할
- 사이드바/네비게이션 텍스트가 chunk_index 0에 그대로 포함

**문제점:**

- 첫 번째 청크에 사이드바 링크 나열("인공 일반 지능\n지능형 에이전트\n재귀적 자기 개선...")이 혼입
- 문장 중간에서 잘림 ("르면 이러한 초연산은 가능하지 않지만, 특별한시공간에서는...")
- 섹션 경계 무시 — 다른 주제의 내용이 하나의 청크에 혼합

**결과:** `processed_v1.csv` — 404건, 502KB

### v2 — 동일 방식 (크롤링 노이즈만 감소)

청킹 로직은 v1과 동일하지만, raw 데이터가 정제되어 결과적으로 청크 품질 향상.

**결과:** `processed_v2.csv` — 223건, 341KB (45% 감소)

### v3 — 섹션 기반 분할

**전면 재설계:**

1. **사이드바 제거** (`remove_sidebar_content`): 본문 첫 문장 이전의 네비 블록 제거
2. **`##` 마커 기준 섹션 분할** (`split_by_sections`): 위키 섹션 헤더 단위로 1차 분할
3. **긴 섹션 추가 분할** (`split_long_section`): 800자 초과 섹션만 문장 경계 기준 2차 분할
4. **최소 크기 필터**: 80자 미만 청크 제외

**결과:** `processed_v3.csv` — 368건, 717KB (context 포함으로 파일 크기 증가)

| 항목 | v1 | v2 | v3 |
|------|-----|-----|-----|
| 청킹 방식 | 500자 고정 | 500자 고정 | 섹션 기반 |
| 청크 수 | 404 | 223 | 368 (Q&A 기준) |
| 사이드바 처리 | 미처리 | 미처리 | 제거 |
| 섹션 정보 | 없음 | 없음 | `section` 컬럼 추가 |

---

## 3. LLM-as-Judge 평가 관점

### v1/v2 — 평가 불가능

**스키마:** `content_id, source_url, title, text, chunk_index, question, expected_keywords`

**question 생성 방식:** 정규식으로 한국어 `은/는` 패턴 매칭 → 주어 추출 → 템플릿 질문 생성

**문제점 (평가 불가능한 이유):**

- 질문이 의미 없음: `"그러나의 정의는 무엇인가요?"`, `"르면 이러한 초연산은 가능하지 않지만의 주요 특징은?"` — 접속사, 문장 조각이 주어로 추출됨
- expected_keywords가 문장 전체: `"인간의 지능을 모방한 기능을 갖춘컴퓨터 시스템이며"` — 키워드가 아닌 문장 조각
- reference_answer 없음 — Judge LLM이 정답과 비교할 기준 부재
- 질문 유형 분류 없음 — 어떤 능력을 테스트하는지 불명확

### v3 — LLM-as-Judge 평가 가능

**스키마:** `content_id, source_url, title, section, context, chunk_index, question, reference_answer, question_type`

**핵심 변경:**

1. **`reference_answer` 추가** — Judge LLM이 생성된 답변과 비교할 정답 기준
2. **`question_type` 분류** — 어떤 능력을 평가하는지 명시
3. **`context` 컬럼** — RAG 파이프라인 시뮬레이션용 (검색된 문서 역할)
4. **`section` 컬럼** — 출처 추적 가능

**질문 생성 방식 (v3):**

| 유형 | 건수 | 생성 방식 | 예시 |
|------|------|-----------|------|
| `summarization` | 97 | 섹션 제목 기반 | "인공지능에서 '강인공지능과 약인공지능'은 무엇을 다루나요?" |
| `definition` | 162 | 괄호 용어 `A(B)` 패턴 | "강인공지능(strong AI)의 정의를 설명해주세요." |
| `temporal` | 100 | `YYYY년` 패턴 + 문장 추출 | "1948년에 인공지능 분야에서 어떤 일이 있었나요?" |
| `comprehension` | 9 | 폴백 (위 패턴 미매칭 시) | "인공지능의 '인공지능 기술의 실용적인 응용'에서 다루는 핵심 내용은?" |

**LLM-as-Judge 평가 흐름:**

```
context (검색된 문서) + question (질문)
         ↓
    LLM이 answer 생성
         ↓
Judge LLM이 (answer, reference_answer) 비교 → 점수 부여
```

---

## 4. 파일 구조

```
data/
├── raw/
│   ├── raw_v1.csv          # 초기 크롤링 (298KB, 14건)
│   └── raw_v2.csv          # mw:WikiLink + reflist 제거 (206KB, 14건)
└── processed/
    ├── processed_v1.csv    # 500자 고정 청킹 + 정규식 QA (502KB, 404건)
    ├── processed_v2.csv    # 동일 로직, 정제된 raw (341KB, 223건)
    └── processed_v3.csv    # 섹션 기반 + LLM-as-Judge 형식 (717KB, 368건)
```

---

## 5. 관련 스크립트

| 파일 | 역할 |
|------|------|
| `utils/crawling.py` | URL 크롤링 → `data/raw/raw_v2.csv` |
| `utils/make-data.py` | raw 전처리 → `data/processed/processed_v3.csv` |
