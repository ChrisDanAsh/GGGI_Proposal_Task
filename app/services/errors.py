# The exceptions a service function raises to signal a broken rule,
# expressed in the domain's own vocabulary rather than in terms of HTTP.
# A service says "that name is already taken", not "return a 409" - it
# does not know a web page exists. The route (Module 13) is what decides
# what a person actually sees; a future caller that is not a web page at
# all (a spreadsheet importer, a CLI tool) could decide differently
# without this file changing.

from uuid import UUID


class ProposalError(Exception):
    """Base class for every proposal rule violation.

    Lets a caller catch every domain failure the service layer can raise
    with a single `except ProposalError:` when it does not need to
    distinguish which rule was broken.
    """


class DuplicateProposalError(ProposalError):
    """Raised when a live proposal already uses the requested name."""

    def __init__(self, project_name: str) -> None:
        # Kept as an attribute, not just folded into the message string,
        # because the route needs the raw name to attach the error to
        # the right form field - digging it back out of formatted text
        # would be fragile.
        self.project_name = project_name
        super().__init__(
            f"A proposal named {project_name!r} already exists."
        )


class ProposalNotFoundError(ProposalError):
    """Raised when the requested proposal does not exist or was deleted.

    Raised rather than represented as a returned None: a caller that
    forgets to check a None would render a page around a missing
    proposal and fail confusingly further along, whereas an unhandled
    exception fails immediately and visibly.
    """

    def __init__(self, proposal_id: UUID) -> None:
        self.proposal_id = proposal_id
        super().__init__(f"No proposal with id {proposal_id}.")
