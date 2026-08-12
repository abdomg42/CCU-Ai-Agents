from pydantic import BaseModel, Field


class RemediationExplanationSchema(BaseModel):
    """Explication textuelle de remédiation, sans action exécutable."""

    explanation: str = Field(
        ...,
        description=(
            "Structured explanation containing What happened / Why / Recommendation. "
            "No executable action."
        ),
    )
