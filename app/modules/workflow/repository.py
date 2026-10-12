from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.intake import Request, RequestStatus, DesignType
from app.database.models.workflow import (
    EventType,
    RequestEvent,
    RevisionOrigin,
    RevisionRound,
)


class RequestEventRepository:

    @staticmethod
    def ever_submitted_clause():
        """Kondisi SQL 'request ini punya minimal satu peristiwa submit' (V7).
        Berkorelasi ke Request.id, dipakai di WHERE query daftar request."""
        return exists().where(
            RequestEvent.request_id == Request.id,
            RequestEvent.event_type == EventType.submit,
        )

    @staticmethod
    async def has_submit(db: AsyncSession, request_id: str) -> bool:
        stmt = select(
            exists().where(
                RequestEvent.request_id == request_id,
                RequestEvent.event_type == EventType.submit,
            )
        )
        return bool(await db.scalar(stmt))

    @staticmethod
    async def list_events(db: AsyncSession, request_id: str) -> list[RequestEvent]:
        stmt = (
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.occurred_at, RequestEvent.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def list_rounds(db: AsyncSession, request_id: str) -> list[RevisionRound]:
        stmt = (
            select(RevisionRound)
            .where(RevisionRound.request_id == request_id)
            .order_by(RevisionRound.round_number)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_for_update(db: AsyncSession, request_id: str) -> Request | None:
        """Ambil request sambil mengunci barisnya sampai commit.
        Dua aksi bersamaan pada request yang sama dijalankan bergiliran."""
        stmt = select(Request).where(Request.id == request_id).with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def record(
        db: AsyncSession,
        req: Request,
        *,
        actor_id: str,
        event_type: EventType,
        new_status: RequestStatus,
        payload: dict | None = None,
        feedback_note: str | None = None,
        work_scope: DesignType | None = None,
    ) -> tuple[RequestEvent, RevisionRound | None]:
        """Satu transaksi: catat peristiwa, buka putaran Jepang bila feedback,
        perbarui requests.status. Pemanggil wajib sudah mengunci req (get_for_update)."""
        event = RequestEvent(
            request_id=req.id,
            actor_user_id=actor_id,
            event_type=event_type,
            payload=payload,
        )
        db.add(event)

        revision_round = None
        if event_type == EventType.feedback:
            # Nomor putaran berurutan per request, mencakup putaran internal dan Jepang.
            last_number = await db.scalar(
                select(func.max(RevisionRound.round_number))
                .where(RevisionRound.request_id == req.id)
            )
            revision_round = RevisionRound(
                request_id=req.id,
                round_number=(last_number or 0) + 1,
                work_scope=work_scope,
                origin=RevisionOrigin.japan_correction,
                trigger_note=feedback_note,
            )
            db.add(revision_round)

        req.status = new_status
        await db.commit()
        await db.refresh(event)
        if revision_round is not None:
            await db.refresh(revision_round)
        return event, revision_round