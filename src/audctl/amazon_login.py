"""
Amazon / Audible device OAuth login.

Derived from ``audible.login.login`` (mkb79/audible, MIT) with:
  - Clear errors when the sign-in page reports a bad password or similar.
  - CVF (SMS/email code) flow: submit the CVF page *first* so Amazon can send
    the code, then prompt — the upstream library asked for the code *before*
    that first POST.
  - Optional ``[r]`` resend by following common resend links/forms on the CVF page.

The patch is applied only around ``Authenticator.from_login`` (see ``auth_setup``).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import urljoin

import httpx
import typer
from bs4 import BeautifulSoup, Tag

from audible.login import (
    USER_AGENT,
    build_init_cookies,
    build_oauth_url,
    check_for_approval_alert,
    check_for_captcha,
    check_for_choice_mfa,
    check_for_cvf,
    check_for_mfa,
    create_code_verifier,
    default_approval_alert_callback,
    default_captcha_callback,
    default_cvf_callback,
    default_otp_callback,
    extract_captcha_url,
    extract_code_from_url,
    get_inputs_from_soup,
    get_next_action_from_soup,
    get_soup,
    is_valid_email,
    logger,
)
from audible.metadata import encrypt_metadata, meta_audible_app

import audible.auth as audible_auth_module
import audible.login as audible_login_module

_ORIGINAL_LOGIN = audible_login_module.login
_ORIGINAL_AUTH_LOGIN = audible_auth_module.login


class AudctlLoginError(Exception):
    """User-facing login failure (wrong password, cancelled CVF, etc.)."""


def _flatten_auth_box(box: Tag) -> str:
    parts: list[str] = []
    h = box.find("h4")
    if isinstance(h, Tag) and h.string:
        parts.append(h.string.strip())
    for li in box.find_all("li"):
        if not isinstance(li, Tag):
            continue
        sp = li.find("span")
        if isinstance(sp, Tag) and sp.string:
            parts.append(sp.string.strip())
    return " ".join(parts).strip()


def collect_auth_error_message(soup: BeautifulSoup) -> str | None:
    """Return text from the red auth error box, if present."""
    box = soup.find(id="auth-error-message-box")
    if isinstance(box, Tag):
        msg = _flatten_auth_box(box)
        if msg:
            return msg
    ap = soup.find(id="ap_error_page_message")
    if isinstance(ap, Tag):
        raw = ap.find(string=True)
        if raw:
            t = str(raw).strip()
            if t:
                return t
    return None


def _maybe_raise_sign_in_error(login_soup: BeautifulSoup) -> None:
    """If Amazon shows a hard error on the sign-in page (e.g. wrong password)."""
    if (
        check_for_captcha(login_soup)
        or check_for_mfa(login_soup)
        or check_for_choice_mfa(login_soup)
        or check_for_cvf(login_soup)
    ):
        return
    err = collect_auth_error_message(login_soup)
    if err:
        raise AudctlLoginError(err)


def _cvf_try_resend(session: httpx.Client, soup: BeautifulSoup) -> bool:
    """Best-effort: click/post a resend control on the CVF page."""
    root = soup.find(id="cvf-page-content")
    if not isinstance(root, Tag):
        return False

    for a in root.find_all("a", href=True):
        href = str(a.get("href", ""))
        text = (a.get_text() or "").lower()
        if "resend" in href.lower() or "resend" in text or "send another" in text:
            try:
                session.request("GET", href)
                return True
            except httpx.HTTPError:
                continue

    for form in root.find_all("form"):
        submit_name: str | None = None
        submit_val: str | None = None
        for inp in form.find_all("input"):
            if inp.get("type") != "submit":
                continue
            val = (inp.get("value") or "").lower()
            if "resend" in val or ("send" in val and "again" in val):
                submit_name = inp.get("name")
                submit_val = inp.get("value")
                break
        if not submit_name:
            continue
        try:
            data: dict[str, str] = {}
            for field in form.find_all("input"):
                try:
                    name = field["name"]
                    if field.get("type") == "hidden":
                        data[name] = str(field.get("value", ""))
                except Exception:  # noqa: BLE001
                    continue
            data[submit_name] = str(submit_val or "")
            method = (form.get("method") or "POST").upper()
            action = form.get("action") or ""
            target = urljoin(str(session.base_url), str(action))
            session.request(method, target, data=data)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _cvf_interactive_loop(
    session: httpx.Client,
    login_soup: BeautifulSoup,
    login_resp: httpx.Response,
    *,
    cvf_callback: Optional[Callable[[], str]],
    default_cvf: Callable[[], str],
) -> tuple[httpx.Response, BeautifulSoup]:
    """
    Submit CVF page once, then loop: menu (code / resend / abort) + submit code.
    """
    typer.echo(
        "\n".join(
            [
                "",
                "── Amazon sign-in verification (CVF) ──",
                "A code is often sent only *after* the first step. If nothing arrived, wait 1–2 minutes,",
                "check spam, or choose [r] to try a resend when Amazon shows that option.",
                "",
            ]
        )
    )

    inputs = get_inputs_from_soup(login_soup)
    method, url = get_next_action_from_soup(login_soup)
    login_resp = session.request(method, url, data=inputs)
    login_soup = get_soup(login_resp)

    while check_for_cvf(login_soup):
        err = collect_auth_error_message(login_soup)
        if err:
            typer.echo(f"Note from Amazon: {err}")
        choice = typer.prompt(
            "[c] Enter verification code   [r] Try resend   [a] Abort",
            default="c",
        ).strip().lower()
        if choice == "a":
            session.close()
            raise AudctlLoginError("Login cancelled at the verification-code step.")
        if choice == "r":
            if _cvf_try_resend(session, login_soup):
                typer.echo("Resend request submitted (best effort). Wait, then choose [c] and enter the new code.")
            else:
                typer.echo(
                    "No resend control found on this page. Open https://www.amazon.com in a browser, "
                    "or verify your marketplace (-m) matches your account."
                )
            try:
                login_resp = session.get(str(login_resp.url))
                login_soup = get_soup(login_resp)
            except httpx.HTTPError as exc:
                typer.echo(f"Refresh failed: {exc}", err=True)
            continue

        if cvf_callback:
            cvf_code = cvf_callback()
        else:
            cvf_code = default_cvf()
        cvf_code = (cvf_code or "").strip()
        if not cvf_code:
            typer.echo("Empty code — try again or choose [r] / [a].", err=True)
            continue

        inputs = get_inputs_from_soup(login_soup)
        inputs["action"] = "code"
        inputs["code"] = cvf_code
        method, url = get_next_action_from_soup(login_soup)
        login_resp = session.request(method, url, data=inputs)
        login_soup = get_soup(login_resp)

    return login_resp, login_soup


def device_login(
    username: str,
    password: str,
    country_code: str,
    domain: str,
    market_place_id: str,
    serial: Optional[str] = None,
    with_username: bool = False,
    captcha_callback: Optional[Callable[[str], str]] = None,
    otp_callback: Optional[Callable[[], str]] = None,
    cvf_callback: Optional[Callable[[], str]] = None,
    approval_callback: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    """Same contract as ``audible.login.login`` with improved CVF and errors."""

    if with_username:
        base_url = f"https://www.audible.{domain}"
        logger.info("Login with Audible username.")
    else:
        if not is_valid_email(username):
            logger.warning("Username %s is not a valid mail address.", username)
        base_url = f"https://www.amazon.{domain}"
        logger.info("Login with Amazon Account.")

    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US",
        "Accept-Encoding": "gzip",
    }
    init_cookies = build_init_cookies()

    session = httpx.Client(
        base_url=base_url,
        headers=default_headers,
        cookies=init_cookies,
        follow_redirects=True,
    )
    code_verifier = create_code_verifier()

    oauth_url, serial = build_oauth_url(
        country_code=country_code,
        domain=domain,
        market_place_id=market_place_id,
        code_verifier=code_verifier,
        serial=serial,
        with_username=with_username,
    )

    oauth_resp = session.get(oauth_url)
    oauth_soup = get_soup(oauth_resp)

    login_inputs = get_inputs_from_soup(oauth_soup)
    login_inputs["email"] = username
    login_inputs["password"] = password

    metadata = meta_audible_app(USER_AGENT, base_url)
    login_inputs["metadata1"] = encrypt_metadata(metadata)

    method, url = get_next_action_from_soup(oauth_soup, {"name": "signIn"})

    login_resp = session.request(method, url, data=login_inputs)
    login_soup = get_soup(login_resp)

    if b"openid.oa2.authorization_code" in login_resp.url.query:
        session.close()
        return {
            "authorization_code": extract_code_from_url(login_resp.url),
            "code_verifier": code_verifier,
            "domain": domain,
            "serial": serial,
        }

    _maybe_raise_sign_in_error(login_soup)

    while check_for_captcha(login_soup):
        captcha_url = extract_captcha_url(login_soup)
        if captcha_callback:
            guess = captcha_callback(captcha_url)
        else:
            guess = default_captcha_callback(captcha_url)

        inputs = get_inputs_from_soup(login_soup)
        inputs["guess"] = guess
        inputs["use_image_captcha"] = "true"
        inputs["use_audio_captcha"] = "false"
        inputs["showPasswordChecked"] = "false"
        inputs["email"] = username
        inputs["password"] = password

        method, url = get_next_action_from_soup(login_soup, {"name": "signIn"})

        login_resp = session.request(method, url, data=inputs)
        login_soup = get_soup(login_resp)
        _maybe_raise_sign_in_error(login_soup)

    while check_for_choice_mfa(login_soup):
        inputs = get_inputs_from_soup(login_soup)
        for node in login_soup.select("div[data-a-input-name=otpDeviceContext]"):
            classes = node.get("class") or []
            if not isinstance(classes, list):
                classes = list(classes) if classes else []
            if "auth-TOTP" in classes:
                inp_node = node.find("input")
                if inp_node and inp_node.get("name"):
                    inputs[inp_node["name"]] = inp_node.get("value", "")

        method, url = get_next_action_from_soup(login_soup)

        login_resp = session.request(method, url, data=inputs)
        login_soup = get_soup(login_resp)

    while check_for_mfa(login_soup):
        if otp_callback:
            otp_code = otp_callback()
        else:
            otp_code = default_otp_callback()

        inputs = get_inputs_from_soup(login_soup)
        inputs["otpCode"] = otp_code
        inputs["mfaSubmit"] = "Submit"
        inputs["rememberDevice"] = "false"

        method, url = get_next_action_from_soup(login_soup)

        login_resp = session.request(method, url, data=inputs)
        login_soup = get_soup(login_resp)
        err = collect_auth_error_message(login_soup)
        if err and check_for_mfa(login_soup):
            raise AudctlLoginError(f"Authenticator code not accepted: {err}")

    while check_for_cvf(login_soup):
        login_resp, login_soup = _cvf_interactive_loop(
            session,
            login_soup,
            login_resp,
            cvf_callback=cvf_callback,
            default_cvf=default_cvf_callback,
        )

    while check_for_approval_alert(login_soup):
        if approval_callback:
            approval_callback()
        else:
            default_approval_alert_callback()

        url = login_resp.url

        login_resp = session.get(url)
        login_soup = get_soup(login_resp)

        while login_soup.find("span", {"class": "transaction-approval-word-break"}):
            login_resp = session.get(url)
            login_soup = get_soup(login_resp)
            logger.info("still waiting for redirect")

    session.close()

    if b"openid.oa2.authorization_code" not in login_resp.url.query:
        tail = collect_auth_error_message(BeautifulSoup(login_resp.text, "html.parser"))
        hint = f" {tail}" if tail else ""
        raise AudctlLoginError(
            "Login did not complete (no authorization code in redirect). "
            "Check email/SMS, marketplace (-m), or try again in a browser." + hint
        )

    logger.debug("Login confirmed for %s", username)

    authorization_code = extract_code_from_url(login_resp.url)

    return {
        "authorization_code": authorization_code,
        "code_verifier": code_verifier,
        "domain": domain,
        "serial": serial,
    }


def apply_device_login_patch() -> None:
    """``audible.auth`` keeps its own reference to ``login``; patch both modules."""
    audible_login_module.login = device_login
    audible_auth_module.login = device_login


def restore_device_login_patch() -> None:
    audible_login_module.login = _ORIGINAL_LOGIN
    audible_auth_module.login = _ORIGINAL_AUTH_LOGIN
