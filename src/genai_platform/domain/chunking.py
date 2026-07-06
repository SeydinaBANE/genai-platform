from genai_platform.domain.models import Chunk, Document


class ChunkingStrategy:
    def __init__(self, max_chunk_size: int = 512, overlap: float = 0.1) -> None:
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_document(self, document: Document) -> list[Chunk]:
        text = document.text
        chunks: list[Chunk] = []
        paragraphs = self._split_by_paragraphs(text)

        for para in paragraphs:
            if len(para) > self.max_chunk_size:
                sentences = self._split_by_sentences(para)
                chunks.extend(self._group_sentences(sentences))
            else:
                chunks.append(
                    Chunk(
                        text=para,
                        metadata={**document.metadata, "section": self._detect_section(para)},
                    )
                )

        chunks = self._add_overlap(chunks)
        return chunks

    def _split_by_paragraphs(self, text: str) -> list[str]:
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    def _split_by_sentences(self, text: str) -> list[str]:
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences(self, sentences: list[str]) -> list[Chunk]:
        chunks: list[Chunk] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > self.max_chunk_size:
                if current:
                    chunks.append(Chunk(text=current.strip()))
                current = sentence
            else:
                current += " " + sentence
        if current:
            chunks.append(Chunk(text=current.strip()))
        return chunks

    def _add_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        if len(chunks) <= 1:
            return chunks
        overlap_size = int(self.max_chunk_size * self.overlap)
        result: list[Chunk] = []
        for i, chunk in enumerate(chunks):
            if i > 0 and overlap_size > 0:
                prev_end = chunks[i - 1].text[-overlap_size:]
                chunk = Chunk(
                    text=prev_end + " " + chunk.text,
                    metadata=chunk.metadata,
                )
            result.append(chunk)
        return result

    def _detect_section(self, text: str) -> str:
        import re

        match = re.match(r"^(#{1,3}|[A-Z][^.]{0,50})", text.strip())
        return match.group(1) if match else ""
