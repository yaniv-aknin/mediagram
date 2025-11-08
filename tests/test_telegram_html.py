import pytest
from mediagram.driver.telegram.html import convert_to_telegram_html


def test_convert_comprehensive_html():
    """Test HTML conversion with all major features in one go."""
    html = """
    <h1>Title</h1>
    <p>This is <strong>bold</strong> and <em>italic</em> text with <code>code</code>.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    <p>A <a href="https://example.com">link</a> and <div>unsupported tag</div>.</p>
    <blockquote>A quote</blockquote>
    """
    result = convert_to_telegram_html(html)

    assert "<b>Title</b>" in result
    assert "<strong>bold</strong>" in result
    assert "<em>italic</em>" in result
    assert "<code>code</code>" in result
    assert "• Item 1" in result
    assert "• Item 2" in result
    assert '<a href="https://example.com">link</a>' in result
    assert "unsupported tag" in result  # content preserved
    assert "<div>" not in result  # tag stripped
    assert "<blockquote>A quote</blockquote>" in result
    assert "\n\n\n" not in result  # excessive newlines cleaned


def test_excessive_newline_cleanup():
    """Verify that multiple consecutive newlines are reduced to double."""
    html = "<p>A</p><p></p><p></p><p></p><p>B</p>"
    result = convert_to_telegram_html(html)
    assert "\n\n\n" not in result


def test_empty_and_plain_text():
    """Empty input and plain text should work correctly."""
    assert convert_to_telegram_html("") == ""
    assert convert_to_telegram_html("plain text") == "plain text"
