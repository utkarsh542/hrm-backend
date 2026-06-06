"""Authentication service — JWT token management and password hashing."""
from app.utils.timezone import get_ist_date
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.models.user import User
from app.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)



def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token: Optional[str] = None,
    db: Session = Depends(get_db),
) -> User:
    raw_token = None
    if credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*roles: str):
    """Role-based access control dependency factory."""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if role_val.lower() not in [r.lower() for r in roles]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return _check


def get_current_employee(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dependency to retrieve the logged-in user's corresponding Employee record."""
    from app.models.employee import Employee
    from datetime import date
    
    # 1. Search by user_id link
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        # 2. Fallback to matching by email
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if emp:
            emp.user_id = current_user.id
            db.commit()
            db.refresh(emp)
            
    if not emp:
        # 3. Newly registered user: Automatically create associated Employee profile
        from app.routers.employees import _get_next_employee_id
        from app.services.payroll_service import calculate_salary_breakup
        breakup = calculate_salary_breakup(500000) # Default CTC: 5 LPA
        emp = Employee(
            user_id=current_user.id,
            employee_id=_get_next_employee_id(db),
            full_name=current_user.full_name,
            email=current_user.email,
            joining_date=get_ist_date(),
            ctc=500000,
            basic_salary=breakup["basic"],
            hra=breakup["hra"],
            da=breakup["da"],
            special_allowance=breakup["special_allowance"],
            pf_contribution=breakup["pf_employee"],
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        
    return emp

