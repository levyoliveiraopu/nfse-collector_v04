"""Contrato estatico do bootstrap Docker local."""

from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "infra" / "local" / "start.ps1"


def test_start_script_supports_explicit_environment_and_tenant() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '[ValidateSet("HOMOLOGACAO", "PRODUCAO")]' in source
    assert '[string]$AdnEnvironment' in source
    assert '[string]$TenantName' in source
    assert 'Set-EnvValue -Path $envFile -Name "NFSE_AMBIENTE"' in source
    assert 'Set-EnvValue -Path $envFile -Name "API_SEED_TENANT_NAME"' in source


def test_start_script_only_updates_values_when_parameter_was_bound() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '$PSBoundParameters.ContainsKey("AdnEnvironment")' in source
    assert '$PSBoundParameters.ContainsKey("TenantName")' in source
