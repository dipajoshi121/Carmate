# backend/routes/service_requests.py (FastAPI example)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

router = APIRouter()

class EstimateIn(BaseModel):
    currency: str = Field(default="USD", max_length=5)
    labor: float = Field(ge=0)
    parts: float = Field(ge=0)
    tax: float = Field(ge=0)
    fees: float = Field(default=0, ge=0)
    notes: Optional[str] = Field(default="")
    valid_until: Optional[date] = None

def calc_total(e: EstimateIn) -> float:
    return round(e.labor + e.parts + e.tax + e.fees, 2)

@router.patch("/api/service-requests/{request_id}/estimate")
def submit_estimate(request_id: str, est: EstimateIn, user=Depends(...)):  # <-- your auth here
    # 1) check permissions (technician/admin only)
    # if user.role not in ("admin", "technician"):
    #     raise HTTPException(status_code=403, detail="Not allowed")

    # 2) load request from DB
    req = ...  # fetch request by id
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # 3) save estimate into the request
    estimate_obj = est.dict()
    estimate_obj["total"] = calc_total(est)
    estimate_obj["status"] = "submitted"   # optional: submitted/accepted/rejected

    req["estimate"] = estimate_obj
    req["status"] = "Quoted"  # optional: update request status
    ...  # persist req

    return {"ok": True, "requestId": request_id, "estimate": req["estimate"]}