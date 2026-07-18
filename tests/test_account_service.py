import io
import tempfile
import unittest
from pathlib import Path

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from app.models.user import User
from app.schemas.user import UserProfileUpdate
from app.services.account_service import (
    update_current_user_avatar,
    update_current_user_profile,
)
from app.utils.response import AppException, ErrorCode


class AccountServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        User.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = User(
            username="zhangsan",
            password_hash="hashed",
            name="旧姓名",
            phone="13800138000",
            email="old@example.com",
            role="student",
            status="normal",
            is_active=True,
            is_phone_verified=True,
            avatar_url="",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_update_profile_returns_full_user_and_allows_empty_email(self):
        payload = UserProfileUpdate(
            name="  张三同学  ",
            phone="13900139000",
            email="",
        )

        result = update_current_user_profile(self.db, self.user, payload)

        self.assertEqual(result["user_id"], str(self.user.id))
        self.assertEqual(result["username"], "zhangsan")
        self.assertEqual(result["name"], "张三同学")
        self.assertEqual(result["phone"], "13900139000")
        self.assertEqual(result["email"], "")
        self.assertEqual(result["role"], "student")
        self.assertEqual(result["status"], "normal")
        self.assertTrue(result["is_active"])
        self.assertIn("created_at", result)
        self.assertIsNone(self.user.email)
        self.assertFalse(self.user.is_phone_verified)

    def test_update_profile_rejects_duplicate_phone_and_email(self):
        other = User(
            username="lisi",
            password_hash="hashed",
            name="李四",
            phone="13700137000",
            email="lisi@example.com",
        )
        self.db.add(other)
        self.db.commit()

        with self.assertRaises(AppException) as phone_error:
            update_current_user_profile(
                self.db,
                self.user,
                UserProfileUpdate(name="张三", phone=other.phone, email="new@example.com"),
            )
        self.assertEqual(phone_error.exception.code, ErrorCode.CONFLICT)

        with self.assertRaises(AppException) as email_error:
            update_current_user_profile(
                self.db,
                self.user,
                UserProfileUpdate(name="张三", phone="13900139000", email="LISI@example.com"),
            )
        self.assertEqual(email_error.exception.code, ErrorCode.CONFLICT)

    def test_update_schema_rejects_invalid_and_immutable_fields(self):
        invalid_payloads = [
            {"name": "张", "phone": "13800138000", "email": "ok@example.com"},
            {"name": "张三", "phone": "12800138000", "email": "ok@example.com"},
            {"name": "张三", "phone": "13800138000", "email": "not-an-email"},
            {
                "name": "张三",
                "phone": "13800138000",
                "email": "ok@example.com",
                "role": "admin",
            },
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                UserProfileUpdate(**payload)

    async def test_upload_avatar_saves_generated_name_and_removes_old_avatar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = Path(temp_dir)
            old_avatar = upload_dir / "old.jpg"
            old_avatar.write_bytes(b"old")
            self.user.avatar_url = "/uploads/avatars/old.jpg"
            self.db.commit()

            file = self._upload(b"\xff\xd8\xffimage-data", "original.jpg", "image/jpeg")
            result = await update_current_user_avatar(
                self.db,
                self.user,
                file,
                upload_dir=upload_dir,
            )

            self.assertRegex(result["avatar_url"], r"^/uploads/avatars/avatar_\d+_[a-f0-9]{32}\.jpg$")
            self.assertNotIn("original", result["avatar_url"])
            self.assertTrue((upload_dir / Path(result["avatar_url"]).name).is_file())
            self.assertFalse(old_avatar.exists())
            self.assertEqual(result["username"], "zhangsan")

    async def test_upload_avatar_rejects_oversize_and_fake_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(AppException) as oversize:
                await update_current_user_avatar(
                    self.db,
                    self.user,
                    self._upload(b"\x89PNG\r\n\x1a\nmore", "a.png", "image/png"),
                    upload_dir=Path(temp_dir),
                    max_bytes=8,
                )
            self.assertEqual(oversize.exception.code, ErrorCode.PAYLOAD_TOO_LARGE)

            with self.assertRaises(AppException) as fake_image:
                await update_current_user_avatar(
                    self.db,
                    self.user,
                    self._upload(b"not-a-real-png", "a.png", "image/png"),
                    upload_dir=Path(temp_dir),
                )
            self.assertEqual(fake_image.exception.code, ErrorCode.PARAM_ERROR)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    @staticmethod
    def _upload(content: bytes, filename: str, content_type: str) -> UploadFile:
        return UploadFile(
            file=io.BytesIO(content),
            filename=filename,
            headers=Headers({"content-type": content_type}),
        )


if __name__ == "__main__":
    unittest.main()
