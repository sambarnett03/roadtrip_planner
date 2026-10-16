## Repo used for hosting sbarnett.pythonanywhere.com

The website allows users to plan and share roadtrips. Users can add pins onto a map with descriptions of each place. There is a sidebar where notes can be made to plan the trip; these can be personal or shared with other collaborators. The map can be downloaded as an HTML file for offline viewing.

## Shared note encryption

Shared sidebar notes are encrypted by Flask before being stored at `users/{owner}/maps/{map}/planning/notes`. The `text` field becomes a versioned Fernet ciphertext object. The encryption key lives only in the server environment, outside Firestore and browser storage. Firebase database access alone cannot reveal the contents. The application server and anyone with its encryption key can decrypt notes; this is not end-to-end encryption. Note size and encryption time remain visible.

The notes API verifies a Firebase ID token on every request and checks the map's existing owner/editor/viewer permissions. Owners and editors can save; viewers can read. Firestore listeners still provide live updates. Concurrent edits produce a conflict message instead of silently replacing another user's changes. Personal notes continue using the existing browser-local storage; they are not stored in Firebase or encrypted by this feature. PDFs and marker descriptions are outside this change.

Encryption uses the maintained `cryptography` library's [authenticated Fernet implementation](https://cryptography.io/en/stable/fernet/). Existing note HTML is preserved exactly during migration, including Unicode and formatting. Migration changes only the `text` field, within a Firestore transaction. Missing, incorrect, or damaged keys/ciphertext block access and saving; there is no plaintext save fallback. New saves are limited to 500 KB of UTF-8 HTML to leave room for encryption overhead. An existing note too large for Firestore after encryption causes migration to stop without replacing that note.

## Deployment and existing data

1. Take a secure database backup before migration. Keep the backup access restricted: older backups and Firestore history may still contain plaintext after migration.
2. Install the updated dependencies with `python -m pip install -r requirements.txt` in the deployment environment.
3. Generate a note key **once** using `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Save it as `NOTES_ENCRYPTION_KEY` in the server environment or the existing ignored `.env`. Use the same value for every worker, restart, deployment, and migration. Keep a separate secure backup of this key. Never put it in Firestore, frontend config, source control, or a user's profile. Losing the key makes encrypted notes unrecoverable. Replacing it is not a key rotation procedure.
4. Keep the existing strong `FLASK_SECRET_KEY`, or configure a persistent random value if one was missing. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. The app now refuses to start with a missing key or the old `dev-secret` fallback because sessions control map sharing. Serve production traffic over HTTPS.
5. **Before migrating, block all client writes to note documents in the deployed Firestore rules**, including writes from older open tabs and downloaded maps. Keep reads restricted to current map members so the live listener can work. No deployed rules file is present in this repository; update the actual Firebase rules. See the example below. Ensure no broader matching rule grants writes to this same path: Firestore combines matching grants with OR, so adding `allow write: if false` alone cannot override an existing grant. Server Admin SDK writes bypass these client rules, as [Firebase documents](https://firebase.google.com/docs/firestore/security/rules-conditions).
6. Deploy/reload the application with the configured keys. Have users reopen their maps so they use the updated sidebar. Old clients cannot read the new format or save through the new API.
7. In that same server environment, run `flask --app app:create_app encrypt-notes`. This scans all `planning/notes` documents, including those below deleted maps, encrypts legacy strings, and validates already encrypted notes without rewriting them. It can safely be rerun after interruption. If it encounters an error, it stops and reports the document path without printing note contents or keys. Previously completed documents stay encrypted; the failing note is untouched. Confirm the command completes successfully before considering all existing notes protected.

Opening a note also migrates its legacy text atomically, so existing data remains readable during rollout. The bulk command is required to cover notes nobody opens. Keep the key and this encryption-capable code available after migration; older application versions cannot read encrypted notes.

Example rule to adapt within the existing `match /databases/{database}/documents` block:

```text
match /users/{ownerId}/maps/{mapId}/planning/notes {
  allow read: if request.auth != null && (
    request.auth.uid == ownerId ||
    request.auth.uid in get(
      /databases/$(database)/documents/users/$(ownerId)/maps/$(mapId)
    ).data.get('collaborators', {})
  );
  allow write: if false;
}
```

Replace any existing rules that grant client writes to this path, and exclude it from broader write grants. Keep unrelated map/stops rules in place. Check in the Firebase rules simulator that owners/editors/viewers can read their notes, unrelated users cannot read, and **every browser user is denied note create/update/delete**, including plaintext writes. The Flask server performs all note writes after verifying Firebase identity and map permissions.

## Local checks

The checked-in `venv` may reference another machine; create a local environment and install `requirements.txt` if needed. The focused tests use an in-memory Firestore double, never a live database:

```sh
python -m unittest discover -s tests
node --test tests/encrypted_notes.test.cjs
```
