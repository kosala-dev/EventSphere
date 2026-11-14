from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models import UserInDB, UserRole
from models import EventModel, TicketCategoryModel, BookingModel, TicketModel
from .events import EventStatus

router = APIRouter(prefix="", tags=["Browsing and Booking"])

# booking request
class BookingRequest(BaseModel):
    event_id: int
    ticket_category_id: int
    quantity: int


# search events
@router.get("/events/search")
def search_events(
    keyword: Optional[str] = Query(None, description="Search by title or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    query = db.query(EventModel).filter(EventModel.status == EventStatus.published)
    
    if keyword:
        kw = f"%{keyword.lower()}%"
        query = query.filter(
            (EventModel.title.ilike(kw)) | (EventModel.description.ilike(kw))
        )
    
    if category:
        query = query.filter(EventModel.category.ilike(category))
        
    events = query.all()
    results = []
    
    for event in events:
        event_dict = {
            "id": event.id,
            "title": event.title,
            "category": event.category,
            "venue_id": event.venue_id,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "description": event.description,
            "status": event.status,
            "ticket_categories": []
        }
        
        for cat in event.ticket_categories:
            sold = db.query(BookingModel).filter(
                BookingModel.ticket_category_id == cat.id,
                BookingModel.status == "active"
            ).with_entities(BookingModel.quantity).all()
            total_sold = sum(q[0] for q in sold)
            
            cat_dict = {
                "id": cat.id,
                "name": cat.name,
                "price": cat.price,
                "quantity": cat.quantity,
                "tickets_left": cat.quantity - total_sold
            }
            event_dict["ticket_categories"].append(cat_dict)
            
        results.append(event_dict)
            
    return results


# book tickets
@router.post("/bookings/", status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_req: BookingRequest,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    category = db.query(TicketCategoryModel).filter(
        TicketCategoryModel.id == booking_req.ticket_category_id
    ).with_for_update().first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Ticket category not found.")
        
    # verify event is published
    event = db.query(EventModel).filter(
        EventModel.id == booking_req.event_id,
        EventModel.status == EventStatus.published
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Published event not found.")
        
    # calculate currently sold tickets
    sold_qty = db.query(BookingModel).filter(
        BookingModel.ticket_category_id == category.id,
        BookingModel.status == "active"
    ).with_entities(BookingModel.quantity).all()
    total_sold = sum(q[0] for q in sold_qty)
    
    remaining = category.quantity - total_sold
    
    if booking_req.quantity > remaining:
        raise HTTPException(
            status_code=400, 
            detail=f"Oversell protection triggered: Only {remaining} tickets remaining in this category."
        )
    
    # paymeny simulation
    payment_reference = f"PAY-REF-{uuid.uuid4().hex[:8].upper()}"
    
    new_booking = BookingModel(
        username=current_user.username,
        event_id=booking_req.event_id,
        ticket_category_id=category.id,
        quantity=booking_req.quantity,
        total_price=booking_req.quantity * category.price,
        payment_reference=payment_reference,
        status="active",
        booked_at=datetime.utcnow()
    )
    db.add(new_booking)
    db.flush() 
    
    # generate QR 
    for _ in range(booking_req.quantity):
        db.add(TicketModel(
            booking_id=new_booking.id,
            ticket_code=uuid.uuid4().hex,
            is_checked_in=False
        ))
        
    db.commit()
    db.refresh(new_booking)
    return new_booking


# booking history
@router.get("/bookings/history")
def get_booking_history(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    user_bookings = db.query(BookingModel).filter(BookingModel.username == current_user.username).all()
    return user_bookings


# cancl booking
@router.delete("/bookings/{booking_id}")
def cancel_booking(
    booking_id: int, 
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    
    if booking.username != current_user.username and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking.")
    
    if booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Booking is already cancelled.")
    
    event = db.query(EventModel).filter(EventModel.id == booking.event_id).first()
    refund_amount = 0.0
    policy_message = "No refund (cancellation window expired)."
    
    if event:
        hours_until_event = (event.start_time - datetime.utcnow()).total_seconds() / 3600
        if hours_until_event > 48:
            refund_amount = booking.total_price
            policy_message = "100% refund applied (> 48 hours notice)."
        elif hours_until_event > 24:
            refund_amount = booking.total_price * 0.5
            policy_message = "50% refund applied (24-48 hours notice)."
        else:
            refund_amount = 0.0
            policy_message = "0% refund applied (< 24 hours notice)."

    booking.status = "cancelled"
    db.commit()
    
    return {
        "message": "Booking successfully cancelled.",
        "payment_reference": booking.payment_reference,
        "refund_amount": refund_amount,
        "policy_applied": policy_message
    }