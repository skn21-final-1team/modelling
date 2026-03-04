import csv
import re
from pathlib import Path

MAX_CHUNK_SIZE = 800
MIN_CHUNK_SIZE = 80


class DataProcessorService:

    SIDEBAR_PATTERNS = [
        r"^(?:[가-힣A-Za-z\s]+\n){5,}",
        r"Grok\s+딥페이크",
        r"Théâtre\s+D'opéra",
        r"AI\s+위험에\s+관한\s+성명",
        r"불쾌한\s+골짜기",
        r"인공지능\s+거품",
        r"딥페이크\s+포르노그래피",
        r"친절한\s+AI",
        r"실존적\s+위험",
    ]

    def __init__(
        self,
        max_chunk_size: int = MAX_CHUNK_SIZE,
        min_chunk_size: int = MIN_CHUNK_SIZE,
    ) -> None:
        self._max_chunk_size = max_chunk_size
        self._min_chunk_size = min_chunk_size

    def clean_text(self, text: str) -> str:
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        text = re.sub(r"&#\d+;", " ", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"\n\s+\n", "\n\n", text)
        return text.strip()

    def remove_sidebar_content(self, text: str) -> str:
        lines = text.split("\n")
        cleaned_lines: list[str] = []
        skip_block = True

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not skip_block:
                    cleaned_lines.append(line)
                continue

            if skip_block:
                if stripped.startswith("## ") or ("다." in stripped and len(stripped) > 30):
                    skip_block = False
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)

        result = "\n".join(cleaned_lines)
        for pattern in self.SIDEBAR_PATTERNS:
            result = re.sub(pattern, "", result, flags=re.MULTILINE)
        return result.strip()

    def split_by_sections(self, text: str) -> list[dict]:
        sections: list[dict] = []
        current_title = "개요"
        current_lines: list[str] = []

        for line in text.split("\n"):
            if line.strip().startswith("## "):
                content = "\n".join(current_lines).strip()
                if content and len(content) >= self._min_chunk_size:
                    sections.append({"section": current_title, "content": content})
                current_title = line.strip().replace("## ", "").strip()
                current_lines = []
            else:
                current_lines.append(line)

        content = "\n".join(current_lines).strip()
        if content and len(content) >= self._min_chunk_size:
            sections.append({"section": current_title, "content": content})

        return sections

    def split_long_section(
        self, content: str, max_size: int | None = None
    ) -> list[str]:
        max_size = max_size or self._max_chunk_size
        if len(content) <= max_size:
            return [content]

        chunks: list[str] = []
        sentences = re.split(
            r"(?<=다\.)\s+|(?<=요\.)\s+|(?<=있다\.)\s+|(?<=한다\.)\s+|(?<=된다\.)\s+",
            content,
        )
        current = ""
        for sent in sentences:
            if len(current) + len(sent) > max_size and current:
                chunks.append(current.strip())
                current = sent
            else:
                current = current + " " + sent if current else sent

        if current.strip() and len(current.strip()) >= self._min_chunk_size:
            chunks.append(current.strip())

        return chunks if chunks else [content]

    def extract_defined_terms(self, content: str) -> list[dict]:
        terms: list[dict] = []
        seen: set[str] = set()

        for m in re.finditer(r"([가-힣\s]{2,20})\(([A-Za-z\s,]+)\)", content):
            korean = m.group(1).strip()
            english = m.group(2).strip()
            if korean not in seen and len(korean) >= 2:
                seen.add(korean)
                sent = self._find_sentence_containing(content, m.start())
                if sent:
                    terms.append({"korean": korean, "english": english, "sentence": sent})

        for m in re.finditer(r"([A-Za-z\s]{2,30})\(([가-힣\s,]+)\)", content):
            english = m.group(1).strip()
            korean = m.group(2).strip()
            if korean not in seen and len(korean) >= 2:
                seen.add(korean)
                sent = self._find_sentence_containing(content, m.start())
                if sent:
                    terms.append({"korean": korean, "english": english, "sentence": sent})

        return terms

    def _find_sentence_containing(self, text: str, pos: int) -> str:
        start = pos
        while start > 0 and text[start - 1] not in ".!?\n":
            start -= 1

        end = pos
        while end < len(text) and text[end] not in ".!?\n":
            end += 1
        if end < len(text):
            end += 1

        sent = text[start:end].strip()
        return sent if len(sent) >= 20 else ""

    def extract_temporal_facts(self, content: str) -> list[dict]:
        facts: list[dict] = []
        seen_years: set[str] = set()

        for m in re.finditer(r"(\d{4})년[에도부터의]?\s*(.{10,150}?[다었됨음])[..]", content):
            year = m.group(1)
            if year in seen_years:
                continue
            seen_years.add(year)
            full_sent = self._find_sentence_containing(content, m.start())
            if full_sent and len(full_sent) >= 20:
                facts.append({"year": year, "sentence": full_sent})

        return facts

    def generate_qa_pairs(
        self, section: str, content: str, title: str, chunk_idx: int
    ) -> list[dict]:
        qa_pairs: list[dict] = []
        short_title = title.split(" - ")[0] if " - " in title else title

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

        terms = self.extract_defined_terms(content)
        for term in terms[:3]:
            qa_pairs.append({
                "question": f"{term['korean']}({term['english']})의 정의를 설명해주세요.",
                "reference_answer": term["sentence"],
                "question_type": "definition",
            })

        temporal = self.extract_temporal_facts(content)
        for fact in temporal[:2]:
            qa_pairs.append({
                "question": f"{fact['year']}년에 인공지능 분야에서 어떤 일이 있었나요?",
                "reference_answer": fact["sentence"],
                "question_type": "temporal",
            })

        if not qa_pairs:
            qa_pairs.append({
                "question": f"{short_title}의 '{section}'에서 다루는 핵심 내용은 무엇인가요?",
                "reference_answer": content[:500].strip(),
                "question_type": "comprehension",
            })

        return qa_pairs

    def process_data(self, raw_data: list[dict]) -> list[dict]:
        processed: list[dict] = []
        content_id = 1

        for row in raw_data:
            url = row["url"]
            title = row["title"]
            raw_text = row["raw_text"]

            cleaned = self.clean_text(raw_text)
            cleaned = self.remove_sidebar_content(cleaned)
            if not cleaned or len(cleaned) < 50:
                continue

            sections = self.split_by_sections(cleaned)

            for sec_idx, sec in enumerate(sections):
                section_name = sec["section"]
                section_content = sec["content"]
                chunks = self.split_long_section(section_content)

                for chunk_idx, chunk in enumerate(chunks):
                    all_qas = self.generate_qa_pairs(
                        section_name, chunk, title, chunk_idx
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

    def load_raw_data(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def save_processed_csv(self, data: list[dict], path: Path) -> Path:
        fieldnames = [
            "content_id", "source_url", "title", "section", "context",
            "chunk_index", "question", "reference_answer", "question_type",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return path
