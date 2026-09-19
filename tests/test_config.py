from schoolpass.config import Settings


def test_production_rejects_dev_otp_and_default_secrets() -> None:
    settings = Settings(
        app_env="production",
        otp_dev_allow=True,
        jwt_private_key_pem="x",
        jwt_public_key_pem="y",
        secret_app_key="dev-only-not-for-production",
        database_url="postgresql+asyncpg://schoolpass_app:real@db/schoolpass",
    )
    try:
        settings.assert_secure_for_environment()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "OTP_DEV_ALLOW" in str(exc)
