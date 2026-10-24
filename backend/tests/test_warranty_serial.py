import unittest

from app.modules.warranty.serials import luhn_check_digit, validate_warranty_serial


class WarrantySerialTests(unittest.TestCase):
    def test_known_body_uses_standard_luhn(self):
        body = "20260728000042"
        check = luhn_check_digit(body)
        serial = f"2026-07-28-000042-{check}"
        self.assertTrue(validate_warranty_serial(serial))

    def test_rejects_bad_check_digit(self):
        body = "20260728000042"
        check = luhn_check_digit(body)
        bad = (check + 1) % 10
        self.assertFalse(validate_warranty_serial(f"2026-07-28-000042-{bad}"))

    def test_rejects_invalid_date_and_zero_sequence(self):
        self.assertFalse(validate_warranty_serial("2026-13-40-000001-0"))
        self.assertFalse(validate_warranty_serial("2026-07-28-000000-0"))


if __name__ == "__main__":
    unittest.main()
