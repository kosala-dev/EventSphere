from pydantic import BaseModel, EmailStr
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base  # Absolute import

# --- SQLAlchemy Database Models ---

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="attendee")
    is_active = Column(Boolean, default=True)


class VenueModel(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    capacity = Column(Integer)
    description = Column(Text)
    image_url = Column(String)
    hourly_rate = Column(Float)
    is_open_for_hire = Column(Boolean, default=True)


class EventModel(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    description = Column(Text)
    status = Column(String, default="draft")

    venue = relationship("VenueModel")
    ticket_categories = relationship("TicketCategoryModel", back_populates="event", cascade="all, delete-orphan")


class TicketCategoryModel(Base):
    __tablename__ = "ticket_categories"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)

    event = relationship("EventModel", back_populates="ticket_categories")


class BookingModel(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    ticket_category_id = Column(Integer, ForeignKey("ticket_categories.id"))
    quantity = Column(Integer)
    total_price = Column(Float)
    payment_reference = Column(String, unique=True)
    status = Column(String, default="active")
    booked_at = Column(DateTime, default=datetime.utcnow)
    hold_expires_at = Column(DateTime, nullable=True)

    event = relationship("EventModel")
    ticket_category = relationship("TicketCategoryModel")
    tickets = relationship("TicketModel", back_populates="booking", cascade="all, delete-orphan")


class TicketModel(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    ticket_code = Column(String, unique=True, index=True)
    is_checked_in = Column(Boolean, default=False)
    checked_in_at = Column(DateTime, nullable=True)
    scan_attempts = Column(Integer, default=0)

    booking = relationship("BookingModel", back_populates="tickets")


class PrivateHireRequestModel(Base):
    __tablename__ = "private_hire_requests"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    purpose = Column(String)
    guest_count = Column(Integer)
    total_price = Column(Float)
    status = Column(String, default="pending")
    admin_notes = Column(String, nullable=True)

    venue = relationship("VenueModel")


class AgentMessageModel(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, index=True)
    sender = Column(String, index=True)
    receiver = Column(String, index=True)
    performative = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# --- Pydantic Enums & Schemas ---

class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    attendee = "attendee"

class UserInDB(BaseModel):
    id: int
    username: str
    email: EmailStr
    hashed_password: str
    role: UserRole
    is_active: bool = True

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    username: str | None = None
    role: UserRole | None = None