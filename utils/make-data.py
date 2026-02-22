"""
데이터 전처리 스크립트 - raw 크롤링 데이터를 LLM 테스트용 데이터로 변환

data/raw/raw.csv → data/processed/processed.csv

처리 과정:
1. 텍스트 정제 (HTML 잔여물, 특수문자 정리)
2. 텍스트 청킹 (500자 단위, 50자 overlap)
3. Q&A 쌍 합성 (각 청크에서 질문/기대키워드 생성)
"""

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "raw.csv"
PROCESSED_DATA_PATH = BASE_DIR / "data" / "processed" / "processed.csv"

CHUNK_SIZE = 500  # 청크 크기 (자)
CHUNK_OVERLAP = 50  # 청크 간 오버랩 (자)


def clean_text(text: str) -> str:
    """텍스트를 정제합니다."""
    # HTML 엔티티 및 잔여물 제거
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    # 제어 문자 제거 (줄바꿈, 탭 제외)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # 연속 공백 정리
    text = re.sub(r"[ \t]+", " ", text)
    # 연속 줄바꿈 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 빈 줄만 있는 섹션 제거
    text = re.sub(r"\n\s+\n", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 청크로 분할합니다. 문장 경계를 최대한 존중합니다."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # 문장 경계(마침표, 줄바꿈) 찾기
            search_text = text[max(end - 80, start):end]
            # 마지막 문장 끝 찾기
            last_break = -1
            for sep in ["\n\n", "\n", ". ", "다. ", "요. "]:
                idx = search_text.rfind(sep)
                if idx != -1:
                    last_break = max(end - 80, start) + idx + len(sep)
                    break

            if last_break > start:
                end = last_break

        chunk = text[start:end].strip()
        if chunk and len(chunk) > 30:
            chunks.append(chunk)

        start = end - overlap
        if start >= len(text):
            break

    return chunks


def extract_section_title(chunk: str) -> str:
    """청크에서 섹션 제목을 추출합니다."""
    match = re.search(r"##\s*(.+)", chunk)
    if match:
        return match.group(1).strip()
    # 첫 줄을 제목으로 사용
    first_line = chunk.split("\n")[0].strip()
    if len(first_line) < 80:
        return first_line
    return first_line[:77] + "..."


def extract_keywords(chunk: str) -> list[str]:
    """청크에서 주요 키워드를 추출합니다."""
    # 괄호 안의 영문/한글 용어 추출
    terms = re.findall(r"[가-힣]{2,}(?:\s[가-힣]{2,})*", chunk)
    # 빈도 기반 키워드 추출
    word_count: dict[str, int] = {}
    for term in terms:
        if len(term) >= 3 and term not in ("하는", "있는", "하고", "되는", "에서", "으로", "이다", "한다"):
            word_count[term] = word_count.get(term, 0) + 1

    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:5]]


def generate_qa(chunk: str, title: str) -> tuple[str, str]:
    """청크 내용 기반으로 질문과 기대 키워드를 합성합니다."""
    keywords = extract_keywords(chunk)
    if not keywords:
        return f"{title}에 대해 설명해주세요.", title

    primary_keyword = keywords[0]

    # 질문 패턴 다양화
    patterns = [
        f"{primary_keyword}에 대해 설명해주세요.",
        f"{primary_keyword}이란 무엇인가요?",
        f"{primary_keyword}의 주요 특징은 무엇인가요?",
        f"{title}에서 {primary_keyword}은 어떤 역할을 하나요?",
    ]

    # 청크 해시 기반으로 패턴 선택 (결정적이면서 다양하게)
    pattern_idx = hash(chunk[:50]) % len(patterns)
    question = patterns[pattern_idx]
    expected = ",".join(keywords)

    return question, expected


def load_raw_data(path: Path = RAW_DATA_PATH) -> list[dict]:
    """raw CSV를 로드합니다."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def process_data(raw_data: list[dict]) -> list[dict]:
    """raw 데이터를 전처리하여 processed 데이터를 생성합니다."""
    processed = []
    content_id = 1

    for row in raw_data:
        url = row["url"]
        title = row["title"]
        raw_text = row["raw_text"]

        # 텍스트 정제
        cleaned = clean_text(raw_text)
        if not cleaned or len(cleaned) < 50:
            print(f"  [SKIP] 텍스트 부족: {title}")
            continue

        # 청킹
        chunks = chunk_text(cleaned)
        print(f"  [{title[:40]}] {len(cleaned)}자 → {len(chunks)}개 청크")

        for chunk_idx, chunk in enumerate(chunks):
            question, expected_keywords = generate_qa(chunk, title)

            processed.append({
                "content_id": content_id,
                "source_url": url,
                "title": title,
                "text": chunk,
                "chunk_index": chunk_idx,
                "question": question,
                "expected_keywords": expected_keywords,
            })
            content_id += 1

    return processed


def save_processed_csv(data: list[dict], path: Path = PROCESSED_DATA_PATH):
    """processed 데이터를 CSV로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "content_id", "source_url", "title", "text",
        "chunk_index", "question", "expected_keywords",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"\n저장 완료: {path} ({len(data)}건)")


def main():
    print("=" * 60)
    print("데이터 전처리 시작 - raw → processed")
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
    else:
        print("처리된 데이터가 없습니다.")

    print(f"\n총 {len(processed)}개 청크 생성 완료")


if __name__ == "__main__":
    main()
