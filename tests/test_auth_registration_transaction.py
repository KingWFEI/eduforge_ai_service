from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.auth import register_user
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.schemas.user import RegisterRequest
from app.services.verification_service import verify_code


def _session_factory(database_path: Path):
    engine = create_engine(f"sqlite:///{database_path}")
    User.__table__.create(engine)
    VerificationCode.__table__.create(engine)
    return engine, sessionmaker(bind=engine)


def _add_code(db, phone: str = "13800138000", code: str = "123456") -> None:
    db.add(
        VerificationCode(
            phone=phone,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            is_used=False,
        )
    )
    db.commit()


def test_registration_assigns_user_id_and_consumes_code_atomically():
    with TemporaryDirectory() as tmp:
        engine, Session = _session_factory(Path(tmp) / "auth.db")
        db = Session()
        try:
            _add_code(db)
            payload = RegisterRequest(
                name="测试学生",
                username="student_registration",
                phone="13800138000",
                verification_code="123456",
                password="secret123",
            )
            with patch("app.api.v1.auth.hash_password", return_value="hashed"):
                response = register_user(payload, db)

            user = db.query(User).filter(User.username == payload.username).one()
            code = db.query(VerificationCode).filter(VerificationCode.phone == payload.phone).one()
            assert user.id is not None
            assert response["data"]["user_id"] == str(user.id)
            assert code.is_used is True
            assert code.used_at is not None
        finally:
            db.close()
            engine.dispose()


def test_verification_code_consumption_rolls_back_with_business_transaction():
    with TemporaryDirectory() as tmp:
        engine, Session = _session_factory(Path(tmp) / "rollback.db")
        db = Session()
        try:
            _add_code(db)
            verify_code("13800138000", "123456", db)
            db.rollback()

            code = db.query(VerificationCode).filter(VerificationCode.phone == "13800138000").one()
            assert code.is_used is False
            assert code.used_at is None
        finally:
            db.close()
            engine.dispose()
