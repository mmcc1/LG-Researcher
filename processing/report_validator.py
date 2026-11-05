from domain.report import ResearchReport


class ReportValidator:

    def validate_claim_references(
        self,
        report: ResearchReport,
        valid_reviewed_claim_ids: set[int],
    ) -> None:

        invalid_ids = set()

        for section in report.sections:

            for claim_id in (
                section.reviewed_claim_ids
            ):

                if (
                    claim_id
                    not in valid_reviewed_claim_ids
                ):

                    invalid_ids.add(
                        claim_id
                    )

        if invalid_ids:

            invalid_text = ", ".join(
                str(value)
                for value
                in sorted(invalid_ids)
            )

            raise ValueError(
                "Report contains invalid reviewed "
                "claim references: "
                f"{invalid_text}"
            )