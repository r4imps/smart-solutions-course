"""Rendered HTML contract and form behavior; no browser or hardware required."""

from html.parser import HTMLParser
import json
import re

from flask import render_template
import pytest


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []
        self.feed(html)
        assert not self.stack, "Unclosed HTML elements"

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": "", "parents": tuple(self.stack)}
        self.elements.append(node)
        if tag not in {"meta", "input", "br", "hr", "link", "img", "col"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1]["tag"] == tag, "Mismatched HTML tag: " + tag
        self.stack.pop()

    def handle_data(self, text):
        for node in self.stack:
            node["text"] += text

    def tagged(self, tag):
        return [node for node in self.elements if node["tag"] == tag]


def test_page_has_labeled_unchanged_form_contract(client, user_headers):
    page = Page(client.get("/", headers=user_headers).get_data(as_text=True))
    form, = page.tagged("form")
    assert form["attrs"]["method"] == "post"
    assert form["attrs"]["action"] == "/jobs"
    fields = [node for node in page.tagged("input") + page.tagged("select")
              if form in node["parents"]]
    assert {node["attrs"]["name"] for node in fields} == {
        "job", "letter", "routine", "ttl_seconds"
    }
    for node in fields:
        assert any(label["attrs"].get("for") == node["attrs"]["id"]
                   for label in page.tagged("label"))
        assert form in node["parents"]
    assert [node["attrs"]["value"] for node in page.tagged("option")
            if form in node["parents"]] == [
        "letter", "pick_place", "source_to_finished"
    ]
    ttl, = [node for node in fields if node["attrs"]["name"] == "ttl_seconds"]
    assert ttl["attrs"]["value"] == "60"
    assert "required" in ttl["attrs"]
    letter, = [node for node in fields if node["attrs"]["name"] == "letter"]
    assert "required" not in letter["attrs"]  # Pick-place needs no letter.
    # Both fields remain usable when JavaScript is disabled.
    for node in fields:
        assert "disabled" not in node["attrs"]
        assert not any("hidden" in parent["attrs"] for parent in node["parents"])
    help_ids = {node["attrs"].get("id") for node in page.elements}
    for node in fields:
        for help_id in node["attrs"].get("aria-describedby", "").split():
            assert help_id in help_ids
    assert "Töid ei ole." in page.tagged("table")[0]["text"]


