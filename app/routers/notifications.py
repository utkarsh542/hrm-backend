"""Notifications router — real-time alerts and updates."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.notification import Notification, NotificationType

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/")
def get_notifications(user_id: int = None, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(Notification)
    if user_id:
        query = query.filter(Notification.user_id == user_id)
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id, "user_id": n.user_id, "title": n.title, "message": n.message,
            "type": n.type.value if n.type else "info", "link": n.link, "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.get("/unread-count")
def get_unread_count(user_id: int, db: Session = Depends(get_db)):
    count = db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False).count()
    return {"count": count}


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"success": True}


@router.put("/read-all")
def mark_all_read(user_id: int, db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"success": True}


def create_notification(db: Session, user_id: int, title: str, message: str, type: str = "info", link: str = None):
    """Helper to create a notification from other routers."""
    notif = Notification(
        user_id=user_id, title=title, message=message,
        type=NotificationType(type) if type in [e.value for e in NotificationType] else NotificationType.info,
        link=link,
    )
    db.add(notif)
    db.commit()
    return notif

