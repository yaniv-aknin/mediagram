from html.parser import HTMLParser


class TelegramHTMLConverter(HTMLParser):
    """Convert standard HTML to Telegram-compatible HTML."""

    SUPPORTED_TAGS = {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "code",
        "pre",
        "a",
        "blockquote",
        "tg-spoiler",
    }

    def __init__(self):
        super().__init__()
        self.result = []
        self.in_list = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SUPPORTED_TAGS:
            # Keep supported tags as-is
            attrs_str = "".join(f' {k}="{v}"' for k, v in attrs)
            self.result.append(f"<{tag}{attrs_str}>")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            # Convert headings to bold
            self.result.append("<b>")
        elif tag == "li":
            # Convert list items to bullets
            self.result.append("• ")
        elif tag in ("ul", "ol"):
            self.in_list = True
        # All other tags are stripped (content is kept via handle_data)

    def handle_endtag(self, tag):
        if tag in self.SUPPORTED_TAGS:
            self.result.append(f"</{tag}>")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("</b>\n")
        elif tag == "li":
            self.result.append("\n")
        elif tag in ("ul", "ol"):
            self.in_list = False
        elif tag == "p":
            # Paragraph breaks become newlines
            self.result.append("\n\n")
        elif tag == "hr":
            self.result.append("―――――\n")

    def handle_data(self, data):
        self.result.append(data)

    def get_result(self) -> str:
        text = "".join(self.result)
        # Clean up excessive newlines
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip()


def convert_to_telegram_html(html: str) -> str:
    """Convert standard HTML to Telegram-compatible HTML."""
    converter = TelegramHTMLConverter()
    converter.feed(html)
    return converter.get_result()
