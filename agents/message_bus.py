import json
from datetime import datetime
from sqlalchemy.orm import Session
from models import AgentMessageModel

class MessageBus:
    """
    Handles structured JSON message passing between agents with performatives,
    conversation tracking, and persistent database auditing.
    """
    
    @staticmethod
    def send_message(
        db: Session,
        conversation_id: str,
        sender: str,
        receiver: str,
        performative: str,
        content: dict
    ) -> AgentMessageModel:
        valid_performatives = {"REQUEST", "AGREE", "REFUSE", "PROPOSE", "INFORM", "FAILURE"}
        if performative not in valid_performatives:
            raise ValueError(f"Invalid performative '{performative}'. Must be one of {valid_performatives}")

        content_json = json.dumps(content)

        message_record = AgentMessageModel(
            conversation_id=conversation_id,
            sender=sender,
            receiver=receiver,
            performative=performative,
            content=content_json,
            timestamp=datetime.utcnow()
        )
        
        db.add(message_record)
        db.commit()
        db.refresh(message_record)
        
        return message_record

    @staticmethod
    def get_conversation_logs(db: Session, conversation_id: str = None):
        query = db.query(AgentMessageModel)
        if conversation_id:
            query = query.filter(AgentMessageModel.conversation_id == conversation_id)
        return query.order_by(AgentMessageModel.timestamp.asc()).all()