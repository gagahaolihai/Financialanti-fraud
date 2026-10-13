"""安全模块单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from engine.security import DataEncryptor, DataMasker, JWTAuth


class TestDataEncryption:
    """数据加密测试"""

    @pytest.fixture
    def encryptor(self):
        return DataEncryptor("test-key-for-unit-testing-only")

    def test_encrypt_decrypt_json(self, encryptor):
        data = {"user_id": "test", "points": 100, "name": "测试用户",
                "nested": {"key": "value"}}
        encrypted = encryptor.encrypt_json(data)
        assert encrypted != str(data)
        assert len(encrypted) > 10
        decrypted = encryptor.decrypt_json(encrypted)
        assert decrypted["user_id"] == "test"
        assert decrypted["points"] == 100
        assert decrypted["nested"]["key"] == "value"

    def test_encrypt_empty_data(self, encryptor):
        data = {}
        encrypted = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(encrypted)
        assert decrypted == {}

    def test_encrypt_file_roundtrip(self, encryptor, tmp_path):
        data = {"secret": "classified", "level": 5}
        file_path = tmp_path / "test_encrypted.dat"
        encryptor.encrypt_file(str(file_path), data)
        assert file_path.exists()
        decrypted = encryptor.decrypt_file(str(file_path))
        assert decrypted["secret"] == "classified"
        assert decrypted["level"] == 5

    def test_key_generation(self):
        key = DataEncryptor.generate_key()
        assert len(key) > 0
        e = DataEncryptor(key)
        data = {"test": "value"}
        encrypted = e.encrypt_json(data)
        decrypted = e.decrypt_json(encrypted)
        assert decrypted["test"] == "value"

    def test_different_keys_different_output(self):
        e1 = DataEncryptor("key1")
        e2 = DataEncryptor("key2")
        data = {"msg": "hello"}
        enc1 = e1.encrypt_json(data)
        enc2 = e2.encrypt_json(data)
        # 不同密钥加密结果不同
        assert enc1 != enc2

    def test_wrong_key_fails(self):
        e = DataEncryptor("real-key")
        encrypted = e.encrypt_json({"secret": "data"})
        # 使用错误密钥解密应失败
        fake_e = DataEncryptor("wrong-key")
        with pytest.raises(Exception):
            fake_e.decrypt_json(encrypted)

    def test_large_data(self, encryptor):
        data = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}
        encrypted = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(encrypted)
        assert len(decrypted["items"]) == 100


class TestDataMasker:
    """数据脱敏测试"""

    def test_mask_phone(self):
        assert DataMasker.mask_phone("13812345678") == "138****5678"

    def test_mask_short_phone(self):
        assert DataMasker.mask_phone("12345") == "12345"

    def test_mask_id_card(self):
        assert DataMasker.mask_id_card("110101199001011234") == "110101****1234"

    def test_mask_bank_card(self):
        assert DataMasker.mask_bank_card("6222021234567890") == "**** **** **** 7890"

    def test_mask_name(self):
        assert DataMasker.mask_name("张三") == "张*"
        assert DataMasker.mask_name("李") == "李"
        assert DataMasker.mask_name("欧阳小明") == "欧***"

    def test_mask_json_sensitive(self):
        data = {"name": "张三", "phone": "13812345678",
                "id_card": "110101199001011234", "age": 30}
        masked = DataMasker.mask_json_sensitive(data)
        assert "***" in masked["name"] or masked["name"] != "张三"
        assert "****" in masked["phone"]
        assert masked["age"] == 30

    def test_mask_json_nested(self):
        data = {"user": {"name": "李四", "phone": "13900001111", "address": "北京"}}
        masked = DataMasker.mask_json_sensitive(data)
        assert "****" in masked["user"]["phone"] or "***" in str(masked["user"])

    def test_mask_json_list(self):
        data = {"users": [{"name": "A", "phone": "13800001111"},
                          {"name": "B", "phone": "13900002222"}]}
        masked = DataMasker.mask_json_sensitive(data)
        assert len(masked["users"]) == 2
        # 敏感字段已被脱敏
        for u in masked["users"]:
            assert "****" in str(u) or "***" in str(u)


class TestJWTAuth:
    """JWT认证测试"""

    @pytest.fixture
    def auth(self):
        return JWTAuth("test-jwt-secret-for-testing")

    def test_create_and_verify(self, auth):
        token = auth.create_token("user123", role="user", expiry_hours=24)
        assert token.count('.') == 2
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "user123"
        assert payload["role"] == "user"

    def test_expired_token(self, auth):
        token = auth.create_token("user123", expiry_hours=0)
        payload = auth.verify_token(token)
        assert payload is None  # 已过期

    def test_invalid_token(self, auth):
        payload = auth.verify_token("invalid.token.format")
        assert payload is None

    def test_tampered_token(self, auth):
        token = auth.create_token("user123")
        tampered = token[:-5] + "XXXXX"
        payload = auth.verify_token(tampered)
        assert payload is None

    def test_different_secrets(self):
        a1 = JWTAuth("secret1")
        a2 = JWTAuth("secret2")
        token = a1.create_token("user1")
        # 用不同secret验证应该失败
        payload = a2.verify_token(token)
        assert payload is None

    def test_token_with_role(self, auth):
        admin_token = auth.create_token("admin1", role="admin")
        user_token = auth.create_token("user1", role="user")
        assert auth.verify_token(admin_token)["role"] == "admin"
        assert auth.verify_token(user_token)["role"] == "user"
