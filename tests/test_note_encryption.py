import copy
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from Utility.note_encryption import NoteEncryption, NoteConflict


NOTE = 'users/owner/maps/trip/planning/notes'
MAP = 'users/owner/maps/trip'


class Reference:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return Reference(self.db, self.path + '/' + name)

    document = collection

    def get(self, transaction=None):
        value = copy.deepcopy(self.db.documents.get(self.path))
        return SimpleNamespace(exists=value is not None, reference=self,
                               to_dict=lambda: value)


class Transaction:
    def __init__(self, db):
        self.db, self.pending = db, []

    def update(self, ref, data):
        self.pending.append((ref, data))

    def set(self, ref, data, merge=False):
        assert merge
        self.pending.append((ref, data))

    def commit(self):
        for ref, data in self.pending:
            self.db.documents.setdefault(ref.path, {}).update(copy.deepcopy(data))


def transactional(function):
    def run(transaction):
        result = function(transaction)
        transaction.commit()
        return result
    return run


class Database:
    def __init__(self):
        self.documents = {
            MAP: {'collaborators': {'editor': {'role': 'editor'}, 'viewer': {'role': 'viewer'}}},
            NOTE: {'text': '<b>Trip café 🏕️</b><div>Second line</div>', 'unrelated': {'keep': True}},
        }

    def collection(self, name):
        return Reference(self, name)

    def transaction(self):
        return Transaction(self)

    def collection_group(self, name):
        return SimpleNamespace(stream=lambda: [Reference(self, path).get()
                              for path in self.documents if '/' + name + '/' in path])


class EncryptionTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch('Utility.note_encryption.firestore.transactional', transactional)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = Database()
        self.ref = Reference(self.db, NOTE)
        self.key = Fernet.generate_key().decode()
        self.encryption = NoteEncryption(self.key)

    def test_migration_preserves_html_metadata_and_is_idempotent(self):
        original = self.db.documents[NOTE]['text']
        text, revision, migrated = self.encryption.read(self.db, self.ref)
        self.assertTrue(migrated)
        self.assertEqual(text, original)
        self.assertEqual(self.db.documents[NOTE]['unrelated'], {'keep': True})
        self.assertNotIn(original, str(self.db.documents[NOTE]))
        stored = copy.deepcopy(self.db.documents[NOTE])
        self.assertEqual(self.encryption.read(self.db, self.ref), (original, revision, False))
        self.assertEqual(stored, self.db.documents[NOTE])

    def test_wrong_key_and_tampering_cannot_read_or_overwrite(self):
        _, revision, _ = self.encryption.read(self.db, self.ref)
        original = copy.deepcopy(self.db.documents[NOTE])
        wrong = NoteEncryption(Fernet.generate_key().decode())
        for action in (lambda: wrong.read(self.db, self.ref),
                       lambda: wrong.save(self.db, self.ref, '', revision)):
            with self.assertRaises(InvalidToken):
                action()
            self.assertEqual(self.db.documents[NOTE], original)
        token = self.db.documents[NOTE]['text']['token']
        self.db.documents[NOTE]['text']['token'] = token[:40] + ('A' if token[40] != 'A' else 'B') + token[41:]
        with self.assertRaises(InvalidToken):
            self.encryption.read(self.db, self.ref)

    def test_ciphertext_is_bound_to_map(self):
        self.encryption.read(self.db, self.ref)
        other = Reference(self.db, 'users/owner/maps/other/planning/notes')
        self.db.documents[other.path] = copy.deepcopy(self.db.documents[NOTE])
        with self.assertRaises(InvalidToken):
            self.encryption.read(self.db, other)

    def test_stale_edits_are_rejected(self):
        _, revision, _ = self.encryption.read(self.db, self.ref)
        new_revision = self.encryption.save(self.db, self.ref, 'First editor', revision)
        with self.assertRaises(NoteConflict):
            self.encryption.save(self.db, self.ref, 'Stale editor', revision)
        self.assertEqual(self.encryption.read(self.db, self.ref), ('First editor', new_revision, False))

    def test_empty_and_missing_notes(self):
        del self.db.documents[NOTE]
        text, revision, migrated = self.encryption.read(self.db, self.ref)
        self.assertEqual((text, migrated), ('', False))
        self.assertNotIn(NOTE, self.db.documents)
        self.encryption.save(self.db, self.ref, '', revision)
        self.assertEqual(self.encryption.read(self.db, self.ref)[0], '')
        self.db.documents[NOTE]['text'] = ''
        self.assertTrue(self.encryption.read(self.db, self.ref)[2])

    def test_unknown_format_is_preserved(self):
        self.db.documents[NOTE]['text'] = {'format': 'future-version', 'token': 'opaque'}
        stored = copy.deepcopy(self.db.documents[NOTE])
        with self.assertRaises(InvalidToken):
            self.encryption.read(self.db, self.ref)
        self.assertEqual(stored, self.db.documents[NOTE])


