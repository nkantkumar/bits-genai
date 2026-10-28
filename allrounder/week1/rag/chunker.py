"""
rag/chunker.py - Boundary-aware semantic chunking for enterprise documents.

Design Patterns Used:
- Pipeline Pattern: First stage in RAG ingestion pipeline.
- Boundary-Aware Chunking: Segments text into semantic propositions and sentences,
  respects headings/sections, and preserves sliding overlap.
"""

import re
from typing import List, Tuple
try:
    from ..storage import Chunk
except (ImportError, ValueError):
    from storage import Chunk

DOC_TITLES = {
    "1792861009005.pdf": "Windows Privilege Escalation: SeTakeOwnershipPrivilege",
    "1792907264681.pdf": "AWS: Penetration Testing Lab Setup",
    "1792907573179.pdf": "PostgreSQL Penetration Testing",
    "1793025397798.pdf": "Comprehensive Guide on Wordlists (Kali, Dirb, Rockyou, SecLists)",
}


class SemanticChunker:
    """Boundary-aware semantic chunking engine."""

    def __init__(self, target_words: int = 350, overlap_sentences: int = 2):
        self.target_words = target_words
        self.overlap_sentences = overlap_sentences
        self.sentence_end_regex = re.compile(r"(?<=[.!?])\s+|\n\n+")
        self.header_regex = re.compile(
            r"^(abstract|table of contents|chapter|\d+\.\d+|\b[A-Z\s]{4,}\b)",
            re.MULTILINE,
        )

    def chunk_document(
        self,
        pages_text: List[Tuple[int, str]],
        doc_name: str,
    ) -> List[Chunk]:
        """
        Segments document pages into semantic chunks:
        - Segments text into propositions/sentences.
        - Respects natural headings and section boundaries.
        - Carries over sliding sentence overlap for semantic continuity.
        """
        title = DOC_TITLES.get(doc_name, doc_name.replace(".pdf", ""))
        chunks: List[Chunk] = []
        all_sentences: List[Tuple[int, str]] = []

        for page_num, p_text in pages_text:
            cleaned = p_text.strip()
            if not cleaned:
                continue
            raw_sents = self.sentence_end_regex.split(cleaned)
            for s in raw_sents:
                s_strip = s.strip()
                if len(s_strip) > 10:
                    all_sentences.append((page_num, s_strip))

        if not all_sentences:
            return chunks

        current_sentences: List[str] = []
        current_word_count = 0
        start_page = all_sentences[0][0]
        end_page = start_page
        chunk_idx = 0

        for page_num, sent in all_sentences:
            words_in_sent = len(sent.split())
            is_header = bool(self.header_regex.search(sent))

            if (current_word_count + words_in_sent > self.target_words and current_word_count >= 150) or (
                is_header and current_word_count >= 180
            ):
                content = " ".join(current_sentences).strip()
                chunk_id = f"{doc_name}_{chunk_idx}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        doc_name=doc_name,
                        title=title,
                        page_start=start_page,
                        page_end=end_page,
                        chunk_index=chunk_idx,
                        content=content,
                        token_count=int(len(content.split()) * 1.3),
                    )
                )
                chunk_idx += 1

                overlap = (
                    current_sentences[-self.overlap_sentences:]
                    if len(current_sentences) >= self.overlap_sentences
                    else []
                )
                current_sentences = list(overlap)
                current_word_count = sum(len(s.split()) for s in current_sentences)
                start_page = page_num

            current_sentences.append(sent)
            current_word_count += words_in_sent
            end_page = page_num

        if current_sentences:
            content = " ".join(current_sentences).strip()
            chunk_id = f"{doc_name}_{chunk_idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    title=title,
                    page_start=start_page,
                    page_end=end_page,
                    chunk_index=chunk_idx,
                    content=content,
                    token_count=int(len(content.split()) * 1.3),
                )
            )

        return chunks
