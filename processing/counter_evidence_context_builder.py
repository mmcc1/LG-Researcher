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

class CounterEvidenceContextBuilder:

    def __init__(
        self,
        max_chars: int = 8000,
    ):
        if max_chars <= 0:
            raise ValueError(
                "max_chars must be greater "
                "than zero."
            )

        self.max_chars = max_chars

    def build(
        self,
        findings,
    ) -> str:

        if not findings:
            return ""

        claims = []
        seen = set()

        for finding in findings:

            claim = self._normalise(
                finding.claim
            )

            if not claim:
                continue

            key = claim.casefold()

            if key in seen:
                continue

            seen.add(key)
            claims.append(claim)

        if not claims:
            return ""

        lines = []

        header = (
            "Existing research claims:\n"
        )

        current_length = len(header)

        for index, claim in enumerate(
            claims,
            start=1,
        ):

            line = (
                f"{index}. {claim}"
            )

            additional_length = (
                len(line) + 1
            )

            if (
                current_length
                + additional_length
                > self.max_chars
            ):
                break

            lines.append(line)

            current_length += (
                additional_length
            )

        if not lines:
            return ""

        return (
            header
            + "\n".join(lines)
        )

    @staticmethod
    def _normalise(
        value: str,
    ) -> str:

        return " ".join(
            value.split()
        )