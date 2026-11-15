
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from urllib.parse import (
    urlsplit,
    urlunsplit,
)

from domain.report import (
    PersistedResearchReport,
)

from domain.report_citation import (
    CitationSource,
    ReportCitationProvenance,
)

from domain.report_citation_registry import (
    BibliographyEntry,
    SectionCitationReferences,
    ReportCitationRegistryResult,
)


class ReportCitationRegistry:

    def build(
        self,
        report: PersistedResearchReport,
        provenance: ReportCitationProvenance,
    ) -> ReportCitationRegistryResult:

        if (
            report.research_session_id
            != provenance.research_session_id
        ):

            raise ValueError(
                "Report and citation provenance "
                "belong to different research sessions."
            )

        claims_by_id = {}

        for claim in provenance.claims:

            if claim.reviewed_claim_id in claims_by_id:

                raise ValueError(
                    "Duplicate reviewed claim in "
                    "citation provenance: "
                    f"{claim.reviewed_claim_id}"
                )

            claims_by_id[
                claim.reviewed_claim_id
            ] = claim

        expected_claim_ids = set()

        for section in report.sections:

            expected_claim_ids.update(
                section.reviewed_claim_ids
            )

        actual_claim_ids = set(
            claims_by_id
        )

        if expected_claim_ids != actual_claim_ids:

            missing_claim_ids = (
                expected_claim_ids
                - actual_claim_ids
            )

            unexpected_claim_ids = (
                actual_claim_ids
                - expected_claim_ids
            )

            raise ValueError(
                "Citation provenance does not match "
                "the report's reviewed claims. "
                f"Missing: {sorted(missing_claim_ids)}. "
                f"Unexpected: {sorted(unexpected_claim_ids)}."
            )

        sections = []

        bibliography = []

        entries_by_key = {}

        source_keys_by_id = {}

        ordered_sections = sorted(
            report.sections,
            key=lambda section: (
                section.ordinal,
                section.id,
            ),
        )

        for section in ordered_sections:

            supporting_numbers = []

            contradicting_numbers = []

            seen_supporting_numbers = set()

            seen_contradicting_numbers = set()

            for claim_id in section.reviewed_claim_ids:

                claim = claims_by_id[
                    claim_id
                ]

                for source in claim.supporting_sources:

                    number = self._register_source(
                        source=source,
                        bibliography=bibliography,
                        entries_by_key=entries_by_key,
                        source_keys_by_id=source_keys_by_id,
                    )

                    if number not in seen_supporting_numbers:

                        supporting_numbers.append(
                            number
                        )

                        seen_supporting_numbers.add(
                            number
                        )

                for source in claim.contradicting_sources:

                    number = self._register_source(
                        source=source,
                        bibliography=bibliography,
                        entries_by_key=entries_by_key,
                        source_keys_by_id=source_keys_by_id,
                    )

                    if number not in seen_contradicting_numbers:

                        contradicting_numbers.append(
                            number
                        )

                        seen_contradicting_numbers.add(
                            number
                        )

            sections.append(
                SectionCitationReferences(
                    section_id=section.id,
                    ordinal=section.ordinal,
                    supporting_numbers=(
                        supporting_numbers
                    ),
                    contradicting_numbers=(
                        contradicting_numbers
                    ),
                )
            )

        return ReportCitationRegistryResult(
            research_session_id=(
                report.research_session_id
            ),
            sections=sections,
            bibliography=bibliography,
        )

    def _register_source(
        self,
        source: CitationSource,
        bibliography: list[BibliographyEntry],
        entries_by_key: dict,
        source_keys_by_id: dict,
    ) -> int:

        url = self._normalize_url(
            source.final_url
        )

        key = url

        existing_key = source_keys_by_id.get(
            source.source_id
        )

        if (
            existing_key is not None
            and existing_key != key
        ):

            raise ValueError(
                "Source ID has conflicting URLs "
                "in citation provenance: "
                f"{source.source_id}"
            )

        source_keys_by_id[
            source.source_id
        ] = key

        existing_entry = entries_by_key.get(
            key
        )

        if existing_entry is not None:

            if (
                source.source_id
                not in existing_entry.source_ids
            ):

                existing_entry.source_ids.append(
                    source.source_id
                )

            return existing_entry.number

        title = source.title.strip()

        if not title:

            raise ValueError(
                "Citation source has no title: "
                f"{source.source_id}"
            )

        number = len(bibliography) + 1

        entry = BibliographyEntry(
            number=number,
            title=title,
            url=url,
            source_ids=[
                source.source_id
            ],
        )

        bibliography.append(
            entry
        )

        entries_by_key[
            key
        ] = entry

        return number

    def _normalize_url(
        self,
        url: str,
    ) -> str:

        value = url.strip()

        parsed = urlsplit(
            value
        )

        scheme = parsed.scheme.lower()

        if scheme not in (
            "http",
            "https",
        ):

            raise ValueError(
                "Citation source has an unsupported "
                f"URL scheme: {value}"
            )

        hostname = parsed.hostname

        if not hostname:

            raise ValueError(
                "Citation source URL has no hostname: "
                f"{value}"
            )

        if (
            parsed.username is not None
            or parsed.password is not None
        ):

            raise ValueError(
                "Citation source URL contains "
                "userinfo."
            )

        hostname = hostname.lower()

        if ":" in hostname:

            hostname = f"[{hostname}]"

        port = parsed.port

        if (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):

            port = None

        netloc = hostname

        if port is not None:

            netloc = (
                f"{hostname}:{port}"
            )

        path = parsed.path

        if not path:

            path = "/"

        normalized = urlunsplit(
            (
                scheme,
                netloc,
                path,
                parsed.query,
                "",
            )
        )

        return normalized
