"""Pruebas de selección del modelo Ollama."""

import pytest

from cafe_ai_agents import config


def test_selects_default_model_when_available(monkeypatch):
    monkeypatch.setattr(config, "get_available_models", lambda base_url: ["tinyllama:latest", "llama3.2:latest"])
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert config.select_model("http://localhost:11434") == "llama3.2:latest"


def test_reports_missing_requested_model(monkeypatch):
    monkeypatch.setattr(config, "get_available_models", lambda base_url: ["tinyllama:latest"])
    with pytest.raises(RuntimeError, match="no está instalado"):
        config.select_model("http://localhost:11434", "modelo-inexistente")
