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

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedChunk:

    index: int

    text: str

    score: float


class QuestionChunkRanker:

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "could",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "specifically",
        "that",
        "the",
        "their",
        "this",
        "to",
        "used",
        "what",
        "which",
        "with",
    }

    def rank(
        self,
        question: str,
        chunks: list[str],
    ) -> list[RankedChunk]:

        terms = self._extract_terms(
            question
        )

        ranked = []

        for index, chunk in enumerate(chunks):

            score = self._score(
                terms,
                chunk,
            )

            ranked.append(
                RankedChunk(
                    index=index,
                    text=chunk,
                    score=score,
                )
            )

        return sorted(
            ranked,
            key=lambda item: item.score,
            reverse=True,
        )

    def _extract_terms(
        self,
        text: str,
    ) -> set[str]:

        words = re.findall(
            r"[A-Za-z0-9]+",
            text.lower(),
        )

        return {
            word
            for word in words
            if (
                len(word) >= 3
                and word not in self.STOP_WORDS
            )
        }

    def _score(
        self,
        terms: set[str],
        chunk: str,
    ) -> float:

        if not terms:
            return 0.0

        chunk_words = re.findall(
            r"[A-Za-z0-9]+",
            chunk.lower(),
        )

        if not chunk_words:
            return 0.0

        frequencies = {}

        for word in chunk_words:

            frequencies[word] = (
                frequencies.get(
                    word,
                    0,
                )
                + 1
            )

        matched_terms = 0
        occurrence_score = 0

        for term in terms:

            count = frequencies.get(
                term,
                0,
            )

            if count > 0:

                matched_terms += 1

                occurrence_score += min(
                    count,
                    5,
                )

        #
        # Reward breadth strongly:
        # a chunk matching Shor + ECDSA + Bitcoin
        # is preferable to one mentioning Bitcoin
        # ten times.
        #

        coverage = (
            matched_terms
            / len(terms)
        )

        return (
            coverage * 10.0
            + occurrence_score
        )