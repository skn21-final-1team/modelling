"""
데이터 전처리 스크립트 - raw 크롤링 데이터를 LLM-as-Judge 테스트용 데이터로 변환

data/raw/raw_v2.csv → data/processed/processed_v3.csv

처리 과정:
1. 텍스트 정제 (사이드바/네비 잔여물, 특수문자 정리)
2. 섹션 기반 청킹 (## 마커 기준 분할, 긴 섹션만 추가 분할)
3. 컨텍스트 기반 Q&A + reference_answer 합성 (LLM-as-Judge 평가용)
"""

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "raw_v2.csv"
PROCESSED_DATA_PATH = BASE_DIR / "data" / "processed" / "processed_v3.csv"

MAX_CHUNK_SIZE = 800  # 섹션이 이보다 길면 추가 분할
MIN_CHUNK_SIZE = 80   # 이보다 짧은 청크는 제외

# 사이드바/네비게이션 패턴 (위키백과 목차, 링크 나열 등)
SIDEBAR_PATTERNS = [
    r"^(?:[가-힣A-Za-z\s]+\n){5,}",  # 줄바꿈으로 구분된 단어 나열 5개 이상
    r"Grok\s+딥페이크",
    r"Théâtre\s+D'opéra",
    r"AI\s+위험에\s+관한\s+성명",
    r"불쾌한\s+골짜기",
    r"인공지능\s+거품",
    r"딥페이크\s+포르노그래피",
    r"친절한\s+AI",
    r"실존적\s+위험",
]


def clean_text(text: str) -> str:
    """텍스트를 정제합니다."""
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\s+\n", "\n\n", text)
    return text.strip()


def remove_sidebar_content(text: str) -> str:
    """사이드바/네비게이션 잔여물을 제거합니다."""
    lines = text.split("\n")
    cleaned_lines = []
    skip_block = True  # 첫 번째 본문 문장 전까지는 네비 블록으로 간주

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not skip_block:
                cleaned_lines.append(line)
            continue

        # 본문 시작 감지: 마침표가 있는 문장이나 섹션 헤더
        if skip_block:
            if stripped.startswith("## ") or ("다." in stripped and len(stripped) > 30):
                skip_block = False
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    for pattern in SIDEBAR_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.MULTILINE)
    return result.strip()


def split_by_sections(text: str) -> list[dict]:
    """## 마커 기준으로 섹션 분할합니다."""
    sections = []
    current_title = "개요"
    current_lines = []

    for line in text.split("\n"):
        if line.strip().startswith("## "):
            # 이전 섹션 저장
            content = "\n".join(current_lines).strip()
            if content and len(content) >= MIN_CHUNK_SIZE:
                sections.append({"section": current_title, "content": content})
            current_title = line.strip().replace("## ", "").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # 마지막 섹션
    content = "\n".join(current_lines).strip()
    if content and len(content) >= MIN_CHUNK_SIZE:
        sections.append({"section": current_title, "content": content})

    return sections


