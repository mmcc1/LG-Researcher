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