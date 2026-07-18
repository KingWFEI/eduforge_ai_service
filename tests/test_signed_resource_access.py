import unittest
from unittest.mock import patch

from app.services.generated_resource_access_service import SignedResourceAccess
from app.utils.response import AppException


class SignedResourceAccessTests(unittest.TestCase):
    def test_token_round_trip_and_tamper_rejection(self):
        token, _ = SignedResourceAccess.issue("res_test", expires_in=60)
        self.assertEqual(SignedResourceAccess.verify(token), "res_test")
        with self.assertRaises(AppException):
            SignedResourceAccess.verify(token + "x")

    def test_expired_token_is_rejected(self):
        with patch("app.services.generated_resource_access_service.time.time", return_value=100):
            token, _ = SignedResourceAccess.issue("res_test", expires_in=1)
        with patch("app.services.generated_resource_access_service.time.time", return_value=102):
            with self.assertRaises(AppException):
                SignedResourceAccess.verify(token)


if __name__ == "__main__":
    unittest.main()
