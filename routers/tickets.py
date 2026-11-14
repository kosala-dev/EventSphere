from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import qrcode
import io
import base64
from database import get_db
from dependencies import get_current_user, require_role
from models import UserRole, UserInDB, TicketModel, BookingModel

router = APIRouter(prefix="/tickets", tags=["Digital Tickets and Check-In"])


# generate qr code
@router.get("/{ticket_id}/qr")
def get_ticket_qr_code(
    ticket_id: int, 
    db: Session = Depends(get_db), 
    current_user: UserInDB = Depends(get_current_user)
):
    ticket = db.query(TicketModel).filter(TicketModel.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    
    if ticket.booking.username != current_user.username and current_user.role not in [UserRole.admin, UserRole.staff]:
        raise HTTPException(status_code=403, detail="Unauthorized access to this ticket.")

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(ticket.ticket_code)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "ticket_id": ticket.id,
        "ticket_code": ticket.ticket_code,
        "qr_code_base64": f"data:image/png;base64,{encoded_image}"
    }


# scanner
@router.post("/scanner/verify")
def verify_and_check_in_ticket(
    ticket_code: str,
    expected_event_id: int,
    db: Session = Depends(get_db),
    staff_user: UserInDB = Depends(require_role(UserRole.staff))
):
    """
    Validates a scanned ticket code (supports camera scanner feed or manual code entry fallback).
    Ensures it exists, belongs to an active booking, matches the correct event, 
    and has NOT been used yet (single-use enforcement).
    """
    ticket = db.query(TicketModel).filter(TicketModel.ticket_code == ticket_code).first()
    
    # Check if ticket exists
    if not ticket:
        raise HTTPException(status_code=404, detail="Invalid Ticket: Code does not exist in the system.")
    
    # Check if booking is cancelled 
    if ticket.booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Access Denied: This ticket belongs to a cancelled booking.")
    
    # Check if ticket belongs to the correct event 
    if ticket.booking.event_id != expected_event_id:
        raise HTTPException(status_code=400, detail="Access Denied: This ticket is for another event.")

    # Check if already checked in
    if ticket.is_checked_in:
        raise HTTPException(
            status_code=400, 
            detail=f"⚠️ DUPLICATE SCAN REJECTED: Ticket was already checked in at {ticket.checked_in_at}."
        )
    
    # Mark as successfully checked in
    ticket.is_checked_in = True
    ticket.checked_in_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "success",
        "message": "Access Granted: Ticket successfully verified and checked in.",
        "ticket_id": ticket.id,
        "event_id": ticket.booking.event_id,
        "checked_in_at": ticket.checked_in_at
    }