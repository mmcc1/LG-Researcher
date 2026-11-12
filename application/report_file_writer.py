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