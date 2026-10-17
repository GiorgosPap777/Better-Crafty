import sqlite3

from peewee import SqliteDatabase

from app.classes.models.management import Backups, HelpersManagement


def test_backup_list_does_not_block_later_writes(tmp_path) -> None:
    """The backup edit page keeps the backup list in its template data without
    reading it. When that list was a lazy cursor it held an old read snapshot,
    so once another thread wrote, every write from the web thread failed with
    "database is locked"."""
    path = tmp_path / "crafty.sqlite"
    db = SqliteDatabase(path, pragmas={"journal_mode": "wal"})
    with db.bind_ctx(
        [Backups], bind_refs=False, bind_backrefs=False
    ), db.connection_context():
        db.create_tables([Backups])
        for name in ("first", "second"):
            Backups.insert(backup_name=name, server_id="server-1").execute()

        # Kept, like the page data, and never read
        backups = HelpersManagement.get_backups_by_server("server-1", model=True)

        # Another thread (for example the stats task) writes meanwhile
        other = sqlite3.connect(path)
        other.execute("UPDATE backups SET max_backups = 3")
        other.commit()
        other.close()

        Backups.update(backup_name="renamed").where(
            Backups.backup_name == "first"
        ).execute()

        assert sorted(backup.backup_name for backup in backups) == [
            "first",
            "second",
        ]
