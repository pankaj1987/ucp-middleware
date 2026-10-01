from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class PolicyType(str, Enum):
    RETURN = "return"
    REFUND = "refund"
    WARRANTY = "warranty"
    CANCELLATION = "cancellation"

class PolicySnapshot(BaseModel):
    policy_id: str = Field(..., description="Unique immutable policy identifier, e.g., POL-30D-RET")
    type: PolicyType = Field(..., description="Category of policy")
    summary: str = Field(..., description="Short human-readable summary of policy terms")
    url: Optional[str] = Field(None, description="Direct merchant URL to official terms")
    period_days: Optional[int] = Field(None, description="Window of eligibility in calendar days")
    restocking_fee_pct: Optional[float] = Field(0.0, description="Restocking fee percentage if applicable")
    version: str = Field("v2026-08-25", description="UCP specification version lock")

def get_default_item_policies() -> List[PolicySnapshot]:
    return [
        PolicySnapshot(
            policy_id="POL-30D-RET",
            type=PolicyType.RETURN,
            summary="30-day no-questions-asked return with free pre-paid label",
            url="https://merchant.example.com/policies/returns",
            period_days=30,
            restocking_fee_pct=0.0
        ),
        PolicySnapshot(
            policy_id="POL-1Y-WARR",
            type=PolicyType.WARRANTY,
            summary="1-year comprehensive hardware/manufacturing defect warranty",
            url="https://merchant.example.com/policies/warranty",
            period_days=365,
            restocking_fee_pct=0.0
        )
    ]