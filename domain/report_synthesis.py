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

from pydantic import BaseModel, Field


class ReportSynthesis(BaseModel):

    executive_summary: str = Field(
        description=(
            "An evidence-based summary of the principal "
            "findings, conclusions, and significant "
            "uncertainties presented in the completed "
            "research report sections."
        )
    )

    conclusions: str = Field(
        description=(
            "The overall conclusions that can reasonably "
            "be drawn from the completed research report "
            "sections and their supporting reviewed evidence."
        )
    )

    limitations: list[str] = Field(
        description=(
            "Material evidence gaps, unresolved contradictions, "
            "uncertainties, methodological limitations, "
            "and subjects for which the reviewed evidence "
            "was insufficient."
        )
    )
