from sqlalchemy.orm import Session
from models import AgentMessageModel
from agents.message_bus import MessageBus

class NotificationAgent:
    """
    NotificationAgent listens to system events and stores user notifications.
    Written by student for ICA 02.
    """
    AGENT_NAME = "NotificationAgent"

    @staticmethod
    def get_user_notifications(db: Session, username: str) -> list:
        # Pulls INFORM messages addressed to this user from the message bus logs
        messages = db.query(AgentMessageModel).filter(
            AgentMessageModel.performative == "INFORM"
        ).order_by(AgentMessageModel.timestamp.desc()).all()

        user_notifs = []
        for msg in messages:
            try:
                import json
                content = json.loads(msg.content)
                if content.get("recipient") == username:
                    user_notifs.append({
                        "timestamp": msg.timestamp,
                        "message": content.get("message")
                    })
            except:
                continue
        return user_notifs