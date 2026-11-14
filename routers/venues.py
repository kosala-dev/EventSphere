from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from dependencies import require_role
from database import get_db
from models import UserRole, VenueModel

router = APIRouter(prefix="/venues", tags=["Venue Management"])

class VenueCreate(BaseModel):
    name: str
    location: str
    capacity: int
    description: str
    image_url: str            
    hourly_rate: float        
    is_open_for_hire: bool    

class VenueUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    hourly_rate: Optional[float] = None
    is_open_for_hire: Optional[bool] = None

class VenueResponse(VenueCreate):
    id: int

    class Config:
        from_attributes = True


# create a venue
@router.post("/", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
def create_venue(
    venue: VenueCreate, 
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    db_venue = VenueModel(**venue.model_dump())
    db.add(db_venue)
    db.commit()
    db.refresh(db_venue)
    return db_venue


# edit a venue
@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int, 
    venue_update: VenueUpdate, 
    db: Session = Depends(get_db),
    admin_user = Depends(require_role(UserRole.admin))
):
    db_venue = db.query(VenueModel).filter(VenueModel.id == venue_id).first()
    if not db_venue:
        raise HTTPException(status_code=404, detail="Venue not found")
        
    update_data = venue_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_venue, key, value)
        
    db.commit()
    db.refresh(db_venue)
    return db_venue


# get all venues
@router.get("/", response_model=List[VenueResponse])
def list_venues(db: Session = Depends(get_db)):
    return db.query(VenueModel).all()