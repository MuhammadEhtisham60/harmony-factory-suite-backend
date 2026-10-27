"""
Shared description of the yarn *processing mills* (Sizing and Warping).

Yarn dispatched to a processing mill follows one workflow regardless of the
mill type:

    YarnOutcome (dispatch)  ->  mill  ->  SizingOutcome (set returned)
                                      ->  Beams  ->  BeamLoading  ->  Loom

The services, ledger and viewsets are written once and are parameterised with a
`ProcessingProfile`, so adding a mill type means adding a profile here instead
of duplicating the workflow.

This module is intentionally free of model imports so that models, services
and serializers can all depend on it without circular imports.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProcessingProfile:
    """Static description of one processing mill type."""

    outcome_type: str
    """`YarnOutcome.outcome_type` value that dispatches yarn to this mill."""

    unit_field: str
    """Name of the `YarnOutcome` FK pointing at the mill master record."""

    unit_name_field: str
    """Name attribute on the mill master model."""

    in_progress_status: str
    """`YarnOutcome.status` while the yarn is at the mill and nothing is returned."""

    beam_status: str
    """`Beam.status` while a beam is out at the mill."""

    label: str
    """Human readable mill label used in audit logs and messages."""

    module: str
    """Audit-log module name."""

    @property
    def unit_id_field(self) -> str:
        return f"{self.unit_field}_id"

    def unit_of(self, yarn_outcome):
        """Mill master record of `yarn_outcome` (None when not set)."""
        return getattr(yarn_outcome, self.unit_field, None) if yarn_outcome else None

    def unit_name_of(self, yarn_outcome) -> str:
        unit = self.unit_of(yarn_outcome)
        return getattr(unit, self.unit_name_field, "") if unit else ""


SIZING_PROFILE = ProcessingProfile(
    outcome_type="Sizing",
    unit_field="sizing",
    unit_name_field="sizing_name",
    in_progress_status="In Sizing",
    beam_status="Sizing",
    label="Sizing",
    module="Yarn – Sizing",
)

WARPING_PROFILE = ProcessingProfile(
    outcome_type="Warping",
    unit_field="warping",
    unit_name_field="warping_name",
    in_progress_status="In Warping",
    beam_status="Warping",
    label="Warping",
    module="Yarn – Warping",
)

PROCESSING_PROFILES = {
    SIZING_PROFILE.outcome_type: SIZING_PROFILE,
    WARPING_PROFILE.outcome_type: WARPING_PROFILE,
}

PROCESSING_OUTCOME_TYPES = tuple(PROCESSING_PROFILES)


def get_profile(outcome_type: str) -> Optional[ProcessingProfile]:
    """Profile for `outcome_type`, or None for non-processing types (Weft, Sold)."""
    return PROCESSING_PROFILES.get(outcome_type)


def profile_for(yarn_outcome) -> Optional[ProcessingProfile]:
    """Profile of a YarnOutcome (None when it is not a processing dispatch)."""
    return get_profile(getattr(yarn_outcome, "outcome_type", None))