def split_long_section(content: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """긴 섹션을 문장 경계 기준으로 추가 분할합니다."""
    if len(content) <= max_size:
        return [content]

    chunks = []
    sentences = re.split(r"(?<=다\.)\s+|(?<=요\.)\s+|(?<=있다\.)\s+|(?<=한다\.)\s+|(?<=된다\.)\s+", content)
    current = ""
    for sent in sentences:
        if len(current) + len(sent) > max_size and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = current + " " + sent if current else sent

    if current.strip() and len(current.strip()) >= MIN_CHUNK_SIZE:
        chunks.append(current.strip())

    return chunks if chunks else [content]


def extract_defined_terms(content: str) -> list[dict]:
    """괄호 표기로 정의된 전문 용어를 추출합니다.

    예: '강인공지능(strong AI)', '약인공지능(weak AI)', '인공 일반 지능(AGI)'
    """
    terms = []
    seen = set()

    # 패턴: 한글용어(영문 또는 약어)
    for m in re.finditer(r"([가-힣\s]{2,20})\(([A-Za-z\s,]+)\)", content):
        korean = m.group(1).strip()
        english = m.group(2).strip()
        key = korean
        if key not in seen and len(korean) >= 2:
            seen.add(key)
            # 해당 용어가 포함된 문장 찾기
            sent = _find_sentence_containing(content, m.start())
            if sent:
                terms.append({"korean": korean, "english": english, "sentence": sent})

    # 패턴: 영문용어(한글)
    for m in re.finditer(r"([A-Za-z\s]{2,30})\(([가-힣\s,]+)\)", content):
        english = m.group(1).strip()
        korean = m.group(2).strip()
        key = korean
        if key not in seen and len(korean) >= 2:
            seen.add(key)
            sent = _find_sentence_containing(content, m.start())
            if sent:
                terms.append({"korean": korean, "english": english, "sentence": sent})

    return terms


def _find_sentence_containing(text: str, pos: int) -> str:
    """텍스트에서 pos 위치를 포함하는 문장을 반환합니다."""
    # 문장 시작 찾기
    start = pos
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1

    # 문장 끝 찾기
    end = pos
    while end < len(text) and text[end] not in ".!?\n":
        end += 1
    if end < len(text):
        end += 1  # 마침표 포함

    sent = text[start:end].strip()
    return sent if len(sent) >= 20 else ""


def extract_temporal_facts(content: str) -> list[dict]:
    """연도 기반 사실을 추출합니다."""
    facts = []
    seen_years = set()

    for m in re.finditer(r"(\d{4})년[에도부터의]?\s*(.{10,150}?[다었됨음])[..]", content):
        year = m.group(1)
        if year in seen_years:
            continue
        seen_years.add(year)
        full_sent = _find_sentence_containing(content, m.start())
        if full_sent and len(full_sent) >= 20:
            facts.append({"year": year, "sentence": full_sent})

    return facts


def generate_qa_pairs(
    section: str, content: str, title: str, chunk_idx: int,
) -> list[dict]:
    """섹션/청크에서 LLM-as-Judge용 Q&A 쌍을 생성합니다."""
    qa_pairs = []
    short_title = title.split(" - ")[0] if " - " in title else title

    # 1) 요약 질문 (첫 번째 청크에만)
    if chunk_idx == 0:
        if section == "개요":
            question = f"{short_title}이란 무엇인가요?"
        else:
            question = f"{short_title}에서 '{section}'은(는) 무엇을 다루나요?"
        qa_pairs.append({
            "question": question,
            "reference_answer": content[:500].strip(),
            "question_type": "summarization",
        })

    # 2) 용어 정의 질문
    terms = extract_defined_terms(content)
    for term in terms[:3]:  # 섹션당 최대 3개
        qa_pairs.append({
            "question": f"{term['korean']}({term['english']})의 정의를 설명해주세요.",
            "reference_answer": term["sentence"],
            "question_type": "definition",
        })

    # 3) 연도 기반 질문
    temporal = extract_temporal_facts(content)
    for fact in temporal[:2]:  # 섹션당 최대 2개
        qa_pairs.append({
            "question": f"{fact['year']}년에 인공지능 분야에서 어떤 일이 있었나요?",
            "reference_answer": fact["sentence"],
            "question_type": "temporal",
        })

    # 4) Q&A가 없는 경우 → 내용 이해 질문
    if not qa_pairs:
        qa_pairs.append({
            "question": f"{short_title}의 '{section}'에서 다루는 핵심 내용은 무엇인가요?",
            "reference_answer": content[:500].strip(),
            "question_type": "comprehension",
        })

    return qa_pairs


def load_raw_data(path: Path = RAW_DATA_PATH) -> list[dict]:
    """raw CSV를 로드합니다."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def process_data(raw_data: list[dict]) -> list[dict]:
    """raw 데이터를 LLM-as-Judge 형식으로 변환합니다."""
    processed = []
    content_id = 1

    for row in raw_data:
        url = row["url"]
        title = row["title"]
        raw_text = row["raw_text"]

        cleaned = clean_text(raw_text)
        cleaned = remove_sidebar_content(cleaned)
        if not cleaned or len(cleaned) < 50:
            print(f"  [SKIP] 텍스트 부족: {title}")
            continue

        sections = split_by_sections(cleaned)
        print(f"  [{title[:40]}] {len(cleaned)}자 → {len(sections)}개 섹션")

        for sec_idx, sec in enumerate(sections):
            section_name = sec["section"]
            section_content = sec["content"]

            # 긴 섹션은 추가 분할
            chunks = split_long_section(section_content)

            for chunk_idx, chunk in enumerate(chunks):
                all_qas = generate_qa_pairs(
                    section_name, chunk, title, chunk_idx,
                )

                for qa in all_qas:
                    processed.append({
                        "content_id": content_id,
                        "source_url": url,
                        "title": title,
                        "section": section_name,
                        "context": chunk,
                        "chunk_index": f"{sec_idx}-{chunk_idx}",
                        "question": qa["question"],
                        "reference_answer": qa["reference_answer"],
                        "question_type": qa["question_type"],
                    })
                    content_id += 1

    return processed


def save_processed_csv(data: list[dict], path: Path = PROCESSED_DATA_PATH):
    """processed 데이터를 CSV로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "content_id", "source_url", "title", "section", "context",
        "chunk_index", "question", "reference_answer", "question_type",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"\n저장 완료: {path} ({len(data)}건)")


def print_stats(data: list[dict]):
    """통계를 출력합니다."""
    type_counts: dict[str, int] = {}
    for row in data:
        t = row["question_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\n--- 질문 유형별 통계 ---")
    for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t}: {count}건")


def main():
    print("=" * 60)
    print("데이터 전처리 시작 - LLM-as-Judge 테스트 데이터 생성")
    print("=" * 60)

    if not RAW_DATA_PATH.exists():
        print(f"[ERROR] raw 데이터가 없습니다: {RAW_DATA_PATH}")
        print("먼저 crawling.py를 실행해주세요.")
        return

    raw_data = load_raw_data()
    print(f"raw 데이터 로드: {len(raw_data)}건\n")

    processed = process_data(raw_data)
    if processed:
        save_processed_csv(processed)
        print_stats(processed)
    else:
        print("처리된 데이터가 없습니다.")

    print(f"\n총 {len(processed)}개 Q&A 쌍 생성 완료")


if __name__ == "__main__":
    main()
