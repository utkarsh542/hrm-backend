"""Authentication router — login, register, demo role switching."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.schemas import LoginRequest, TokenResponse, UserResponse, UserCreate
from app.services.auth_service import authenticate_user, create_access_token, hash_password, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.email, "role": user.role.value, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/register", response_model=UserResponse)
def register(request: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role=UserRole(request.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/demo-users", response_model=list[UserResponse])
def get_demo_users(db: Session = Depends(get_db)):
    """Get all demo users for role switching."""
    users = db.query(User).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/switch-role/{user_id}", response_model=TokenResponse)
def switch_role(user_id: int, db: Session = Depends(get_db)):
    """Switch to a demo user role (for demo mode)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token = create_access_token({"sub": user.email, "role": user.role.value, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


# ─── PASSWORD RESET & CHANGE ───

from pydantic import BaseModel

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.auth_service import verify_password, hash_password
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid current password")
        
    # Update password
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()
    
    # Trigger security confirmation alerts
    try:
        from app.services.email_service import send_password_change_alert
        from app.routers.notifications import create_notification
        
        # Send security email
        send_password_change_alert(current_user.email, current_user.full_name)
        
        # Insert real-time warning in-app notification
        create_notification(
            db=db,
            user_id=current_user.id,
            title="Password Changed Successfully",
            message="Your account login password has been changed. If you did not make this change, please alert HR immediately.",
            type="warning"
        )
    except Exception as e:
        from app.logger import logger
        logger.error(f"Error in password change alerts: {e}")
        
    return {"message": "Password updated successfully"}


@router.post("/reset-password-admin/{user_id}")
def reset_password_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.auth_service import hash_password
    
    # Role guard: Only admin or hr can trigger a password reset for employees
    if current_user.role.value not in ["admin", "hr"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    # Locate target user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Reset to default Welcome@123
    user.hashed_password = hash_password("Welcome@123")
    db.commit()
    
    # Trigger reset alerts
    try:
        from app.services.email_service import send_password_reset_alert
        from app.routers.notifications import create_notification
        
        # Send temporary credentials email
        send_password_reset_alert(user.email, user.full_name, "Welcome@123")
        
        # Create in-app notification for the reset recipient
        create_notification(
            db=db,
            user_id=user.id,
            title="Password Reset by Admin",
            message="An administrator has reset your login password to the secure temporary default: Welcome@123.",
            type="info"
        )
    except Exception as e:
        from app.logger import logger
        logger.error(f"Error in password reset alerts: {e}")
        
    return {"message": f"Password reset to Welcome@123 successfully for {user.full_name}"}

