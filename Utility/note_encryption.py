"""Authenticated encryption and lossless, transactional upgrades of shared notes."""

import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from firebase_admin import firestore


class NoteConflict(Exception):
    """The saved note changed since this editor loaded it."""


class NoteEncryption:
    def __init__(self, key):
        if not key:
            raise ValueError("NOTES_ENCRYPTION_KEY is required")
        self.cipher = Fernet(key.encode("ascii"))

    def encrypt(self, text, path):
        # Binding the document path prevents moving ciphertext to another map.
        payload = json.dumps({"path": path, "text": text}, ensure_ascii=False).encode("utf-8")
        return {"format": "fernet-v1", "token": self.cipher.encrypt(payload).decode("ascii")}

    def decrypt(self, value, path):
        if isinstance(value, str):
            return value  # Existing plaintext; read() upgrades it atomically.
        if not isinstance(value, dict) or value.get("format") != "fernet-v1":
            raise InvalidToken
        try:
            payload = json.loads(self.cipher.decrypt(value["token"].encode("ascii")))
            if payload["path"] != path or not isinstance(payload["text"], str):
                raise InvalidToken
            return payload["text"]
        except (KeyError, TypeError, ValueError, UnicodeError, AttributeError) as error:
            raise InvalidToken from error

    @staticmethod
    def revision(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()

    def read(self, db, ref):
        """Read and, if needed, replace only the legacy text field in one transaction."""
        @firestore.transactional
        def read_note(transaction):
            doc = ref.get(transaction=transaction)
            data = doc.to_dict() or {}
            value = data.get("text", "")
            text = self.decrypt(value, ref.path)
            migrated = doc.exists and isinstance(value, str) and "text" in data
            if migrated:
                value = self.encrypt(text, ref.path)
                transaction.update(ref, {"text": value})
            return text, self.revision(value), migrated

        return read_note(db.transaction())

    def save(self, db, ref, text, revision):
        @firestore.transactional
        def save_note(transaction):
            doc = ref.get(transaction=transaction)
            value = (doc.to_dict() or {}).get("text", "")
            # Never overwrite a note we cannot decrypt, even with a matching revision.
            self.decrypt(value, ref.path)
            if self.revision(value) != revision:
                raise NoteConflict
            encrypted = self.encrypt(text, ref.path)
            transaction.set(ref, {"text": encrypted}, merge=True)
            return self.revision(encrypted)

        return save_note(db.transaction())
