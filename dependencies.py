from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from security import SECRET_KEY, ALGORITHM
from models import TokenData, UserRole, UserInDB, UserModel
from database import get_db  # Make sure this is imported before it's used

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_user_by_username(db: Session, username: str) -> UserModel | None:
    """Query the database for a user by username."""
    return db.query(UserModel).filter(UserModel.username == username).first()

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=UserRole(role))
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = get_user_by_username(db, token_data.username)
    if user is None:
        raise credentials_exception
        
    # Map SQLAlchemy model to Pydantic UserInDB schema
    return UserInDB(
        id=user.id,
        username=user.username,
        email=user.email,
        hashed_password=user.hashed_password,
        role=user.role,
        is_active=user.is_active
    )

def require_role(required_role: UserRole):
    """Role-Based Access Control dependency to restrict endpoints."""
    def role_dependency(current_user: UserInDB = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not permitted. Requires role: {required_role}"
            )
        return current_user
    return role_dependency