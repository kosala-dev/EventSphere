from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from dependencies import require_role
from models import UserRole, EventModel, BookingModel, TicketModel, AgentMessageModel

router = APIRouter(prefix="/dashboard", tags=["Organiser Dashboard"])


# event metrices
@router.get("/metrics")
def get_organiser_metrics(
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    events = db.query(EventModel).all()
    dashboard_data = []

    for event in events:
        total_capacity = sum(cat.quantity for cat in event.ticket_categories)
        
        # all active bookings for this event
        bookings = db.query(BookingModel).filter(
            BookingModel.event_id == event.id,
            BookingModel.status == "active"
        ).all()
        
        tickets_sold = sum(b.quantity for b in bookings)
        simulated_revenue = sum(b.total_price for b in bookings)
        
        # Count check-ins linked through bookings for this event
        booking_ids = [b.id for b in bookings]
        check_ins_count = 0
        if booking_ids:
            check_ins_count = db.query(TicketModel).filter(
                TicketModel.booking_id.in_(booking_ids),
                TicketModel.is_checked_in == True
            ).count()

        dashboard_data.append({
            "event_id": event.id,
            "title": event.title,
            "category": event.category,
            "status": event.status,
            "venue_id": event.venue_id,
            "total_capacity": total_capacity,
            "tickets_sold": tickets_sold,
            "remaining_capacity": total_capacity - tickets_sold,
            "simulated_revenue": round(simulated_revenue, 2),
            "check_ins": check_ins_count,
            "attendance_rate": f"{round((check_ins_count / tickets_sold * 100), 2)}%" if tickets_sold > 0 else "0%"
        })

    return {
        "total_events": len(events),
        "events_breakdown": dashboard_data
    }


# audit log
@router.get("/agent-logs")
def get_agent_message_logs(
    conversation_id: Optional[str] = Query(None, description="Filter logs by a specific multi-agent conversation ID"),
    sender: Optional[str] = Query(None, description="Filter by sending agent name"),
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    """
    Returns a readable chronological log of messages exchanged between agents.
    Essential for tracing user actions across multiple agents during viva testing.
    """
    query = db.query(AgentMessageModel)
    
    if conversation_id:
        query = query.filter(AgentMessageModel.conversation_id == conversation_id)
    if sender:
        query = query.filter(AgentMessageModel.sender.ilike(f"%{sender}%"))
        
    messages = query.order_by(AgentMessageModel.timestamp.asc()).all()
    
    return [
        {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender": msg.sender,
            "receiver": msg.receiver,
            "performative": msg.performative, 
            "content": msg.content,
            "timestamp": msg.timestamp
        }
        for msg in messages
    ]