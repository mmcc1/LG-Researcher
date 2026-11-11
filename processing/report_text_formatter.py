class ReportTextFormatter:

    def format(
        self,
        report,
    ) -> str:

        lines = []

        lines.append(
            "=" * 70
        )

        lines.append(
            report.title
        )

        lines.append(
            "=" * 70
        )

        lines.append("")

        lines.append(
            "EXECUTIVE SUMMARY"
        )

        lines.append("")

        lines.append(
            report.executive_summary
        )

        for section in report.sections:

            lines.append("")

            lines.append(
                "-" * 70
            )

            lines.append(
                section.heading
            )

            lines.append(
                "-" * 70
            )

            lines.append("")

            lines.append(
                section.content
            )

            lines.append("")

            claim_ids = [
                str(claim_id)
                for claim_id in section.reviewed_claim_ids
            ]

            lines.append(
                "Reviewed claim IDs: "
                + ", ".join(claim_ids)
            )

        lines.append("")

        lines.append(
            "-" * 70
        )

        lines.append(
            "CONCLUSIONS"
        )

        lines.append(
            "-" * 70
        )

        lines.append("")

        lines.append(
            report.conclusions
        )

        lines.append("")

        lines.append(
            "-" * 70
        )

        lines.append(
            "LIMITATIONS"
        )

        lines.append(
            "-" * 70
        )

        for limitation in report.limitations:

            lines.append(
                f"- {limitation}"
            )

        lines.append("")

        return "\n".join(
            lines
        )