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

class TextChunker:

    def __init__(
        self,
        chunk_size: int = 4000,
        overlap: int = 400,
    ):
        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than zero."
            )

        if overlap < 0:
            raise ValueError(
                "overlap cannot be negative."
            )

        if overlap >= chunk_size:
            raise ValueError(
                "overlap must be smaller than "
                "chunk_size."
            )

        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(
        self,
        text: str,
    ) -> list[str]:

        text = text.strip()

        if not text:
            return []

        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:

            end = min(
                start + self.chunk_size,
                text_length,
            )

            chunk = text[start:end]

            #
            # If we're not at the end, try to finish
            # at a natural boundary.
            #

            if end < text_length:

                boundary = self._find_boundary(
                    chunk
                )

                if boundary is not None:

                    end = start + boundary

                    chunk = text[start:end]

            chunk = chunk.strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = max(
                end - self.overlap,
                start + 1,
            )

        return chunks

    def _find_boundary(
        self,
        text: str,
    ) -> int | None:

        #
        # Search backwards through the latter
        # half of the chunk for a sensible
        # paragraph/sentence boundary.
        #

        minimum = len(text) // 2

        candidates = [
            "\n\n",
            "\n",
            ". ",
        ]

        for separator in candidates:

            position = text.rfind(
                separator,
                minimum,
            )

            if position != -1:

                return (
                    position
                    + len(separator)
                )

        return None