@pytest.mark.parametrize(
    "job_type,letter,expected",
    [("letter", "b", {"letter": "B"}),
     ("pick_place", "", {"routine": "source_to_finished"})],
)
def test_form_submits_both_job_types_with_all_visible_fields(
    client, user_headers, job_type, letter, expected
):
    response = client.post(
        "/jobs", headers=user_headers,
        data={"job": job_type, "letter": letter,
              "routine": "source_to_finished", "ttl_seconds": "30"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = Page(response.get_data(as_text=True))
    jobs = client.get("/api/jobs", headers=user_headers).get_json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["arg"] == expected
    assert jobs[0]["job"] == job_type
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["id"] in page.tagged("table")[0]["text"]


def test_invalid_form_still_shows_error_and_does_not_create_job(client, user_headers):
    response = client.post(
        "/jobs", headers=user_headers,
        data={"job": "letter", "letter": "!", "ttl_seconds": "60"},
        follow_redirects=True,
    )
    page = Page(response.get_data(as_text=True))
    assert any(node["attrs"].get("role") == "alert" and node["text"]
               for node in page.tagged("p"))
    assert client.get("/api/jobs", headers=user_headers).get_json()["jobs"] == []


def test_render_preserves_full_values_and_escapes_untrusted_content(app):
    hostile = '<script>alert("test")</script><img src=x onerror=alert(1)>'
    job = {
        "id": "long-job-id-" * 20 + hostile,
        "job": "letter", "arg": {"letter": hostile}, "status": "refused",
        "created_at": "2030-01-01T12:00:00.123456Z",
        "result": {"detail": hostile}, "reason": hostile,
    }
    with app.test_request_context():
        page = Page(render_template(
            "index.html", jobs=[job], default_ttl=60, error=hostile,
            atom={"status": "offline", "last_seen": "2030-01-01T11:59:00Z"},
        ))
    assert not page.tagged("img")
    scripts = page.tagged("script")
    assert {script["attrs"].get("id") for script in scripts} == {
        "theme-init", "theme-control", "job-fields", "ui-i18n"
    }
    assert all(hostile not in script["text"] and "src" not in script["attrs"]
               for script in scripts)
    codes = [node["text"] for node in page.tagged("code")]
    assert job["id"] in codes
    assert "2030-01-01T11:59:00Z" in codes
    assert page.tagged("time")[0]["text"] == job["created_at"]
    assert page.tagged("time")[0]["attrs"]["datetime"] == job["created_at"]
    for value in (job["arg"], job["result"], job["reason"]):
        assert any(json.loads(code) == value for code in codes if code.startswith(('"', '{')))
    assert len(page.tagged("td")) == 6
    assert all(node["attrs"].get("scope") == "col" for node in page.tagged("th"))
    assert len(page.tagged("th")) == 6
    assert any(node["attrs"].get("role") == "alert" and hostile in node["text"]
               for node in page.tagged("p"))


def test_page_and_form_remain_authenticated(client):
    assert client.get("/").status_code == 401
    assert client.post("/jobs", data={"job": "letter", "letter": "A"}).status_code == 401


@pytest.mark.parametrize("path", ["/", "/jobs"])
@pytest.mark.parametrize("authorization", [None, "Basic d3Jvbmc6d3Jvbmc="])
def test_browser_unauthorized_is_friendly_html_without_job_data(
    client, create_letter, user_headers, path, authorization
):
    job_id = create_letter().get_json()["id"]
    headers = {"Authorization": authorization} if authorization else {}
    response = (client.get(path, headers=headers) if path == "/" else
                client.post(path, headers=headers,
                            data={"job": "letter", "letter": "Z", "ttl_seconds": "60"}))
    assert response.status_code == 401
    assert response.mimetype == "text/html"
    assert response.headers["WWW-Authenticate"] == 'Basic realm="Lab 2 post-office"'
    body = response.get_data(as_text=True)
    page = Page(body)
    for text in (
        "Sisselogimine on vajalik", "Postkontori kasutamiseks tuleb sisse logida.",
        "Kontrolli kasutajanime ja parooli ning proovi uuesti.", "Proovi uuesti",
    ):
        assert text in body
    retry, = page.tagged("a")
    assert retry["attrs"]["href"] == "/"
    assert not page.tagged("form") and not page.tagged("input")
    assert not page.tagged("table") and job_id not in body
    assert "test-user-password" not in body
    assert "test-atom-key" not in body
    jobs = client.get("/api/jobs", headers=user_headers).get_json()["jobs"]
    assert [job["id"] for job in jobs] == [job_id]


@pytest.mark.parametrize("path", ["/api/jobs", "/api/status"])
@pytest.mark.parametrize("authorization,code,message", [
    (None, "user_auth_required", "User authentication is required."),
    ("Basic d3Jvbmc6d3Jvbmc=", "invalid_user_credentials", "Invalid user credentials."),
])
def test_user_api_keeps_json_auth_error(client, path, authorization, code, message):
    headers = {"Authorization": authorization} if authorization else {}
    response = client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.mimetype == "application/json"
    assert response.get_json() == {"error": {"code": code, "message": message}}
    assert response.headers["WWW-Authenticate"] == 'Basic realm="Lab 2 post-office"'


def test_atom_bearer_contract_unchanged(client, atom_headers, valid_poll, user_headers):
    for headers, status, code in [
        ({}, 401, "atom_key_required"),
        (user_headers, 401, "atom_key_required"),
        ({"Authorization": "Bearer wrong"}, 403, "invalid_atom_key"),
    ]:
        response = client.post("/api/atom/poll", headers=headers, json=valid_poll)
        assert response.status_code == status
        assert response.mimetype == "application/json"
        assert response.get_json()["error"]["code"] == code
        assert "WWW-Authenticate" not in response.headers
    assert client.post("/api/atom/poll", headers=atom_headers, json=valid_poll).status_code == 200


@pytest.mark.parametrize("authenticated", [True, False])
def test_theme_control_is_shared_safe_progressive_enhancement(client, user_headers, authenticated):
    page = Page(client.get("/", headers=user_headers if authenticated else {}).get_data(as_text=True))
    toggle, = [node for node in page.tagged("button")
               if node["attrs"].get("id") == "theme-toggle"]
    assert toggle["attrs"]["type"] == "button"
    assert toggle["attrs"]["aria-label"] == "Tume teema"
    assert "aria-pressed" not in toggle["attrs"]  # Action name describes the next theme.
    label, = [node for node in page.tagged("span")
              if node["attrs"].get("class") == "theme-label"]
    assert label["text"] == toggle["attrs"]["aria-label"]
    assert "hidden" in toggle["attrs"]  # No unusable control without JS.
    assert not any(node["tag"] == "form" for node in toggle["parents"])
    scripts = {node["attrs"]["id"]: node for node in page.tagged("script")}
    assert scripts["theme-init"]["parents"][-1]["tag"] == "head"
    assert "localStorage.getItem('lab2-theme')" in scripts["theme-init"]["text"]
    assert "localStorage.setItem('lab2-theme', theme)" in scripts["theme-control"]["text"]
    assert "try {" in scripts["theme-init"]["text"]
    assert "try {" in scripts["theme-control"]["text"]
    control = scripts["theme-control"]["text"]
    assert "isDark() ? 'Hele teema' : 'Tume teema'" in control
    assert "button.querySelector('.theme-label').textContent = label" in control
    assert "button.setAttribute('aria-label', label)" in control
    assert "aria-pressed" not in control
    assert "system.addEventListener('change', update)" in control
    assert "window.addEventListener('lab2:languagechange', update)" in control
    assert "window.Lab2I18n.t(isDark() ? 'theme.light' : 'theme.dark')" in control
    assert all("fetch(" not in node["text"] and "XMLHttpRequest" not in node["text"]
               for node in scripts.values())
    style = page.tagged("style")[0]["text"]
    assert "prefers-color-scheme: dark" in style
    assert ":focus-visible" in style


def _contrast(a, b):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                  for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + .05) / (darker + .05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_tokens_meet_wcag_aa_contrast(client, user_headers, theme):
    style = Page(client.get("/", headers=user_headers).get_data(as_text=True)).tagged("style")[0]["text"]
    selector = ":root {" if theme == "light" else ':root[data-theme="dark"] {'
    block = style.split(selector, 1)[1].split("}", 1)[0]
    tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))
    text_pairs = [(text, bg) for text in ("ink", "muted", "accent")
                  for bg in ("page", "panel", "subtle", "hover", "input")]
    text_pairs += [("button-text", bg) for bg in ("button", "button-hover")]
    text_pairs += [(tone + "-ink", tone + "-bg")
                   for tone in ("success", "waiting", "claimed", "danger", "neutral")]
    for foreground, background in text_pairs:
        assert _contrast(tokens[foreground], tokens[background]) >= 4.5, (theme, foreground, background)
    for foreground in ("input-border", "focus"):
        for background in ("input", "panel", "page"):
            assert _contrast(tokens[foreground], tokens[background]) >= 3, (theme, foreground, background)


