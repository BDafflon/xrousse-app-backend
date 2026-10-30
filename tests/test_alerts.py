from app.models.event import Event, EventStatus
from app.models.subscription import AlertMode, Subscription
from app.models.tag import Tag
from app.models.user import Role, User
from app.services.alerts import send_digest_for_day, trigger_immediate_alerts


def _make_user(session, email="lecteur@test.com"):
    user = User(email=email, password_hash="irrelevant", role=Role.lecteur)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_tag(session):
    from sqlmodel import select

    return session.exec(select(Tag)).first()


def _make_published_event_with_tag(session, tag, created_by_id):
    event = Event(
        titre="Vide grenier",
        description="desc",
        source_url="https://example.com/digest-event",
        statut=EventStatus.publie,
        created_by_id=created_by_id,
        tags=[tag],
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def create_subscription(session, user, tag, mode, resume_day=None):
    sub = Subscription(
        user_id=user.id,
        tag_id=tag.id,
        mode=AlertMode(mode),
        resume_day=resume_day,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def test_trigger_immediate_alerts_sends_email_to_matching_subscribers(
    session, monkeypatch
):
    sent = []
    monkeypatch.setattr(
        "app.services.alerts.send_email", lambda to, subject, html: sent.append(to)
    )

    lecteur_user = _make_user(session)
    tag = _make_tag(session)
    published_event_with_tag = _make_published_event_with_tag(
        session, tag, lecteur_user.id
    )
    create_subscription(session, user=lecteur_user, tag=tag, mode="immediat")

    trigger_immediate_alerts(published_event_with_tag, session)

    assert lecteur_user.email in sent


def test_trigger_immediate_alerts_skips_non_matching_tags(session, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.alerts.send_email", lambda to, subject, html: sent.append(to)
    )

    lecteur_user = _make_user(session)
    from sqlmodel import select

    tags = session.exec(select(Tag)).all()
    subscribed_tag, event_tag = tags[0], tags[1]
    published_event_with_tag = _make_published_event_with_tag(
        session, event_tag, lecteur_user.id
    )
    create_subscription(session, user=lecteur_user, tag=subscribed_tag, mode="immediat")

    trigger_immediate_alerts(published_event_with_tag, session)

    assert sent == []


def test_trigger_immediate_alerts_skips_resume_subscriptions(session, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.alerts.send_email", lambda to, subject, html: sent.append(to)
    )

    lecteur_user = _make_user(session)
    tag = _make_tag(session)
    published_event_with_tag = _make_published_event_with_tag(
        session, tag, lecteur_user.id
    )
    create_subscription(session, user=lecteur_user, tag=tag, mode="resume", resume_day=0)

    trigger_immediate_alerts(published_event_with_tag, session)

    assert sent == []


def test_send_digest_for_day_sends_one_email_per_user(session, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.alerts.send_email",
        lambda to, subject, html: sent.append((to, subject, html)),
    )

    lecteur_user = _make_user(session)
    tag = _make_tag(session)
    _make_published_event_with_tag(session, tag, lecteur_user.id)
    create_subscription(session, user=lecteur_user, tag=tag, mode="resume", resume_day=0)

    send_digest_for_day(0, session)

    assert len(sent) == 1
    assert sent[0][0] == lecteur_user.email


def test_send_digest_for_day_skips_other_days(session, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.alerts.send_email", lambda to, subject, html: sent.append(to)
    )

    lecteur_user = _make_user(session)
    tag = _make_tag(session)
    _make_published_event_with_tag(session, tag, lecteur_user.id)
    create_subscription(session, user=lecteur_user, tag=tag, mode="resume", resume_day=1)

    send_digest_for_day(0, session)

    assert sent == []


def test_send_email_failure_does_not_raise(monkeypatch):
    from app.services.email import send_email

    def boom(*args, **kwargs):
        raise Exception("Resend down")

    monkeypatch.setattr("httpx.post", boom)
    send_email("a@b.com", "subj", "<p>hi</p>")  # must not raise


def test_send_email_non_2xx_does_not_raise(monkeypatch):
    from app.services.email import send_email

    class FakeResponse:
        status_code = 500
        text = "server error"

        def raise_for_status(self):
            import httpx

            raise httpx.HTTPStatusError(
                "error", request=None, response=self
            )

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: FakeResponse())
    send_email("a@b.com", "subj", "<p>hi</p>")  # must not raise
