from datetime import datetime

from sqlalchemy.orm import Session

from models import EventModel, PrivateHireRequestModel, VenueModel
from agents.message_bus import MessageBus


class VenueAgent:
    """
    VenueAgent decides whether a private hire request is feasible based on venue
    availability and current bookings.
    """

    AGENT_NAME = "VenueAgent"

    @staticmethod
    def _venue_is_available(db: Session, venue_id: int, start_time: datetime, end_time: datetime, exclude_request_id: int = None) -> bool:
        query = db.query(PrivateHireRequestModel).filter(
            PrivateHireRequestModel.venue_id == venue_id,
            PrivateHireRequestModel.status.in_(["confirmed", "pending_admin_approval", "pending"]),
            PrivateHireRequestModel.start_time < end_time,
            PrivateHireRequestModel.end_time > start_time,
        )
        if exclude_request_id is not None:
            query = query.filter(PrivateHireRequestModel.id != exclude_request_id)

        has_overlap = db.query(query.exists()).scalar()

        if has_overlap:
            return False

        query = db.query(EventModel).filter(
            EventModel.venue_id == venue_id,
            EventModel.status == "published",
            EventModel.start_time < end_time,
            EventModel.end_time > start_time,
        )
        if exclude_request_id is not None:
            query = query.filter(EventModel.id != exclude_request_id)
        return not db.query(query.exists()).scalar()

    @staticmethod
    def evaluate_private_hire(db: Session, conversation_id: str, request_data: dict, requester: str = None) -> dict:
        venue_id = request_data.get("venue_id")
        start_time = request_data.get("start_time")
        end_time = request_data.get("end_time")

        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        if not venue_id:
            return {"status": "refused", "reason": "Venue ID is required."}

        venue = db.query(VenueModel).filter(VenueModel.id == venue_id).first()
        if venue is None:
            return {"status": "refused", "reason": "Selected venue does not exist."}

        if not venue.is_open_for_hire:
            return {"status": "refused", "reason": "This venue is currently unavailable for hire."}

        if end_time <= start_time:
            return {"status": "refused", "reason": "End time must be after start time."}

        if not VenueAgent._venue_is_available(db, venue_id, start_time, end_time):
            reason = "VenueAgent Refusal: Requested time slot overlaps with an existing booking or event."
            MessageBus.send_message(
                db,
                conversation_id,
                VenueAgent.AGENT_NAME,
                requester or "system",
                "REFUSE",
                {"reason": reason},
            )
            return {"status": "refused", "reason": reason}

        duration_hours = (end_time - start_time).total_seconds() / 3600
        total_price = round(duration_hours * float(venue.hourly_rate), 2)

        message = (
            f"The venue is available for a private hire request from {start_time} to {end_time}. "
            f"Total estimated cost: ${total_price:.2f}."
        )
        MessageBus.send_message(
            db,
            conversation_id,
            VenueAgent.AGENT_NAME,
            requester or "system",
            "AGREE",
            {"message": message, "total_price": total_price},
        )

        return {
            "status": "confirmed",
            "message": message,
            "total_price": total_price,
            "alternatives": [],
        }