@pytest.mark.parametrize("state,label", [
    ("queued", "Ootel"), ("claimed", "Vastu võetud"), ("done", "Lõpetatud"),
    ("refused", "Keeldutud"), ("expired", "Aegunud"),
])
def test_job_status_has_readable_text_as_well_as_machine_value(app, state, label):
    with app.test_request_context():
        page = Page(render_template(
            "index.html", default_ttl=60, error=None,
            atom={"status": "offline", "last_seen": None},
            jobs=[{"id": "ui-test", "job": "letter", "arg": {"letter": "A"},
                   "status": state, "created_at": "2030-01-01T12:00:00Z",
                   "result": None, "reason": None}],
        ))
    table = page.tagged("table")[0]["text"]
    assert label in table and state in table


@pytest.mark.parametrize("state,expected", [
    ("online", "Roboti töö sõltub jaama kohalikust loast."),
    ("stale", "Töö vastuvõtmine pole kinnitatud."),
    ("offline", "Uus töö jääb järjekorda ja võib enne vastuvõtmist aeguda."),
])
def test_atom_state_explains_execution_limits(app, state, expected):
    with app.test_request_context():
        page = Page(render_template(
            "index.html", jobs=[], default_ttl=60, error=None,
            atom={"status": state, "last_seen": None},
        ))
    assert expected in page.tagged("main")[0]["text"]
    assert "Pole veel ühendunud" in page.tagged("main")[0]["text"]


def test_page_shows_reported_robot_state_and_poll_interval(
    client, user_headers, atom_headers, valid_poll
):
    def meta(item_id):
        page = Page(client.get("/", headers=user_headers).get_data(as_text=True))
        span = next(node for node in page.tagged("span") if node["attrs"].get("id") == item_id)
        return next(node for node in page.tagged("code") if span in node["parents"])

    assert meta("robot-state")["text"] == "Pole teatatud"
    assert meta("poll-interval")["attrs"].get("data-i18n") == "atom.notReported"

    valid_poll["poll_interval_ms"] = 2500
    valid_poll["station"]["robot_state"] = "locally_enabled"
    assert client.post("/api/atom/poll", headers=atom_headers, json=valid_poll).status_code == 200
    # Machine values stay untranslated, like the job states.
    state, interval = meta("robot-state"), meta("poll-interval")
    assert state["text"] == "locally_enabled" and "data-i18n" not in state["attrs"]
    assert interval["text"] == "2500 ms" and "data-i18n" not in interval["attrs"]


