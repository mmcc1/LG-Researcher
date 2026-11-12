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

from domain.control import (
    ControlHelp,
)


class HelpCommandHandler:

    def execute(
        self,
    ) -> ControlHelp:

        return ControlHelp(
            available_operations=[
                "Check the status of the current research.",
                "Start research on a new topic.",
                "Add a research question.",
                "Modify the research scope.",
                "Research part of the topic in more detail.",
                "Search for counter-evidence to a claim.",
                "Generate a research report.",
                "Pause research.",
                "Resume incomplete research.",
            ]
        )