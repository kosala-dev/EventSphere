from getpass import getpass

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from pydantic import EmailStr, TypeAdapter, ValidationError

from database import Base, SessionLocal, engine
from models import UserModel, UserRole
from security import hash_password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(UserModel).filter(UserModel.role == UserRole.admin.value).first():
            raise SystemExit("An admin account already exists. Sign in or create accounts from the organiser console.")

        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        try:
            email = TypeAdapter(EmailStr).validate_python(email)
        except ValidationError:
            raise SystemExit("Enter a valid email address.") from None
        password = getpass("Admin password (12-72 UTF-8 bytes): ")
        confirm_password = getpass("Confirm admin password: ")

        if len(username) < 3:
            raise SystemExit("Username must be at least 3 characters.")
        password_length = len(password.encode("utf-8"))
        if password_length < 12 or password_length > 72:
            raise SystemExit("Password must be between 12 and 72 UTF-8 bytes.")
        if password != confirm_password:
            raise SystemExit("Passwords do not match.")

        existing_user = db.query(UserModel).filter(
            or_(UserModel.username == username, UserModel.email == email)
        ).first()
        if existing_user:
            raise SystemExit("That username or email is already in use.")

        db.add(UserModel(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.admin.value,
            is_active=True,
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise SystemExit("An account with that username or email already exists.") from None

        print("Initial admin account created. Use it to log in through the EventSphere login page.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
