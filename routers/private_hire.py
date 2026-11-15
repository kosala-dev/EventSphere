from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
import uuid
from database import get_db
from dependencies import get_current_user, require_role
from models import UserInDB, UserRole, PrivateHireRequestModel
from agents.venue_agent import VenueAgent
from agents.message_bus import MessageBus

router = APIRouter(prefix="/private-hire", tags=["Private Venue Hire"])


@router.get("/")
def list_private_hire_requests(
    db: Session = Depends(get_db),
    admin_user: UserInDB = Depends(require_role(UserRole.admin))
):
    requests = db.query(PrivateHireRequestModel).order_by(
        PrivateHireRequestModel.start_time.asc()
    ).all()
    return [
        {
            "id": request.id,
            "username": request.username,
            "venue_id": request.venue_id,
            "venue_name": request.venue.name if request.venue else "Unknown venue",
            "start_time": request.start_time,
            "end_time": request.end_time,
            "purpose": request.purpose,
            "guest_count": request.guest_count,
            "total_price": request.total_price,
            "status": request.status,
            "admin_notes": request.admin_notes,
        }
        for request in requests
    ]


class PrivateHireRequestCreate(BaseModel):
    venue_id: int
    start_time: datetime
    end_time: datetime
    purpose: str
    guest_count: int

@router.post("/", status_code=status.HTTP_201_CREATED)
def request_private_hire(
    req: PrivateHireRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    if req.end_time <= req.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    conversation_id = f"hire-conv-{uuid.uuid4().hex[:6]}"
    
    # Send REQUEST message to start agent dialogue
    MessageBus.send_message(
        db, conversation_id, current_user.username, "VenueAgent", "REQUEST",
        req.model_dump(mode="json")
    )

    # Invoke VenueAgent autonomous decision rule
    decision = VenueAgent.evaluate_private_hire(
        db, conversation_id, req.model_dump(mode="json"), requester=current_user.username
    )

    # Save to database based on agent decision status
    hire_status = "pending"
    if decision["status"] == "confirmed":
        hire_status = "confirmed"
    elif decision["status"] == "refused":
        raise HTTPException(status_code=400, detail=decision["reason"])
    elif decision["status"] == "propose":
        raise HTTPException(
            status_code=400, 
            detail={"message": decision["reason"], "alternatives": decision["alternatives"]}
        )
    elif decision["status"] == "escalated":
        hire_status = "pending_admin_approval"

    new_hire = PrivateHireRequestModel(
        username=current_user.username,
        venue_id=req.venue_id,
        start_time=req.start_time,
        end_time=req.end_time,
        purpose=req.purpose,
        guest_count=req.guest_count,
        total_price=decision.get("total_price", 0.0),
        status=hire_status
    )
    db.add(new_guard := new_hire) 
    db.commit()
    db.refresh(new_hire)

    return {
        "conversation_id": conversation_id,
        "decision": decision["status"],
        "total_price": new_hire.total_price,
        "hire_request_id": new_hire.id,
        "message": decision.get("message", decision.get("reason"))
    }


@router.patch("/{request_id}/admin-decision")
def admin_handle_escalation(
    request_id: int,
    approve: bool,
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    """Admin approves or rejects requests escalated by the VenueAgent (Requirement 6d)."""
    hire_req = db.query(PrivateHireRequestModel).filter(PrivateHireRequestModel.id == request_id).first()
    if not hire_req:
        raise HTTPException(status_code=404, detail="Private hire request not found.")

    hire_req.status = "confirmed" if approve else "rejected"
    db.commit()

    return {
        "status": "success",
        "request_id": hire_req.id,
        "new_status": hire_req.status
    }