"""
웹 크롤링 스크립트 - NotebookLM 웹소스 추가 시뮬레이션

URL 리스트에서 텍스트 콘텐츠를 추출하여 data/raw/raw.csv에 저장합니다.
requests + BeautifulSoup4만 사용합니다 (selenium 미사용).
"""

import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "raw.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

REQUEST_DELAY = 2  # 요청 간 대기 시간 (초)
REQUEST_TIMEOUT = 15  # 요청 타임아웃 (초)

# 크롤링 대상 URL 목록 - 한국어 위키백과 기술 문서
TARGET_URLS = [
    "https://ko.wikipedia.org/wiki/%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5",
    "https://ko.wikipedia.org/wiki/%EA%B8%B0%EA%B3%84_%ED%95%99%EC%8A%B5",
    "https://ko.wikipedia.org/wiki/%EC%9E%90%EC%97%B0%EC%96%B4_%EC%B2%98%EB%A6%AC",
    "https://ko.wikipedia.org/wiki/%EB%94%A5_%EB%9F%AC%EB%8B%9D",
    "https://ko.wikipedia.org/wiki/%ED%8A%B8%EB%9E%9C%EC%8A%A4%ED%8F%AC%EB%A8%B8_(%EA%B8%B0%EA%B3%84_%ED%95%99%EC%8A%B5_%EB%AA%A8%EB%8D%B8)",
    "https://ko.wikipedia.org/wiki/%EB%8C%80%ED%98%95_%EC%96%B8%EC%96%B4_%EB%AA%A8%EB%8D%B8",
    "https://ko.wikipedia.org/wiki/%EC%BB%B4%ED%93%A8%ED%84%B0_%EB%B9%84%EC%A0%84",
    "https://ko.wikipedia.org/wiki/%EA%B0%95%ED%99%94_%ED%95%99%EC%8A%B5",
    "https://ko.wikipedia.org/wiki/%EC%8B%A0%EA%B2%BD%EB%A7%9D",
    "https://ko.wikipedia.org/wiki/%ED%95%A9%EC%84%B1%EA%B3%B1_%EC%8B%A0%EA%B2%BD%EB%A7%9D",
    "https://ko.wikipedia.org/wiki/%EC%88%9C%ED%99%98_%EC%8B%A0%EA%B2%BD%EB%A7%9D",
    "https://ko.wikipedia.org/wiki/%EC%83%9D%EC%84%B1%EC%A0%81_%EC%A0%81%EB%8C%80_%EC%8B%A0%EA%B2%BD%EB%A7%9D",
    "https://ko.wikipedia.org/wiki/%EC%96%B4%ED%85%90%EC%85%98_(%EA%B8%B0%EA%B3%84_%ED%95%99%EC%8A%B5)",
    "https://ko.wikipedia.org/wiki/%EB%B2%A1%ED%84%B0_%EB%8D%B0%EC%9D%B4%ED%84%B0%EB%B2%A0%EC%9D%B4%EC%8A%A4",
    "https://ko.wikipedia.org/wiki/%EC%9E%84%EB%B2%A0%EB%94%A9",
]


def extract_text_from_html(html: str, url: str) -> tuple[str, str]:
    """HTML에서 제목과 본문 텍스트를 추출합니다."""
    soup = BeautifulSoup(html, "html.parser")

    # 불필요한 태그 제거
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # 제목 추출
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    # 위키백과 특화 처리
    domain = urlparse(url).netloc
    if "wikipedia.org" in domain:
        content_div = soup.find("div", {"id": "mw-content-text"})
        if content_div:
            # 참조, 편집 링크, 목차 등 제거
            for unwanted in content_div.find_all(
                ["sup", "span"],
                class_=["reference", "mw-editsection"],
            ):
                unwanted.decompose()
            for unwanted in content_div.find_all("div", {"id": "toc"}):
                unwanted.decompose()
            for unwanted in content_div.find_all("table", class_="ambox"):
                unwanted.decompose()

            paragraphs = content_div.find_all(["p", "h2", "h3", "h4", "li"])
            text_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 5:
                    # h2, h3 태그는 섹션 구분으로 표시
                    if p.name in ("h2", "h3", "h4"):
                        text = f"\n## {text}\n"
                    text_parts.append(text)
            raw_text = "\n".join(text_parts)
        else:
            raw_text = soup.get_text(separator="\n", strip=True)
    else:
        # 일반 웹페이지: <article> 또는 <main> 우선, 없으면 <body>
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("body")
            or soup
        )
        paragraphs = main_content.find_all(["p", "h1", "h2", "h3", "h4", "li"])
        text_parts = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 5:
                if p.name in ("h1", "h2", "h3", "h4"):
                    text = f"\n## {text}\n"
                text_parts.append(text)
        raw_text = "\n".join(text_parts)

    # 텍스트 후처리
    raw_text = re.sub(r"\[편집\]", "", raw_text)
    raw_text = re.sub(r"\[\d+\]", "", raw_text)  # 각주 번호 제거
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)  # 과도한 줄바꿈 정리
    raw_text = raw_text.strip()

    return title, raw_text


def crawl_url(url: str) -> dict | None:
    """단일 URL을 크롤링하여 딕셔너리로 반환합니다."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        title, raw_text = extract_text_from_html(response.text, url)

        if not raw_text or len(raw_text) < 100:
            print(f"  [SKIP] 텍스트 부족: {url} ({len(raw_text)}자)")
            return None

        return {
            "url": url,
            "title": title,
            "raw_text": raw_text,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}")
        return None


def crawl_urls(urls: list[str]) -> list[dict]:
    """URL 리스트를 크롤링합니다."""
    results = []
    for i, url in enumerate(urls):
        print(f"[{i + 1}/{len(urls)}] 크롤링 중: {url}")
        result = crawl_url(url)
        if result:
            print(f"  [OK] {result['title'][:50]}... ({len(result['raw_text'])}자)")
            results.append(result)
        if i < len(urls) - 1:
            time.sleep(REQUEST_DELAY)
    return results


def save_raw_csv(data: list[dict], output_path: Path = RAW_DATA_PATH):
    """크롤링 결과를 CSV로 저장합니다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "raw_text", "crawled_at"])
        writer.writeheader()
        writer.writerows(data)
    print(f"\n저장 완료: {output_path} ({len(data)}건)")


def main():
    print("=" * 60)
    print("웹 크롤링 시작 - OpenLLM 테스트 데이터 생성")
    print(f"대상 URL: {len(TARGET_URLS)}개")
    print("=" * 60)

    results = crawl_urls(TARGET_URLS)
    if results:
        save_raw_csv(results)
    else:
        print("크롤링된 데이터가 없습니다.")

    print(f"\n총 {len(results)}/{len(TARGET_URLS)}개 크롤링 완료")


if __name__ == "__main__":
    main()
