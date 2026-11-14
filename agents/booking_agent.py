from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from models import EventModel, TicketCategoryModel, BookingModel
from agents.message_bus import MessageBus

class BookingAgent:
    """
    BookingAgent handles ticket sales fairness, prevents overselling,
    and calculates cancellation refund amounts.
    Written by student for ICA 02.
    """
    AGENT_NAME = "BookingAgent"
    MAX_TICKETS_PER_BOOKING = 6  

    @staticmethod
    def process_booking_request(db: Session, conversation_id: str, booking_data: dict, requester: str) -> dict:
        event_id = booking_data["event_id"]
        category_id = booking_data["ticket_category_id"]
        quantity = booking_data["quantity"]

        # Rule 1: Check max ticket limit per request
        if quantity > BookingAgent.MAX_TICKETS_PER_BOOKING:
            reason = f"Refused: You can only book a maximum of {BookingAgent.MAX_TICKETS_PER_BOOKING} tickets at once."
            MessageBus.send_message(db, conversation_id, BookingAgent.AGENT_NAME, requester, "REFUSE", {"reason": reason})
            return {"status": "refused", "reason": reason}

        # Rule 2: Check category existence and remaining capacity
        category = db.query(TicketCategoryModel).filter(TicketCategoryModel.id == category_id).with_for_update().first()
        if not category:
            reason = "Refused: Ticket category does not exist."
            MessageBus.send_message(db, conversation_id, BookingAgent.AGENT_NAME, requester, "REFUSE", {"reason": reason})
            return {"status": "refused", "reason": reason}

        sold_qty = db.query(BookingModel).filter(
            BookingModel.ticket_category_id == category.id,
            BookingModel.status == "active"
        ).with_entities(BookingModel.quantity).all()
        total_sold = sum(q[0] for q in sold_qty)
        remaining = category.quantity - total_sold

        if quantity > remaining:
            reason = f"Refused: Oversell protection. Only {remaining} tickets left."
            MessageBus.send_message(db, conversation_id, BookingAgent.AGENT_NAME, requester, "REFUSE", {"reason": reason})
            return {"status": "refused", "reason": reason}

        # Rule 3: Approve booking and request TicketAgent to issue unique codes
        total_price = quantity * category.price
        payment_reference = f"PAY-{uuid.uuid4().hex[:8].upper()}"

        new_booking = BookingModel(
            username=requester,
            event_id=event_id,
            ticket_category_id=category.id,
            quantity=quantity,
            total_price=total_price,
            payment_reference=payment_reference,
            status="active"
        )
        db.add(new_booking)
        db.flush()

        # Send REQUEST message to TicketAgent to issue codes (no direct method calls)
        ticket_conv_id = f"ticket-issue-{uuid.uuid4().hex[:6]}"
        MessageBus.send_message(
            db, ticket_conv_id, BookingAgent.AGENT_NAME, "TicketAgent", "REQUEST",
            {"booking_id": new_booking.id, "quantity": quantity}
        )

        # Notify user via NotificationAgent
        MessageBus.send_message(
            db, conversation_id, BookingAgent.AGENT_NAME, "NotificationAgent", "INFORM",
            {"recipient": requester, "message": f"Successfully booked {quantity} tickets for event ID {event_id}."}
        )

        MessageBus.send_message(
            db, conversation_id, BookingAgent.AGENT_NAME, requester, "AGREE",
            {"booking_id": new_booking.id, "payment_reference": payment_reference, "total_price": total_price}
        )

        db.commit()
        return {"status": "agreed", "booking_id": new_booking.id, "payment_reference": payment_reference}

    @staticmethod
    def calculate_refund(db: Session, conversation_id: str, booking_id: int, requester: str) -> dict:
        booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
        if not booking:
            return {"refund_amount": 0.0, "policy": "Booking not found"}

        event = db.query(EventModel).filter(EventModel.id == booking.event_id).first()
        refund_amount = 0.0
        policy = "No refund"

        if event:
            hours_left = (event.start_time - datetime.utcnow()).total_seconds() / 3600
            if hours_left > 48:
                refund_amount = booking.total_price
                policy = "100% refund (> 48 hours notice)"
            elif hours_left > 24:
                refund_amount = booking.total_price * 0.5
                policy = "50% refund (24-48 hours notice)"
            else:
                refund_amount = 0.0
                policy = "0% refund (< 24 hours notice)"

        booking.status = "cancelled"
        db.commit()

        # Inform NotificationAgent
        MessageBus.send_message(
            db, conversation_id, BookingAgent.AGENT_NAME, "NotificationAgent", "INFORM",
            {"recipient": requester, "message": f"Booking #{booking_id} cancelled. Refund: ${refund_amount}"}
        )

        return {"refund_amount": refund_amount, "policy": policy}