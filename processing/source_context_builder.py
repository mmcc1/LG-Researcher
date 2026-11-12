#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from processing.chunk_ranker import (
    QuestionChunkRanker,
)
from processing.text_chunker import (
    TextChunker,
)


class SourceContextBuilder:

    def __init__(
        self,
        chunker: TextChunker,
        ranker: QuestionChunkRanker,
        max_chunks: int = 3,
        max_characters: int = 10000,
        chunking_enabled: bool = True,
    ):
        self.chunker = chunker
        self.ranker = ranker
        self.max_chunks = max_chunks
        self.max_characters = max_characters
        self.chunking_enabled = chunking_enabled

    def build(
        self,
        question: str,
        source_text: str,
    ) -> tuple[str, int, int]:

        if not self.chunking_enabled:

            source_text = source_text.strip()

            if not source_text:

                return (
                    "",
                    0,
                    0,
                )

            context = source_text[
                :self.max_characters
            ]

            return (
                context,
                1,
                1,
            )

        chunks = self.chunker.split(
            source_text
        )

        ranked = self.ranker.rank(
            question=question,
            chunks=chunks,
        )

        print("Chunk ranking:")

        for item in ranked:

            print(
                f"  chunk "
                f"{item.index + 1}: "
                f"{item.score:.2f}"
            )
            
        selected = ranked[
            :self.max_chunks
        ]

        #
        # Put selected chunks back into original
        # document order before sending them to
        # the model.
        #

        selected = sorted(
            selected,
            key=lambda item: item.index,
        )

        context_parts = []

        current_length = 0

        for chunk in selected:

            remaining = (
                self.max_characters
                - current_length
            )

            if remaining <= 0:
                break

            text = chunk.text

            if len(text) > remaining:

                text = text[:remaining]

            context_parts.append(
                (
                    f"[SOURCE CHUNK "
                    f"{chunk.index + 1}]\n"
                    f"{text}"
                )
            )

            current_length += len(text)

        context = "\n\n".join(
            context_parts
        )

        return (
            context,
            len(chunks),
            len(selected),
        )