import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


class CrawlerService:

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        delay: float = 2.0,
        timeout: float = 15.0,
    ) -> None:
        self._headers = headers or DEFAULT_HEADERS
        self._delay = delay
        self._timeout = timeout

    def extract_text_from_html(self, html: str, url: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        domain = urlparse(url).netloc
        if "wikipedia.org" in domain:
            raw_text = self._extract_wikipedia(soup)
        else:
            raw_text = self._extract_generic(soup)

        raw_text = re.sub(r"\[편집\]", "", raw_text)
        raw_text = re.sub(r"\[\d+\]", "", raw_text)
        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
        raw_text = raw_text.strip()

        return title, raw_text

    def _extract_wikipedia(self, soup: BeautifulSoup) -> str:
        content_div = soup.find("div", {"id": "mw-content-text"})
        if not content_div:
            return soup.get_text(separator="\n", strip=True)

        for unwanted in content_div.find_all(
            ["sup", "span"], class_=["reference", "mw-editsection"]
        ):
            unwanted.decompose()
        for unwanted in content_div.find_all("div", {"id": "toc"}):
            unwanted.decompose()
        for unwanted in content_div.find_all("table", class_="ambox"):
            unwanted.decompose()
        for unwanted in content_div.find_all(
            "a", attrs={"rel": "mw:WikiLink", "class": "new"}
        ):
            unwanted.decompose()
        for unwanted in content_div.find_all("div", class_="reflist"):
            unwanted.decompose()

        return self._paragraphs_to_text(
            content_div.find_all(["p", "h2", "h3", "h4", "li"])
        )

    def _extract_generic(self, soup: BeautifulSoup) -> str:
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("body")
            or soup
        )
        return self._paragraphs_to_text(
            main_content.find_all(["p", "h1", "h2", "h3", "h4", "li"])
        )

    def _paragraphs_to_text(self, paragraphs: list) -> str:
        text_parts: list[str] = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 5:
                if p.name in ("h1", "h2", "h3", "h4"):
                    text = f"\n## {text}\n"
                text_parts.append(text)
        return "\n".join(text_parts)

    async def crawl_url(self, url: str) -> dict | None:
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            title, raw_text = self.extract_text_from_html(response.text, url)

            if not raw_text or len(raw_text) < 100:
                return None

            return {
                "url": url,
                "title": title,
                "raw_text": raw_text,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
        except httpx.HTTPError:
            return None

    async def crawl_urls(self, urls: list[str]) -> list[dict]:
        results: list[dict] = []
        for i, url in enumerate(urls):
            result = await self.crawl_url(url)
            if result:
                results.append(result)
            if i < len(urls) - 1:
                await asyncio.sleep(self._delay)
        return results

    def save_raw_csv(self, data: list[dict], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["url", "title", "raw_text", "crawled_at"]
            )
            writer.writeheader()
            writer.writerows(data)
        return output_path
