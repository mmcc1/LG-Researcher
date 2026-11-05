class ReviewContextBuilder:

    def build(
        self,
        findings,
        sources_by_id,
    ) -> str:

        parts = []

        for finding in findings:

            source = sources_by_id.get(
                finding.source_id
            )

            if source is None:

                source_title = "Unknown source"
                source_url = "Unknown"

            else:

                source_title = source.title
                source_url = source.final_url

            part = (
                f"FINDING ID: {finding.id}\n"
                f"SOURCE ID: {finding.source_id}\n"
                f"SOURCE TITLE: {source_title}\n"
                f"SOURCE URL: {source_url}\n"
                f"CLAIM:\n{finding.claim}\n\n"
                f"EVIDENCE:\n{finding.evidence}\n\n"
                f"RELEVANCE:\n{finding.relevance}\n\n"
                f"EXTRACTION CONFIDENCE: "
                f"{finding.confidence}"
            )

            parts.append(part)

        return (
            "\n\n"
            "================================\n\n"
        ).join(parts)