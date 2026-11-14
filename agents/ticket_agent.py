from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from models import TicketModel
from agents.message_bus import MessageBus

class TicketAgent:
    """
    TicketAgent manages unique QR token generation and single-use door check-ins.
    Tracks repeated scan attempts in state for security.
    Written by student for ICA 02.
    """
    AGENT_NAME = "TicketAgent"

    @staticmethod
    def issue_tickets(db: Session, conversation_id: str, booking_id: int, quantity: int):
        tickets = []
        for _ in range(quantity):
            code = uuid.uuid4().hex
            ticket = TicketModel(
                booking_id=booking_id,
                ticket_code=code,
                is_checked_in=False,
                scan_attempts=0  # Persistent state tracking suspicious repeated scans
            )
            db.add(ticket)
            tickets.append(code)
        db.commit()

        MessageBus.send_message(
            db, conversation_id, TicketAgent.AGENT_NAME, "BookingAgent", "INFORM",
            {"status": "tickets_issued", "count": quantity}
        )
        return tickets

    @staticmethod
    def verify_scan(db: Session, conversation_id: str, ticket_code: str, expected_event_id: int, staff_user: str) -> dict:
        ticket = db.query(TicketModel).filter(TicketModel.ticket_code == ticket_code).first()

        if not ticket:
            MessageBus.send_message(db, conversation_id, TicketAgent.AGENT_NAME, staff_user, "REFUSE", {"reason": "Invalid ticket code."})
            return {"status": "rejected", "reason": "Invalid ticket code."}

        # Track scan attempts in state (Advanced feature: detects suspicious repeated scans)
        ticket.scan_attempts = (ticket.scan_attempts or 0) + 1
        db.commit()

        if ticket.booking.status == "cancelled":
            MessageBus.send_message(db, conversation_id, TicketAgent.AGENT_NAME, staff_user, "REFUSE", {"reason": "Ticket belongs to a cancelled booking."})
            return {"status": "rejected", "reason": "Ticket belongs to a cancelled booking."}

        if ticket.booking.event_id != expected_event_id:
            MessageBus.send_message(db, conversation_id, TicketAgent.AGENT_NAME, staff_user, "REFUSE", {"reason": "Ticket is for another event."})
            return {"status": "rejected", "reason": "Ticket is for another event."}

        if ticket.is_checked_in:
            reason = f"Duplicate Scan Detected! Already checked in at {ticket.checked_in_at} (Attempt #{ticket.scan_attempts})"
            MessageBus.send_message(db, conversation_id, TicketAgent.AGENT_NAME, staff_user, "FAILURE", {"reason": reason})
            return {"status": "rejected", "reason": reason}

        # Successful single-use admission
        ticket.is_checked_in = True
        ticket.checked_in_at = datetime.utcnow()
        db.commit()

        MessageBus.send_message(
            db, conversation_id, TicketAgent.AGENT_NAME, staff_user, "AGREE",
            {"message": "Access granted. Ticket verified successfully."}
        )
        return {"status": "admitted", "ticket_id": ticket.id}