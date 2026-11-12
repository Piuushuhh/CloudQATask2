"""Runtime configuration loaded from environment and command line."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@dataclass
class Config:
    model: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    allowed_domains: tuple[str, ...] = tuple(x.strip().lower() for x in os.getenv("ALLOWED_DOMAINS", "phptravels.com,app.phptravels.com,localhost,127.0.0.1").split(",") if x.strip())
    timeout_ms: int = int(os.getenv("BROWSER_TIMEOUT_MS", "10000"))
    max_steps: int = int(os.getenv("MAX_STEPS", "20"))
    execution_timeout_s: int = int(os.getenv("EXECUTION_TIMEOUT_S", "120"))
    reports_dir: Path = ROOT / "reports"
    screenshots_dir: Path = ROOT / "screenshots"
    headless: bool = True
    base_url: str = "https://phptravels.com/demo/"

    def validate_url(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only absolute HTTP(S) URLs are allowed")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URLs containing embedded credentials are not allowed")
        host = parsed.hostname.lower()
        if not any(host == domain or host.endswith("." + domain) for domain in self.allowed_domains):
            raise ValueError(f"URL host '{host}' is not allowlisted. Allowed domains: {', '.join(self.allowed_domains)}")
        return url
