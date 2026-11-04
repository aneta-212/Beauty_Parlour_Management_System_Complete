import json,sqlite3,tempfile,zipfile,shutil,os
from pathlib import Path
from django.conf import settings
from django.utils import timezone


def create_backup(destination=None):
    if settings.DATABASES['default']['ENGINE']!='django.db.backends.sqlite3':raise ValueError('This backup utility supports SQLite only.')
    if destination is None:
        fd,name=tempfile.mkstemp(suffix='.zip');os.close(fd);destination=Path(name)
    destination=Path(destination)
    with tempfile.TemporaryDirectory() as directory:
        snapshot=Path(directory)/'db.sqlite3'
        with sqlite3.connect(str(settings.DATABASES['default']['NAME'])) as source,sqlite3.connect(snapshot) as target:source.backup(target)
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot,'db.sqlite3')
            archive.writestr('manifest.json',json.dumps({'format':'beauty-parlour-backup-v1','created':timezone.now().isoformat()}))
            media=Path(settings.MEDIA_ROOT)
            if media.exists():
                for file in media.rglob('*'):
                    if file.is_file() and not file.is_symlink():archive.write(file,'media/'+file.relative_to(media).as_posix())
    return destination


def restore_backup(source):
    # Caller must stop the application and explicitly confirm the restore.
    from django.db import connections
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        with zipfile.ZipFile(source) as archive:
            if sum(x.file_size for x in archive.infolist())>1024**3:raise ValueError('Backup exceeds the 1 GiB restore limit.')
            if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Duplicate archive paths.')
            for info in archive.infolist():
                name=info.filename
                parts=Path(name).parts
                if '\\' in name or Path(name).is_absolute() or '..' in parts or (name not in ['manifest.json','db.sqlite3'] and not name.startswith('media/')):
                    raise ValueError('Unexpected archive path.')
                if name.endswith('/'):continue
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
        if json.loads((root/'manifest.json').read_text()).get('format')!='beauty-parlour-backup-v1':raise ValueError('Unsupported backup format.')
        with sqlite3.connect(root/'db.sqlite3') as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup database failed integrity check.')
            tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'django_migrations','auth_user','salon_appointment'}.issubset(tables):raise ValueError('Not a compatible project database.')
        backup_dir=Path(settings.BASE_DIR)/'backups';backup_dir.mkdir(exist_ok=True)
        recovery=create_backup(backup_dir/('before_restore_'+timezone.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip'))
        connections.close_all()
        database=Path(settings.DATABASES['default']['NAME'])
        temporary=database.with_suffix('.restore-tmp')
        shutil.copy2(root/'db.sqlite3',temporary);os.replace(temporary,database)
        media=Path(settings.MEDIA_ROOT)
        # Replace media from the snapshot; the pre-restore archive preserves old files.
        if media.exists():shutil.rmtree(media)
        if (root/'media').exists():shutil.copytree(root/'media',media)
        else:media.mkdir(parents=True)
    return recovery
