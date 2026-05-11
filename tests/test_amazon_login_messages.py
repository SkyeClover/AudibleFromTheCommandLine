from bs4 import BeautifulSoup

from audctl.amazon_login import collect_auth_error_message


def test_collect_auth_error_message() -> None:
    html = """
    <div id="auth-error-message-box">
      <h4>There was a problem</h4>
      <ul><li><span>Your password is incorrect</span></li></ul>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    msg = collect_auth_error_message(soup)
    assert msg is not None
    assert "incorrect" in msg.lower()
