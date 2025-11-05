from pathlib import Path


def test_offline_install_template_contains_required_tokens() -> None:
    template_path = Path("docs/templates/offline_install.md")
    assert template_path.exists(), "offline install template is missing"

    content = template_path.read_text(encoding="utf-8")

    required_tokens = [
        "{{bundle.version}}",
        "make bundle-offline",
        "make bundle-verify",
        "poetry install --sync",
        "gpg --verify",
        "shasum -a 256",
    ]

    missing = [token for token in required_tokens if token not in content]
    assert not missing, f"template is missing required tokens: {missing}"
