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
    ):
        self.chunker = chunker
        self.ranker = ranker
        self.max_chunks = max_chunks
        self.max_characters = max_characters

    def build(
        self,
        question: str,
        source_text: str,
    ) -> tuple[str, int, int]:

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