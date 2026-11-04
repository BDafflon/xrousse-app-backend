from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user, require_role
from app.db import get_session
from app.models.event import Event, EventStatus
from app.models.event_report import EventReport
from app.models.user import Role, User
from app.schemas.report import ReportIn, ReportOut

router = APIRouter(tags=["reports"])


@router.post("/events/{event_id}/reports", status_code=status.HTTP_204_NO_CONTENT)
def report_event(
    event_id: int,
    data: ReportIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Report a published event to the moderators. Idempotent per member:
    a second report while the first one is still open is a no-op (204)."""
    event = session.get(Event, event_id)
    if event is None or event.statut != EventStatus.publie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    already = session.exec(
        select(EventReport).where(
            EventReport.event_id == event_id,
            EventReport.reporter_id == current_user.id,
            EventReport.resolved == False,  # noqa: E712
        )
    ).first()
    if already is None:
        session.add(
            EventReport(event_id=event_id, reporter_id=current_user.id, reason=data.reason)
        )
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


admin_router = APIRouter(
    prefix="/backoffice/moderation/reports",
    tags=["backoffice-moderation"],
    dependencies=[Depends(require_role(Role.admin))],
)


@admin_router.get("", response_model=list[ReportOut])
def list_reports(
    resolved: bool = False, session: Session = Depends(get_session)
) -> list[ReportOut]:
    """Open reports (default) or handled ones, oldest first."""
    reports = session.exec(
        select(EventReport).where(EventReport.resolved == resolved).order_by(EventReport.id)
    ).all()
    out = []
    for report in reports:
        event = session.get(Event, report.event_id)
        reporter = session.get(User, report.reporter_id)
        out.append(
            ReportOut(
                id=report.id,
                event_id=report.event_id,
                event_titre=event.titre if event else None,
                reporter_email=reporter.email if reporter else "",
                reason=report.reason,
                resolved=report.resolved,
                created_at=report.created_at,
            )
        )
    return out


@admin_router.post("/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
def resolve_report(report_id: int, session: Session = Depends(get_session)) -> Response:
    """Mark a report as handled (the admin acted on the event, or dismissed it)."""
    report = session.get(EventReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report.resolved = True
    session.add(report)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
