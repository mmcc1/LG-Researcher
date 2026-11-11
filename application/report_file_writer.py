import os
import tempfile

from pathlib import Path
from uuid import UUID


class ReportFileWriter:

    def __init__(
        self,
        output_directory: str | Path,
    ):

        self.output_directory = Path(
            output_directory
        )

    def write(
        self,
        session_id: str,
        report_text: str,
    ) -> Path:

        validated_session_id = str(
            UUID(session_id)
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = (
            self.output_directory
            / f"{validated_session_id}.txt"
        )

        temporary_path = None

        try:

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.output_directory,
                prefix=f".{validated_session_id}-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:

                temporary_path = Path(
                    temporary_file.name
                )

                temporary_file.write(
                    report_text
                )

                temporary_file.flush()

                os.fsync(
                    temporary_file.fileno()
                )

            os.replace(
                temporary_path,
                output_path,
            )

        finally:

            if (
                temporary_path is not None
                and temporary_path.exists()
            ):

                temporary_path.unlink()

        return output_path