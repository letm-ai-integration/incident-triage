from app.guardrails import config
from app.guardrails.backends.custom_backend import CustomGuardrailBackend
from app.guardrails.backends.nemo_backend import NemoGuardrailBackend
from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType


def test_default_backend_is_custom_for_every_check_type() -> None:
    for check_type in GuardrailCheckType:
        assert isinstance(get_backend(check_type), CustomGuardrailBackend)


def test_overriding_config_routes_to_the_configured_backend() -> None:
    original = config.DEFAULT_BACKENDS[GuardrailCheckType.SAFETY]
    config.DEFAULT_BACKENDS[GuardrailCheckType.SAFETY] = "nemo"
    try:
        assert isinstance(get_backend(GuardrailCheckType.SAFETY), NemoGuardrailBackend)
    finally:
        config.DEFAULT_BACKENDS[GuardrailCheckType.SAFETY] = original
