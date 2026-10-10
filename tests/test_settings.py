"""環境變數設定的解析與預設值"""

from pathlib import Path

from support_bot.settings import Settings


def test_defaults_use_bundled_example_config():
    settings = Settings.from_env({})

    assert Path(settings.faq_file).is_file()
    assert Path(settings.rules_file).is_file()
    assert settings.admin_user_ids == frozenset()
    assert settings.roster_enabled is False
    assert settings.handoff_notifier == 'log'


def test_from_env_parses_values():
    settings = Settings.from_env({
        'LINE_CHANNEL_SECRET': 'secret',
        'LINE_CHANNEL_ACCESS_TOKEN': 'token',
        'FAQ_FILE': 'shop/faq.yaml',
        'RULES_FILE': 'shop/rules.yaml',
        'ADMIN_USER_IDS': ' Uowner, Ustaff ,, ',
        'ROSTER_ENABLED': 'true',
        'HANDOFF_NOTIFIER': ' LINE_PUSH ',
    })

    assert (settings.line_channel_secret, settings.line_channel_access_token) == ('secret', 'token')
    assert (settings.faq_file, settings.rules_file) == ('shop/faq.yaml', 'shop/rules.yaml')
    assert settings.admin_user_ids == frozenset({'Uowner', 'Ustaff'})
    assert settings.roster_enabled is True
    assert settings.handoff_notifier == 'line_push'


def test_flag_accepts_common_true_values_only():
    for value in ['1', 'true', 'Yes', 'on']:
        assert Settings.from_env({'ROSTER_ENABLED': value}).roster_enabled is True
    for value in ['', '0', 'false', 'off', 'enabled']:
        assert Settings.from_env({'ROSTER_ENABLED': value}).roster_enabled is False


def test_ai_settings():
    assert Settings.from_env({}).ai_enabled is False

    settings = Settings.from_env({
        'AI_ENABLED': 'true',
        'AI_BASE_URL': 'http://localhost:11434/v1',
        'AI_API_KEY': 'key',
        'AI_MODEL': 'model-name',
    })

    assert settings.ai_enabled is True
    assert (settings.ai_base_url, settings.ai_api_key, settings.ai_model) == ('http://localhost:11434/v1', 'key', 'model-name')
    assert Settings.from_env({'AI_BASE_URL': ''}).ai_base_url == 'https://api.openai.com/v1'
