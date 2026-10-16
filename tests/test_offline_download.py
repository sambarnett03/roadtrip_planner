import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from Utility.html_edits import insert_offline_bundle, insert_sidebar
from Utility.note_encryption import NoteEncryption
from test_note_encryption import MAP, NOTE, Database, Reference, transactional

PDFS = MAP + '/pdfs'


class StreamingReference(Reference):
    """Adds what the PDF code needs on top of the notes test double: ids and streaming."""

    @property
    def id(self):
        return self.path.rsplit('/', 1)[-1]

    def collection(self, name):
        return StreamingReference(self.db, self.path + '/' + name)

    document = collection

    def get(self, transaction=None):
        doc = super().get(transaction)
        doc.id = self.id
        return doc

    def stream(self):
        prefix = self.path + '/'
        return [StreamingReference(self.db, path).get() for path in sorted(self.db.documents)
                if path.startswith(prefix) and '/' not in path[len(prefix):]]


class StreamingDatabase(Database):
    def collection(self, name):
        return StreamingReference(self, name)


def bundle_from(html):
    start = html.index('window.ROADTRIP_OFFLINE = ') + len('window.ROADTRIP_OFFLINE = ')
    return json.loads(html[start:html.index(';</script>', start)])


class OfflineDownloadTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode()
        patches = [
            patch('Utility.note_encryption.firestore.transactional', transactional),
            # Existing imports initialize a Maps client; no requests are made.
            patch.dict(os.environ, {'GOOGLE_MAPS_KEY': 'AIza' + 'x' * 35,
                                    'FLASK_SECRET_KEY': 'test-session-secret',
                                    'NOTES_ENCRYPTION_KEY': self.key}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.db = StreamingDatabase()
        self.db.documents[NOTE] = {'text': NoteEncryption(self.key).encrypt(
            '<b>Shared plan</b> </script><script>alert(1)</script>', NOTE)}
        self.pdf_bytes = {}
        for pdf_id, visibility, uploader in [('shared-pdf', 'shared', 'editor'),
                                             ('owner-private', 'private', 'owner'),
                                             ('viewer-private', 'private', 'viewer')]:
            data = b'%PDF-1.4 ' + pdf_id.encode() + b' ' + bytes(range(256))
            self.pdf_bytes[pdf_id] = data
            self.db.documents[f'{PDFS}/{pdf_id}'] = {
                'display_name': pdf_id.replace('-', ' ').title(), 'filename': pdf_id + '.pdf',
                'size': len(data), 'num_chunks': 2, 'visibility': visibility, 'uploaded_by': uploader}
            half = len(data) // 2
            self.db.documents[f'{PDFS}/{pdf_id}/chunks/0'] = {'data': data[:half]}
            self.db.documents[f'{PDFS}/{pdf_id}/chunks/1'] = {'data': data[half:]}

        import app
        with patch.object(app.firebase_admin, 'get_app'), \
                patch.object(app.fb_firestore, 'client', return_value=self.db):
            self.app = app.create_app()
        self.client = self.app.test_client()

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.map_path = Path(directory.name) / 'map.html'
        self.map_path.write_text('<html><head></head><body>Map</body></html>')
        insert_sidebar(self.map_path, 'trip', 'owner', firebase_config={'projectId': 'example'})

    def download(self, uid):
        with self.client.session_transaction() as session:
            session.update({'uid': uid, 'current_map_id': 'trip', 'current_map_owner': 'owner',
                            'last_map_path': str(self.map_path)})
        return self.client.get('/download_current_map')

    def test_download_embeds_shared_notes_and_visible_pdfs(self):
        response = self.download('viewer')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        html = response.get_data(as_text=True)
        bundle = bundle_from(html)

        self.assertEqual(bundle['notes'], {'text': '<b>Shared plan</b> </script><script>alert(1)</script>'})
        # The note must not be able to close the embedding <script> tag.
        self.assertNotIn('</script><script>alert(1)', html)
        # Shared PDFs plus only this user's private ones, with their full contents.
        pdfs = {pdf['id']: pdf for pdf in bundle['pdfs']}
        self.assertEqual(set(pdfs), {'shared-pdf', 'viewer-private'})
        for pdf_id, pdf in pdfs.items():
            self.assertEqual(base64.b64decode(pdf['data']), self.pdf_bytes[pdf_id])
            self.assertEqual(pdf['filename'], pdf_id + '.pdf')
        # Downloads stay readable by the sidebar code.
        self.assertIn('const offline = window.ROADTRIP_OFFLINE || null;', html)
        self.assertLess(html.index('window.ROADTRIP_OFFLINE = '), html.index('id="mySidebar"'))

    def test_download_requires_access_and_sign_in(self):
        self.assertEqual(self.download('outsider').status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/download_current_map').status_code, 302)

    def test_undecryptable_notes_still_download_the_map_without_plaintext(self):
        with patch.dict(os.environ, {'NOTES_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            response = self.download('owner')
        self.assertEqual(response.status_code, 200)
        bundle = bundle_from(response.get_data(as_text=True))
        self.assertEqual(bundle['notes'], {'error': 'Shared notes could not be included in this download.'})
        self.assertEqual({pdf['id'] for pdf in bundle['pdfs']}, {'shared-pdf', 'owner-private'})

    def test_bundle_escaping_round_trips_unusual_text(self):
        text = 'a </script> b <!-- c --> &   d   é 🏕️'
        html = insert_offline_bundle('<html><head></head><body></body></html>', {'notes': {'text': text}})
        self.assertEqual(bundle_from(html)['notes']['text'], text)
        self.assertEqual(html.count('</script>'), 1)


if __name__ == '__main__':
    unittest.main()