def test_ui_loads_no_external_styles_scripts_or_fonts(client, user_headers):
    page = Page(client.get("/", headers=user_headers).get_data(as_text=True))
    assert not page.tagged("link")
    assert all("src" not in node["attrs"] for node in page.tagged("script"))
    assert not any("http://" in node["text"] or "https://" in node["text"]
                   for node in page.tagged("style"))


@pytest.fixture
def translations(client):
    page = Page(client.get("/").get_data(as_text=True))
    source, = [node["text"] for node in page.tagged("script")
               if node["attrs"].get("id") == "ui-i18n"]
    dictionaries = json.loads(re.search(r"const messages = (.*?);\n  const own", source, re.S)[1])
    assert "innerHTML" not in source and "eval(" not in source
    assert "fetch(" not in source and "XMLHttpRequest" not in source
    return dictionaries


@pytest.mark.parametrize("authenticated", [True, False])
def test_language_selector_is_accessible_local_and_outside_job_form(
    client, user_headers, authenticated, translations
):
    page = Page(client.get("/", headers=user_headers if authenticated else {}).get_data(as_text=True))
    selector, = [node for node in page.tagged("select")
                 if node["attrs"].get("id") == "ui-language"]
    assert selector["attrs"]["aria-labelledby"] == "language-label"
    assert "name" not in selector["attrs"]
    assert not any(node["tag"] == "form" for node in selector["parents"])
    control = next(node for node in selector["parents"]
                   if node["attrs"].get("id") == "language-control")
    assert "hidden" in control["attrs"]  # Estonian HTML remains usable without JS.
    options = [node for node in page.tagged("option") if selector in node["parents"]]
    assert [(node["attrs"]["value"], node["attrs"]["lang"], node["text"]) for node in options] == [
        ("et", "et", "ET · Eesti"), ("ru", "ru", "RU · Русский"), ("en", "en", "EN · English")
    ]
    assert page.tagged("html")[0]["attrs"]["lang"] == "et"
    asset, = [node for node in page.tagged("script")
              if node["attrs"].get("id") == "ui-i18n"]
    assert "src" not in asset["attrs"]  # No translation requests, including local assets.
    assert asset["parents"][-1]["tag"] == "body"
    for node in page.elements:
        key = node["attrs"].get("data-i18n")
        if key:
            assert all(key in dictionary for dictionary in translations.values())
            assert node["text"] == translations["et"][key]


def test_translation_dictionaries_are_complete(translations):
    assert set(translations) == {"et", "ru", "en"}
    keys = set(translations["et"])
    assert all(set(dictionary) == keys for dictionary in translations.values())
    assert all(isinstance(text, str) and text.strip()
               for dictionary in translations.values() for text in dictionary.values())
    for state in ("queued", "claimed", "done", "refused", "expired"):
        assert "status." + state in keys
    for state in ("online", "stale", "offline"):
        assert "atom." + state in keys and "atom." + state + "Note" in keys
    assert translations["ru"]["auth.heading"] == "Необходим вход"
    assert translations["en"]["auth.retry"] == "Try again"


@pytest.mark.parametrize("message,key", [
    ("letter must be a string.", "error.letter"),
    ("letter must be exactly one character A-Z.", "error.letter"),
    ("pick_place routine must be 'source_to_finished'.", "error.routine"),
    ("Only the enabled high-level jobs 'letter' and 'pick_place' are accepted.", "error.job"),
    ("TTL must be an integer.", "error.ttlInteger"),
    ("ttl_seconds must be an integer.", "error.ttlInteger"),
    ("ttl_seconds must be between 1 and 3600.", "error.ttlRange"),
])
def test_known_form_errors_have_explicit_localization_and_estonian_fallback(
    client, user_headers, translations, message, key
):
    response = client.get("/", headers=user_headers, query_string={"error": message})
    page = Page(response.get_data(as_text=True))
    error, = [node for node in page.tagged("p") if node["attrs"].get("role") == "alert"]
    label, = [node for node in page.tagged("span") if error in node["parents"]]
    assert label["attrs"]["data-i18n"] == key
    assert label["text"] == translations["et"][key].replace("{max}", "3600")
    assert message not in error["text"]


def test_unknown_error_is_never_treated_as_a_translation_key(client, user_headers):
    hostile = '<img src=x onerror=alert(1)> __proto__ error.letter'
    response = client.get("/", headers=user_headers, query_string={"error": hostile})
    page = Page(response.get_data(as_text=True))
    assert not page.tagged("img")
    error, = [node for node in page.tagged("p") if node["attrs"].get("role") == "alert"]
    assert hostile in error["text"]
    labels = [node["attrs"].get("data-i18n") for node in page.elements if error in node["parents"]]
    assert "error.general" in labels and "error.letter" not in labels
