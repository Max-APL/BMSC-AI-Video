from pathlib import Path
from string import Template
import html

from app.config import settings


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
ASSET_DIR = Path(__file__).resolve().parent / "assets"
BRAND_NAME = settings.email_brand_name
LOGO_CID = "bmsc-logo"
LOGO_FILENAME = "bmsc-logo.png"
LOGO_PATH = ASSET_DIR / LOGO_FILENAME


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_template(template_name: str, context: dict[str, object]) -> str:
    path = TEMPLATE_DIR / template_name
    template = Template(path.read_text(encoding="utf-8"))
    full_context = {"brand_name": BRAND_NAME, **context}
    return template.substitute({key: str(value) for key, value in full_context.items()})


def render_html_email(title: str, content: str) -> str:
    return render_template(
        "base.html",
        {
            "title": escape(title),
            "brand_name": escape(BRAND_NAME),
            "logo_cid": LOGO_CID,
            "content": content,
        },
    )
