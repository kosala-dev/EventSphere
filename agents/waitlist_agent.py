from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
from models import BookingModel, TicketCategoryModel
from agents.message_bus import MessageBus

class WaitlistAgent:
    """
    WaitlistAgent manages seat waitlists and runs a background timer loop 
    to expire unclaimed seat holds automatically (Proactive behavior).
    Written by student for ICA 02.
    """
    AGENT_NAME = "WaitlistAgent"
    HOLD_DURATION_MINUTES = 15  # Rule: seats are held for 15 minutes before expiring

    @staticmethod
    async def run_expiry_sweep_loop(SessionLocal):
        """Proactive background task that runs every minute with no user input."""
        while True:
            await asyncio.sleep(60) # Run every 60 seconds
            db = SessionLocal()
            try:
                # Find expired temporary holds in state
                now = datetime.utcnow()
                expired_holds = db.query(BookingModel).filter(
                    BookingModel.status == "pending_hold",
                    BookingModel.hold_expires_at < now
                ).all()

                for hold in expired_holds:
                    hold.status = "expired"
                    db.commit()
                    
                    # Log message for traceability
                    conv_id = f"sweep-{hold.id}"
                    MessageBus.send_message(
                        db, conv_id, WaitlistAgent.AGENT_NAME, "NotificationAgent", "INFORM",
                        {"recipient": hold.username, "message": "Your temporary seat hold has expired and was released."}
                    )
            except Exception as e:
                print(f"WaitlistAgent background sweep error: {e}")
            finally:
                db.close()