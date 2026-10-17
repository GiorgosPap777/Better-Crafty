import json
import logging
from datetime import datetime

from peewee import CharField, DateTimeField, TextField

from app.classes.helpers.helpers import Helpers
from app.classes.models.base_model import BaseModel
from app.classes.models.management import Backups

logger = logging.getLogger(__name__)


class OffsiteTargets(BaseModel):
    """A place to copy backups to: a folder or S3-compatible storage"""

    target_id = CharField(primary_key=True, default=Helpers.create_uuid)
    name = CharField(default="Off-site storage")
    kind = CharField(default="folder")
    # JSON; the secret key of S3 storage never goes to the browser
    settings = TextField(default="{}")
    created = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "offsite_targets"


def _as_dict(row: OffsiteTargets) -> dict:
    try:
        settings = json.loads(row.settings)
    except ValueError:
        settings = {}
    return {
        "target_id": row.target_id,
        "name": row.name,
        "kind": row.kind,
        "settings": settings if isinstance(settings, dict) else {},
    }


class HelperOffsite:
    @staticmethod
    def get_all() -> list:
        return [
            _as_dict(row)
            for row in OffsiteTargets.select().order_by(OffsiteTargets.created)
        ]

    @staticmethod
    def get(target_id: str) -> dict | None:
        row = OffsiteTargets.get_or_none(OffsiteTargets.target_id == target_id)
        return _as_dict(row) if row else None

    @staticmethod
    def add(name: str, kind: str, settings: dict) -> str:
        row = OffsiteTargets.create(name=name, kind=kind, settings=json.dumps(settings))
        return row.target_id

    @staticmethod
    def update(target_id: str, name: str, kind: str, settings: dict) -> None:
        OffsiteTargets.update(
            name=name, kind=kind, settings=json.dumps(settings)
        ).where(OffsiteTargets.target_id == target_id).execute()

    @staticmethod
    def delete(target_id: str) -> int:
        """Remove the place; backups that copied there stop copying.
        Returns how many backups did."""
        stopped = (
            Backups.update(offsite_id="", offsite_status="")
            .where(Backups.offsite_id == target_id)
            .execute()
        )
        OffsiteTargets.delete().where(OffsiteTargets.target_id == target_id).execute()
        return stopped

    @staticmethod
    def used_by(target_id: str) -> int:
        return Backups.select().where(Backups.offsite_id == target_id).count()
