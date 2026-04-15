from dataclasses import dataclass

from shared.enums import RiskLevel


@dataclass(slots=True)
class RiskAssessment:
    score: int
    level: RiskLevel
    reasons: list[str]

    @property
    def suspicious(self) -> bool:
        return self.level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