class ApiTests(unittest.TestCase):
    def setUp(self):
        EncryptionTests.setUp(self)
        # Existing imports initialize a Maps client; no requests are made.
        self.env = patch.dict(os.environ, {'GOOGLE_MAPS_KEY': 'AIza' + 'x' * 35,
                             'FLASK_SECRET_KEY': 'test-session-secret',
                             'NOTES_ENCRYPTION_KEY': self.key})
        self.env.start()
        self.addCleanup(self.env.stop)
        import app
        self.module = app
        with patch.object(app.firebase_admin, 'get_app'), \
                patch.object(app.fb_firestore, 'client', return_value=self.db):
            self.app = app.create_app()
        self.client = self.app.test_client()
        self.tokens = patch.object(app.fb_auth, 'verify_id_token',
                                   side_effect=lambda token, **kwargs: {'uid': token})
        self.tokens.start()
        self.addCleanup(self.tokens.stop)

    def get_note(self, uid='owner'):
        return self.client.get('/api/notes?owner_id=owner&map_id=trip',
                               headers={'Authorization': 'Bearer ' + uid})

    def save_note(self, uid, text, revision):
        return self.client.post('/api/notes', json={'owner_id': 'owner', 'map_id': 'trip',
                                'text': text, 'revision': revision},
                                headers={'Authorization': 'Bearer ' + uid})

    def test_api_permissions_and_no_cookies(self):
        with self.client.session_transaction() as session:
            session['uid'] = 'owner'
        self.assertEqual(self.client.get('/api/notes?map_id=trip').status_code, 401)
        self.assertEqual(self.get_note('outsider').status_code, 403)
        viewer = self.get_note('viewer')
        self.assertEqual(viewer.status_code, 200)
        self.assertFalse(viewer.json['can_edit'])
        self.assertEqual(viewer.headers['Cache-Control'], 'no-store')
        revision = viewer.json['revision']
        self.assertEqual(self.save_note('viewer', 'bad edit', revision).status_code, 403)
        saved = self.save_note('editor', 'Collaborative edit', revision)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.get_note().json['text'], 'Collaborative edit')
        self.assertEqual(self.save_note('owner', 'stale edit', revision).status_code, 409)

    def test_missing_or_wrong_key_preserves_data(self):
        for key in ('', 'invalid-key'):
            with patch.dict(os.environ, {'NOTES_ENCRYPTION_KEY': key}):
                original = copy.deepcopy(self.db.documents[NOTE])
                self.assertEqual(self.get_note().status_code, 503)
                self.assertEqual(original, self.db.documents[NOTE])
        response = self.get_note()
        original = copy.deepcopy(self.db.documents[NOTE])
        with patch.dict(os.environ, {'NOTES_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            self.assertEqual(self.get_note().status_code, 503)
            self.assertEqual(self.save_note('owner', '', response.json['revision']).status_code, 503)
        self.assertEqual(original, self.db.documents[NOTE])

    def test_invalid_token_and_parameters(self):
        with patch.object(self.module.fb_auth, 'verify_id_token', side_effect=ValueError):
            self.assertEqual(self.get_note().status_code, 401)
        self.assertEqual(self.client.post('/api/notes', json=[],
                         headers={'Authorization': 'Bearer owner'}).status_code, 400)
        self.assertEqual(self.client.get('/api/notes?map_id=a/b',
                         headers={'Authorization': 'Bearer owner'}).status_code, 400)
        revision = self.get_note().json['revision']
        self.assertEqual(self.save_note('owner', 'x' * 500001, revision).status_code, 413)

    def test_bulk_migration_covers_orphans_and_can_rerun(self):
        orphan = 'users/deleted/maps/deleted/planning/notes'
        self.db.documents[orphan] = {'text': 'Keep orphan note'}
        result = self.app.test_cli_runner().invoke(args=['encrypt-notes'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('encrypted 2 legacy notes', result.output)
        self.assertEqual(self.encryption.decrypt(self.db.documents[orphan]['text'], orphan),
                         'Keep orphan note')
        again = self.app.test_cli_runner().invoke(args=['encrypt-notes'])
        self.assertEqual(again.exit_code, 0, again.output)
        self.assertIn('encrypted 0 legacy notes', again.output)

    def test_insecure_session_secret_rejected(self):
        with patch.dict(os.environ, {'FLASK_SECRET_KEY': 'dev-secret'}):
            with self.assertRaises(RuntimeError):
                self.module.create_app()

    def test_bulk_migration_checks_key_before_upgrading_plaintext(self):
        other = 'users/owner/maps/other/planning/notes'
        self.db.documents[other] = {'text': self.encryption.encrypt('Encrypted note', other)}
        original = copy.deepcopy(self.db.documents)
        with patch.dict(os.environ, {'NOTES_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            result = self.app.test_cli_runner().invoke(args=['encrypt-notes'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('No notes were migrated', result.output)
        self.assertEqual(original, self.db.documents)

    def test_generated_map_embeds_notes_code_for_downloads(self):
        import tempfile
        from pathlib import Path
        from Utility.html_edits import insert_sidebar
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'map.html'
            path.write_text('<html><head></head><body>Map</body></html>')
            insert_sidebar(path, 'trip', 'owner', firebase_config={'projectId': 'example'})
            html = path.read_text()
        self.assertIn('function createEncryptedNotes(', html)
        self.assertIn('const notes = createEncryptedNotes({ auth, docRef,', html)
        self.assertNotIn('docRef.set(', html)
        self.assertNotIn('{notes_script}', html)


if __name__ == '__main__':
    unittest.main()
