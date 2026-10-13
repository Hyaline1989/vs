"""Compare two read-only audit JSON snapshots by actual effective permissions."""
import argparse
import json
from pathlib import Path


def compare(before, after):
    differences = []
    if before['object_count'] != after['object_count']:
        differences.append(f"Число объектов изменилось: {before['object_count']} → {after['object_count']}")
    old = {user['id']: user for user in before['users']}
    new = {user['id']: user for user in after['users']}
    for uid in sorted(old.keys() | new.keys()):
        if uid not in old:
            differences.append(f'Добавлен пользователь ID {uid}')
        elif uid not in new:
            differences.append(f'Пропал пользователь ID {uid}')
        elif old[uid]['fingerprint'] != new[uid]['fingerprint']:
            changes = []
            for key in ('role', 'active'):
                if old[uid][key] != new[uid][key]:
                    changes.append(f"{key}: {old[uid][key]} → {new[uid][key]}")
            for name, allowed in old[uid]['modules'].items():
                latest = new[uid]['modules'].get(name)
                if allowed != latest:
                    changes.append(f'{name}: {allowed} → {latest}')
            for oid, permissions in old[uid]['objects'].items():
                latest = new[uid]['objects'].get(oid)
                if permissions != latest:
                    changes.append(f'объект ID {oid}: {permissions} → {latest}')
            differences.append(f"ID {uid} ({old[uid]['name']}): " + '; '.join(changes))
    return differences


def main():
    parser = argparse.ArgumentParser(description='Сравнить действующие права пользователей до и после обновления')
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding='utf-8'))
    after = json.loads(args.after.read_text(encoding='utf-8'))
    differences = compare(before, after)
    if differences:
        print(f'ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ: {len(differences)}')
        for item in differences:
            print(item)
        raise SystemExit(1)
    print(f"Права совпадают: {len(after['users'])} пользователей, {after['object_count']} объектов.")


if __name__ == '__main__':
    main()
