from app.config import Settings


def test_local_dotenv_overrides_base_file_but_process_env_wins(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("BACKEND_API_KEY=base-key\nDEEPSEEK_API_KEY=base-model-key\n")
    (tmp_path / ".env.local").write_text("BACKEND_API_KEY=local-key\nDEEPSEEK_API_KEY=local-model-key\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = Settings()
    assert settings.BACKEND_API_KEY == "local-key"
    assert settings.DEEPSEEK_API_KEY == "local-model-key"

    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-model-key")
    assert Settings().DEEPSEEK_API_KEY == "process-model-key"
