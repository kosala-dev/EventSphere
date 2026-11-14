from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum
from sqlalchemy.orm import Session
from dependencies import require_role
from models import UserRole
from database import get_db
from models import EventModel, VenueModel, TicketCategoryModel

router = APIRouter(prefix="/events", tags=["Event Management"])

class EventStatus(str, Enum):
    draft = "draft"
    published = "published"
    cancelled = "cancelled"

class TicketCategory(BaseModel):
    name: str
    price: float = Field(..., ge=0)
    quantity: int = Field(..., gt=0)

class EventCreate(BaseModel):
    title: str
    category: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    description: str
    status: EventStatus = EventStatus.draft
    ticket_categories: List[TicketCategory]

class EventResponse(EventCreate):
    id: int

    class Config:
        from_attributes = True


# checking overlapping
def venue_agent_check_overlap(db: Session, venue_id: int, start: datetime, end: datetime, exclude_event_id: int = None) -> bool:
    query = db.query(EventModel).filter(
        EventModel.venue_id == venue_id,
        EventModel.status == EventStatus.published,
        EventModel.start_time < end,
        EventModel.end_time > start
    )
    if exclude_event_id:
        query = query.filter(EventModel.id != exclude_event_id)
    return db.query(query.exists()).scalar()


# create an event
@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    # validate time that is aftter the strt time
    if event.end_time <= event.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    # find venue to check capacity
    venue = db.query(VenueModel).filter(VenueModel.id == event.venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Selected venue does not exist.")

    # total tickets > capacity then error
    total_tickets = sum(cat.quantity for cat in event.ticket_categories)
    if total_tickets > venue.capacity:
        raise HTTPException(
            status_code=400, 
            detail=f"Total ticket quantity ({total_tickets}) exceeds venue capacity ({venue.capacity})."
        )

    # check event crash at the same time
    if event.status == EventStatus.published:
        has_clash = venue_agent_check_overlap(db, event.venue_id, event.start_time, event.end_time)
        if has_clash:
            raise HTTPException(
                status_code=400, 
                detail="VenueAgent Refusal: Time slot clashes with an existing event at this venue."
            )

    # save event
    db_event = EventModel(
        title=event.title,
        category=event.category,
        venue_id=event.venue_id,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        status=event.status
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # save ticket categories linked to the event
    for cat in event.ticket_categories:
        db_category = TicketCategoryModel(
            event_id=db_event.id,
            name=cat.name,
            price=cat.price,
            quantity=cat.quantity
        )
        db.add(db_category)
    db.commit()
    db.refresh(db_event)

    return db_event


# updte evnt
@router.patch("/{event_id}/status", response_model=EventResponse)
def update_event_status(
    event_id: int,
    new_status: EventStatus,
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    db_event = db.query(EventModel).filter(EventModel.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    if new_status == EventStatus.published and db_event.status != EventStatus.published:
        if venue_agent_check_overlap(db, db_event.venue_id, db_event.start_time, db_event.end_time, exclude_event_id=db_event.id):
            raise HTTPException(
                status_code=400, 
                detail="VenueAgent Refusal: Cannot publish. Time slot conflicts with another event."
            )
        
    db_event.status = new_status
    db.commit()
    db.refresh(db_event)
    return db_event