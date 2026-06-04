import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlmodel import Session, select
from app.db import engine
from app.models import User
from app.security import hash_password

users_data = [
    ("alice@example.com", "Alice Wang", "member", True),
    ("bob@example.com", "Bob Chen", "member", True),
    ("carol@example.com", "Carol Liu", "admin", True),
    ("dave@example.com", "Dave Zhang", "member", False),
    ("eve@example.com", "Eve Li", "member", True),
    ("frank@example.com", "Frank Zhao", "member", False),
    ("grace@example.com", "Grace Huang", "member", True),
    ("henry@example.com", "Henry Wu", "admin", True),
    ("iris@example.com", "Iris Sun", "member", False),
    ("jack@example.com", "Jack Xu", "member", True),
    ("kate@example.com", "Kate Yang", "member", False),
    ("leo@example.com", "Leo Lin", "member", True),
    ("mary@example.com", "Mary Tang", "member", True),
    ("nina@example.com", "Nina Zhou", "member", False),
    ("oscar@example.com", "Oscar Deng", "member", True),
    ("paul@example.com", "Paul Ma", "member", True),
    ("quin@example.com", "Quin Hu", "member", False),
    ("rose@example.com", "Rose Feng", "member", True),
    ("sam@example.com", "Sam Guo", "admin", False),
    ("tina@example.com", "Tina Pan", "member", True),
]

password = "test1234"

with Session(engine) as session:
    created = 0
    for email, display_name, role, is_active in users_data:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            print(f"  SKIP  {email} (already exists)")
            continue
        user = User(
            email=email,
            display_name=display_name,
            role=role,
            password_hash=hash_password(password),
            is_active=is_active,
        )
        session.add(user)
        created += 1
        status = "active" if is_active else "disabled"
        print(f"  ADD   {display_name} <{email}>  role={role}  [{status}]")

    session.commit()
    print(f"\nDone. Created {created} users (password: {password})")
