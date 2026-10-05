from unittest import TestCase

from src.security import (AuditLog, check_password_strength, hash_password, mask_card,
                          mask_name, verify_password)


class MaskingTest(TestCase):
    def test_mask_name_hides_identifier(self):
        masked = mask_name("Иванов Иван Иванович")
        self.assertNotIn("Иванов", masked)
        self.assertTrue(masked.startswith("Ив"))

    def test_mask_card_keeps_only_edges(self):
        self.assertEqual(mask_card("4276 1234 5678 9012"), "4276 **** **** 9012")


class PasswordTest(TestCase):
    def test_weak_password_rejected(self):
        self.assertFalse(check_password_strength("abc123"))
        self.assertTrue(check_password_strength("Synergy-2026"))

    def test_hash_and_verify_roundtrip(self):
        digest, salt = hash_password("Synergy-2026")
        self.assertTrue(verify_password("Synergy-2026", digest, salt))
        self.assertFalse(verify_password("Synergy-2025", digest, salt))

    def test_salts_diverge(self):
        a = hash_password("Synergy-2026")
        b = hash_password("Synergy-2026")
        self.assertNotEqual(a[0], b[0])


class AuditLogTest(TestCase):
    def test_chain_is_valid(self):
        log = AuditLog()
        log.add("cli", "login"), log.add("cli", "build_report", "contract=DM-1")
        self.assertTrue(log.verify())

    def test_tampering_is_detected(self):
        log = AuditLog()
        log.add("cli", "login")
        log.add("cli", "refund", "amount=100")
        log.entries[0].details = "amount=999999"
        self.assertFalse(log.verify())
