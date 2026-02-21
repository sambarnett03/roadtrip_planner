# app.py
import os
import io
import json
import base64
import datetime
from functools import wraps
import csv

from Utility.plotting_functions import *
from Utility.html_edits import *
from Utility.classes import Place, RoadTrip
from Utility.utility_functions import *

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, g, flash, send_file, jsonify, Response
)

# Firebase Admin (Firestore)
import firebase_admin
from firebase_admin import credentials, auth as fb_auth, firestore as fb_firestore

from werkzeug.utils import secure_filename

from make_map import generate_map
import tempfile


env_path = '/home/sbarnett/roadtrip_planner/.env'
load_dotenv(dotenv_path=env_path)


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')

    # placeholder for Firestore client
    app.db = None

    # -------------------------
    # Firebase Admin init
    # -------------------------
    def init_firebase():
        print('function called')
        # 1. Check if already initialized
        try:
            firebase_admin.get_app()
            app.db = fb_firestore.client()
            return
        except ValueError:
            pass

        # 2. Get the path from environment
        cred_path = os.environ.get("FIREBASE_CREDENTIALS")

        # 3. If path is missing or wrong, use a hardcoded fallback for PythonAnywhere
        if not cred_path or not os.path.exists(cred_path):
            cred_path = '/home/sbarnett/roadtrip_planner/roadmap-planner-87b0a-firebase-adminsdk-fbsvc-59190012ce.json'

        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            app.db = fb_firestore.client()
            print(f"Successfully initialized Firebase with: {cred_path}")
        else:
            # This will show up in your Error Log and stop the app from being "half-broken"
            raise RuntimeError(f"CRITICAL: Service account file not found at {cred_path}")

    init_firebase()


    # -------------------------
    # Helpers
    # -------------------------
    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not session.get('uid'):
                return redirect(url_for('sign_up'))
            return fn(*a, **kw)
        return wrapper

    @app.before_request
    def load_user():
        g.uid = session.get('uid')


    def get_next_sequence_number(uid, map_id):
        db = app.db
        stops_ref = (
            db.collection("users")
            .document(uid)
            .collection("maps")
            .document(map_id)
            .collection("stops")
        )

        # Get the highest seq value
        query = stops_ref.order_by("id", direction=fb_firestore.Query.DESCENDING).limit(1)
        docs = list(query.stream())

        if not docs:
            return 1  # first stop

        highest_seq = docs[0].to_dict().get("id", 0)
        return highest_seq + 1




    # -------------------------
    # Collaboration helpers + routes
    # -------------------------
    def add_collaborator_to_map(owner_uid, map_id, collaborator_uid, role='editor'):
            """
            Add collaborator_uid to the map doc at users/{owner_uid}/maps/{map_id}
            Sets map.collaborators.<collaborator_uid> = { ... }
            AND appends collaborator_uid to map.collaborator_uids array.
            """
            db = getattr(app, 'db', None)
            if db is None:
                raise RuntimeError("Firestore client not configured")

            map_ref = db.collection("users").document(owner_uid).collection("maps").document(map_id)

            # update nested field for details AND add to array for searchability
            coll_field = f"collaborators.{collaborator_uid}"

            map_ref.update({
                coll_field: {
                    "role": role,
                    "added_at": fb_firestore.SERVER_TIMESTAMP,
                    "by": owner_uid
                },
                "collaborator_uids": fb_firestore.ArrayUnion([collaborator_uid])
            })


    @app.route('/collaborate', methods=['GET', 'POST'])
    @login_required
    def collaborate():
        """
        Simple collaborator management UI.
        Shows current user id and the collaborators for the active map.
        POST adds a collaborator uid (owner-only).
        """
        uid = session.get('uid')
        map_id = request.args.get('map_id') or session.get('current_map_id')

        if not map_id:
            flash("No active map selected. Open a map first.", "error")
            return redirect(url_for('roadtrips'))

        db = getattr(app, 'db', None)
        if db is None:
            flash("Firestore not configured.", "error")
            return redirect(url_for('roadtrips'))

        map_ref = db.collection("users").document(uid).collection("maps").document(map_id)
        try:
            map_doc = map_ref.get()
        except Exception as e:
            app.logger.exception("Error fetching map for collaborate page: %s", e)
            flash("Failed to load map.", "error")
            return redirect(url_for('roadtrips'))

        if not map_doc.exists:
            flash("Map not found (or you are not the owner).", "error")
            return redirect(url_for('roadtrips'))

        map_data = map_doc.to_dict() or {}
        # Only the owner should be allowed to add collaborators via this simple UI.
        owner_uid = map_data.get('owner') or uid
        if request.method == 'POST':
            # Only owner can add collaborators in this simple flow
            if uid != owner_uid:
                flash("Only the map owner may add collaborators.", "error")
                return redirect(url_for('collaborate', map_id=map_id))

            collab_uid = (request.form.get('collab_uid') or '').strip()
            role = (request.form.get('role') or 'editor').strip()
            if not collab_uid:
                flash("Please enter a collaborator user id.", "error")
                return redirect(url_for('collaborate', map_id=map_id))

            try:
                add_collaborator_to_map(owner_uid, map_id, collab_uid, role=role)
                flash(f"Added collaborator {collab_uid} as {role}.", "success")
            except Exception as e:
                app.logger.exception("Failed to add collaborator: %s", e)
                flash("Failed to add collaborator (check server logs).", "error")

            return redirect(url_for('collaborate', map_id=map_id))

        # For GET: render current collaborators
        collaborators = map_data.get('collaborators') or {}
        # collaborators is a dict keyed by uid -> { role, added_at, by }
        return render_template('collaborate.html',
                               map_id=map_id,
                               user_id=uid,
                               owner_id=owner_uid,
                               collaborators=collaborators)


    @app.route('/collaborators/remove', methods=['POST'])
    @login_required
    def remove_collaborator():
        """
        Remove a collaborator from the current map.
        Expects form data: map_id, collab_uid
        Only the map owner may remove collaborators.
        """
        uid = session.get('uid')
        map_id = request.form.get('map_id') or session.get('current_map_id')
        collab_uid = (request.form.get('collab_uid') or '').strip()

        if not map_id or not collab_uid:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'missing parameters'}), 400
            flash("Missing map_id or collaborator id.", "error")
            return redirect(url_for('collaborate', map_id=map_id))

        db = getattr(app, 'db', None)
        if db is None:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'firestore not configured'}), 500
            flash("Firestore not configured.", "error")
            return redirect(url_for('collaborate', map_id=map_id))

        # verify map exists and that the requester is the owner
        map_ref = db.collection("users").document(uid).collection("maps").document(map_id)
        try:
            map_doc = map_ref.get()
        except Exception as e:
            app.logger.exception("Error fetching map for remove collaborator: %s", e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'failed to load map'}), 500
            flash("Failed to load map.", "error")
            return redirect(url_for('collaborate', map_id=map_id))

        if not map_doc.exists:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'map not found or access denied'}), 404
            flash("Map not found (or you are not the owner).", "error")
            return redirect(url_for('collaborate', map_id=map_id))

        map_data = map_doc.to_dict() or {}
        owner_uid = map_data.get('owner') or uid
        if uid != owner_uid:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'only owner may remove collaborators'}), 403
            flash("Only the map owner may remove collaborators.", "error")
            return redirect(url_for('collaborate', map_id=map_id))

        try:
            # remove nested field collaborators.<collab_uid> AND remove from array
            map_ref.update({
                f"collaborators.{collab_uid}": fb_firestore.DELETE_FIELD,
                "collaborator_uids": fb_firestore.ArrayRemove([collab_uid])
            })

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'ok', 'removed': collab_uid}), 200
            flash(f"Removed collaborator {collab_uid}.", "success")
        except Exception as e:
            app.logger.exception("Failed to remove collaborator: %s", e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'failed to remove collaborator'}), 500
            flash("Failed to remove collaborator (check server logs).", "error")

        return redirect(url_for('collaborate', map_id=map_id))



    def create_roadmap_doc(uid, name):
            """
            Create a document under users/{uid}/maps with server-side metadata.
            Returns new document id.
            """
            db = app.db
            if db is None:
                raise RuntimeError("Firestore client not configured")
            doc_ref = db.collection("users").document(uid).collection("maps").document()
            data = {
                "name": name,
                "created_at": fb_firestore.SERVER_TIMESTAMP,
                "last_seq": 0,
                "owner": uid,
                "collaborators": {},
                # NEW: Initialize empty array for querying
                "collaborator_uids": []
            }
            doc_ref.set(data)
            return doc_ref.id



    def append_roadmap_doc(uid, place, map_id):
        """
        Create a document under users/{uid}/maps with CSV stored as text.
        Returns new document id.
        """
        db = app.db
        if db is None:
            raise RuntimeError("Firestore client not configured")

        doc_ref = db.collection("users") \
             .document(uid) \
             .collection("maps") \
             .document(map_id) \
             .collection("stops") \
             .document(place.name)

        place.id = get_next_sequence_number(uid, map_id)
        doc_ref.set(place.to_dict())
        return doc_ref.id




    # -------------------------
    # Routes
    # -------------------------
    @app.route('/')
    def index():
        # If the user is already logged in, send them to their roadtrips
        if 'uid' in session:
            return redirect(url_for('roadtrips'))

        # Otherwise, immediately redirect to sign up
        return redirect(url_for('sign_up'))

    @app.route('/dashboard')
    def dashboard():
        roadmaps = []
        if getattr(app, 'db', None) and session.get('uid'):
            try:
                docs = app.db.collection('users').document(session['uid']).collection('maps').stream()
                for d in docs:
                    roadmaps.append(d.to_dict())
            except Exception as e:
                app.logger.exception("Error fetching roadmaps: %s", e)
        return render_template('dashboard.html', roadmaps=roadmaps)



    @app.route('/add_marker', methods=['GET', 'POST'])
    def add_place():
        if request.method == 'POST':
            name = request.form.get('place_name')
            if not name:
                flash('Please provide a place name.', 'error')
                return redirect(url_for('add_place'))
            if getattr(app, 'db', None) and session.get('uid'):
                try:
                    data = {'name': name, 'owner': session['uid'], 'created_at': datetime.datetime.utcnow()}
                    app.db.collection('places').add(data)
                    flash('Place added.', 'success')
                except Exception as e:
                    app.logger.error('Error saving place: %s', e)
                    flash('Failed to save place.', 'error')
            else:
                flash('Firebase not configured — not saved.', 'warning')
            return redirect(url_for('dashboard'))
        return render_template('add_marker.html')




    @app.route('/sign_up')
    def sign_up():
        # render sign_up template (frontend Firebase config for client SDK)
        return render_template('sign_up.html',
                               firebase_api_key=os.environ.get('FIREBASE_API_KEY', ''),
                               firebase_auth_domain=os.environ.get('FIREBASE_AUTH_DOMAIN', ''),
                               firebase_project_id=os.environ.get('FIREBASE_PROJECT_ID', ''))





    # helper: check whether user_uid has access to owner_uid's map
    def check_map_access(owner_uid, map_id, user_uid, require_write=False):
        """
        Return (True, map_doc) if user_uid is allowed to access map at users/{owner_uid}/maps/{map_id}.
        If require_write=True then collaborator must have role 'editor' (or be owner).
        Otherwise 'viewer' or 'editor' suffices for read access.
        """
        db = getattr(app, 'db', None)
        if db is None:
            return False, None

        map_ref = db.collection("users").document(owner_uid).collection("maps").document(map_id)
        try:
            map_doc = map_ref.get()
        except Exception as e:
            app.logger.exception("check_map_access: failed to read map: %s", e)
            return False, None

        if not map_doc.exists:
            return False, None

        if user_uid == owner_uid:
            return True, map_doc

        data = map_doc.to_dict() or {}
        collab_map = data.get('collaborators') or {}
        entry = collab_map.get(user_uid)
        if not entry:
            return False, map_doc

        role = entry.get('role', 'editor')
        if require_write and role != 'editor':
            return False, map_doc

        # read allowed (role present), or write allowed (role == editor)
        return True, map_doc


    @app.route('/api/stops/update', methods=['POST'])
    @login_required
    def api_update_stop_field():
        uid = session.get('uid')
        payload = request.get_json(silent=True) or {}
        map_id = payload.get('map_id') or session.get('current_map_id')
        owner_id = payload.get('owner_id') or uid
        doc_id = payload.get('doc_id')
        field = payload.get('field')
        value = payload.get('value')

        if not map_id or not doc_id or field is None:
            return jsonify({'error': 'missing parameters'}), 400

        db = getattr(app, 'db', None)
        if db is None:
            return jsonify({'error': 'firestore not configured'}), 500

        # permission check (write)
        allowed, map_doc = check_map_access(owner_id, map_id, uid, require_write=True)
        if not allowed:
            return jsonify({'error': 'access denied'}), 403

        try:
            # Attempt to coerce certain types (basic heuristics)
            new_value = value
            if field == 'id':
                try:
                    new_value = int(value)
                except Exception:
                    pass
            else:
                if isinstance(value, str):
                    if value.isdigit():
                        new_value = int(value)
                    else:
                        try:
                            fv = float(value)
                            if '.' in value:
                                new_value = fv
                        except Exception:
                            pass

            doc_ref = db.collection("users").document(owner_id).collection("maps").document(map_id).collection("stops").document(doc_id)
            doc_ref.update({field: new_value})
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            app.logger.exception("api_update_stop_field error: %s", e)
            return jsonify({'error': 'failed to update field'}), 500


    @app.route('/api/stops/delete', methods=['POST'])
    @login_required
    def api_delete_stop():
        """
        Deletes a specific stop document.
        Expects JSON: { "map_id": "...", "doc_id": "...", "owner_id": "..." (optional) }
        """
        uid = session.get('uid')
        data = request.get_json(silent=True) or {}

        map_id = data.get('map_id')
        doc_id = data.get('doc_id')
        owner_id = data.get('owner_id') or uid # Use explicit owner if shared

        if not map_id or not doc_id:
            return jsonify({'error': 'Missing map_id or doc_id'}), 400

        # Check permission (logic similar to update/reorder)
        allowed, map_doc = check_map_access(owner_id, map_id, uid, require_write=True)
        if not allowed:
            return jsonify({'error': 'Access denied'}), 403

        db = getattr(app, 'db', None)
        if not db:
            return jsonify({'error': 'DB not configured'}), 500

        try:
            # Delete the specific document
            db.collection("users").document(owner_id)\
              .collection("maps").document(map_id)\
              .collection("stops").document(doc_id)\
              .delete()

            return jsonify({'status': 'ok', 'deleted': doc_id}), 200
        except Exception as e:
            app.logger.exception("Failed to delete stop %s", doc_id)
            return jsonify({'error': str(e)}), 500



    @app.route('/api/stops')
    @login_required
    def api_get_stops():
        """
        Returns JSON array of stops for the requested map.
        Query params:
          - map_id (required)
          - owner_id (optional) -> when absent, defaults to session['uid']
        Access: owner or collaborator (viewer/editor) for read.
        """
        uid = session.get('uid')
        map_id = request.args.get('map_id') or session.get('current_map_id')
        owner_id = request.args.get('owner_id') or uid  # allow owner override for shared maps

        if not map_id:
            return jsonify({"error": "missing map_id"}), 400

        db = getattr(app, 'db', None)
        if db is None:
            return jsonify({"error": "firestore not configured"}), 500

        # permission check (read)
        allowed, map_doc = check_map_access(owner_id, map_id, uid, require_write=False)
        if not allowed:
            return jsonify({"error": "access denied"}), 403

        try:
            coll = db.collection("users").document(owner_id).collection("maps").document(map_id).collection("stops")
            try:
                docs = coll.order_by("id").stream()
            except Exception:
                docs = coll.stream()

            stops = []
            for d in docs:
                data = d.to_dict() or {}
                data['_doc_id'] = d.id
                stops.append(data)

            # optionally include map metadata (owner, name, visible_fields)
            map_meta = (map_doc.to_dict() or {}) if map_doc else {}
            return jsonify({"stops": stops, "map_meta": map_meta}), 200
        except Exception as e:
            app.logger.exception("api_get_stops error: %s", e)
            return jsonify({"error": "failed to fetch stops"}), 500



    @app.route('/api/stops/reorder', methods=['POST'])
    @login_required
    def api_reorder_stops():
        uid = session.get('uid')
        payload = request.get_json(silent=True) or {}
        map_id = payload.get('map_id') or session.get('current_map_id')
        owner_id = payload.get('owner_id') or uid
        order_list = payload.get('order') or []

        if not map_id:
            return jsonify({"error": "missing map_id"}), 400
        if not isinstance(order_list, list):
            return jsonify({"error": "invalid order list"}), 400

        db = getattr(app, 'db', None)
        if db is None:
            return jsonify({"error": "firestore not configured"}), 500

        # permission check (write)
        allowed, map_doc = check_map_access(owner_id, map_id, uid, require_write=True)
        if not allowed:
            return jsonify({"error": "access denied"}), 403

        try:
            batch = db.batch()
            coll_base = db.collection("users").document(owner_id).collection("maps").document(map_id).collection("stops")
            i = 1
            for doc_id in order_list:
                if not isinstance(doc_id, str):
                    continue
                doc_ref = coll_base.document(doc_id)
                batch.update(doc_ref, {"id": i})
                i += 1

            if i > 1:
                batch.commit()
                return jsonify({"status": "ok", "saved_count": i-1}), 200
            else:
                return jsonify({"status": "ok", "saved_count": 0}), 200

        except Exception as e:
            app.logger.exception("api_reorder_stops error: %s", e)
            return jsonify({"error": "failed to save new order"}), 500






    # -------------------------
    # Firestore-based Roadtrips
    # -------------------------


    @app.route('/delete_map', methods=['POST'])
    @login_required
    def delete_map():
        """
        Deletes a map owned by the current user.
        """
        uid = session.get('uid')
        map_id = request.form.get('map_id')

        if not map_id:
            flash("Missing map ID.", "error")
            return redirect(url_for('roadtrips'))

        db = getattr(app, 'db', None)
        if db is None:
            flash("Database not connected.", "error")
            return redirect(url_for('roadtrips'))

        try:
            # 1. Get reference to the map
            map_ref = db.collection("users").document(uid).collection("maps").document(map_id)
            doc = map_ref.get()

            # 2. Verify existence
            if not doc.exists:
                flash("Map not found.", "error")
                return redirect(url_for('roadtrips'))

            # 3. Delete the map document
            # Note: In Firestore, deleting a document does NOT automatically delete
            # its subcollections (like 'stops' or 'planning'). They will become
            # orphaned but will no longer appear in your list.
            map_ref.delete()

            flash("Roadtrip deleted successfully.", "success")

        except Exception as e:
            app.logger.exception("Error deleting map %s: %s", map_id, e)
            flash("An error occurred while deleting the map.", "error")

        return redirect(url_for('roadtrips'))


    @app.route('/map/<owner_id>/<map_id>')
    @login_required
    def open_map_shared(owner_id, map_id):
        """
        Open a map that belongs to owner_id. Checks current user's read access.
        Renders the same map HTML (via generate_map) but reads stops from owner's namespace.
        """
        uid = session.get('uid')
        db = getattr(app, 'db', None)
        if db is None:
            app.logger.error("Firestore not configured; cannot open map")
            return "Firestore not configured", 500

        # permission check (read)
        allowed, map_doc = check_map_access(owner_id, map_id, uid, require_write=False)
        if not allowed:
            return "Access denied", 403

        try:
            stops = db.collection("users") \
                    .document(owner_id) \
                    .collection("maps") \
                    .document(map_id) \
                    .collection("stops") \
                    .order_by("id") \
                    .stream()

            rows = [doc.to_dict() for doc in stops]

            # remember which map is active and where it is owned
            session['current_map_id'] = map_id
            session['current_map_owner'] = owner_id

            # 1. Generate the basic Map HTML
            tf = generate_map(map_id, rows)

            # 2. Inject Sidebar with correct Owner ID and Map ID
            # Pass client-side config from env vars if available
            fb_config = {
                "apiKey": os.environ.get('FIREBASE_API_KEY'),
                "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN'),
                "projectId": os.environ.get('FIREBASE_PROJECT_ID'),
                "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET'),
                "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
                "appId": os.environ.get('FIREBASE_APP_ID')
            }

            # This inserts the sidebar code into the temp file
            insert_sidebar(tf.name, map_id, owner_id, firebase_config=fb_config)

            try:
                return send_file(tf.name, mimetype='text/html')
            finally:
                pass

        except Exception as e:
            app.logger.exception("Error opening map %s for user %s: %s", map_id, uid, e)
            return "Error", 500


    @app.route('/map/<map_id>')
    @login_required
    def open_map(map_id):
        """
        Load the map by Firestore doc id, parse CSV, then pass name/header/rows
        into a rendering function if provided, otherwise render templates/map.html.
        """
        uid = session.get('uid')
        if not uid:
            return redirect(url_for('sign_up'))

        if not getattr(app, 'db', None):
            app.logger.error("Firestore not configured; cannot open map")
            return "Firestore not configured", 500

        try:
            stops = app.db.collection("users") \
                    .document(uid) \
                    .collection("maps") \
                    .document(map_id) \
                    .collection("stops") \
                    .order_by("id") \
                    .stream()

            rows = [doc.to_dict() for doc in stops]

            # Keep session small: remember which map is active
            session['current_map_id'] = map_id
            session['current_map_owner'] = uid # For owned maps, owner is self

            # 1. Generate Map
            tf = generate_map(map_id, rows)

            # 2. Inject Sidebar
            fb_config = {
                "apiKey": os.environ.get('FIREBASE_API_KEY'),
                "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN'),
                "projectId": os.environ.get('FIREBASE_PROJECT_ID'),
                "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET'),
                "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
                "appId": os.environ.get('FIREBASE_APP_ID')
            }

            insert_sidebar(tf.name, map_id, uid, firebase_config=fb_config)

            try:
                return send_file(tf.name, mimetype='text/html')
            finally:
                # optionally remove file after some time / or use delete=True for immediate cleanup
                pass

        except Exception as e:
            app.logger.exception("Error opening map %s for user %s: %s", map_id, uid, e)
            return "Error", 500


    @app.route('/roadtrips')
    @login_required
    def roadtrips():
        """
        List roadtrips for current user:
         - maps they own (users/{uid}/maps)
         - maps shared with them (collection-group 'maps' where collaborator_uids array contains uid)
        """
        owned_roadmaps = []
        shared_roadmaps = []
        uid = session.get('uid')
        db = getattr(app, 'db', None)
        if not db:
            app.logger.warning("Firestore not configured - roadtrips cannot be loaded")
            return render_template('roadtrips.html', owned_roadtrips=owned_roadmaps, shared_roadtrips=shared_roadmaps)

        # 1) Owned maps
        try:
            coll = db.collection("users").document(uid).collection("maps")
            try:
                docs = coll.order_by("created_at", direction=fb_firestore.Query.DESCENDING).stream()
            except Exception:
                docs = coll.stream()
            for d in docs:
                data = d.to_dict() or {}
                name = data.get('name') or "(unnamed)"
                created = data.get('created_at')
                created_str = created.isoformat() if hasattr(created, 'isoformat') else str(created)
                filename = data.get('filename')
                owned_roadmaps.append({
                    "id": d.id,
                    "name": name,
                    "created_at": created_str,
                    "filename": filename,
                    "owner": uid
                })
        except Exception as e:
            app.logger.exception("Error listing user's own roadmaps: %s", e)

        # 2) Shared maps: search across all users/*/maps using a collection-group query
        try:
            # Query maps where the 'collaborator_uids' array contains the current user's uid
            query = db.collection_group("maps").where("collaborator_uids", "array_contains", uid)
            shared_docs = list(query.stream())

            for d in shared_docs:
                # skip maps owned by the current user (avoid duplicating owned maps)
                owner_ref = d.reference.parent.parent
                owner_id = owner_ref.id if owner_ref else None
                if owner_id == uid:
                    continue

                data = d.to_dict() or {}
                name = data.get('name') or "(unnamed)"
                created = data.get('created_at')
                created_str = created.isoformat() if hasattr(created, 'isoformat') else str(created)
                filename = data.get('filename')

                shared_roadmaps.append({
                    "id": d.id,
                    "name": name,
                    "created_at": created_str,
                    "filename": filename,
                    "owner": owner_id
                })
        except Exception as e:
            app.logger.exception("Error listing shared roadmaps: %s", e)

        # Render template with both lists
        return render_template('roadtrips.html',
                               owned_roadtrips=owned_roadmaps,
                               shared_roadtrips=shared_roadmaps)




    @app.route('/create_roadtrip', methods=['POST'])
    @login_required
    def create_roadtrip():
        name = (request.form.get('name') or "").strip()
        if not name:
            return "Missing name", 400

        filename_safe = secure_filename(name) or "roadtrip"
        csv_filename = f"{filename_safe}.csv"

        fileobj = request.files.get('file')
        if fileobj and fileobj.filename:
            try:
                raw = fileobj.read()
                try:
                    csv_text = raw.decode('utf-8')
                except UnicodeDecodeError:
                    csv_text = raw.decode('latin-1')
            except Exception as e:
                app.logger.exception("Failed to read uploaded file: %s", e)
                return "Failed to read file", 400
        else:
            csv_text = "Location ID	Nickname, Name, Description, Overnight, Include Drive, Link Titles, Links, Gmaps ID, Latitude, Longitude\n"


        # Safety: enforce conservative size cap (900 KB)
        MAX_BYTES = 900 * 1024
        csv_bytes = csv_text.encode('utf-8')
        if len(csv_bytes) > MAX_BYTES:
            app.logger.warning("Uploaded CSV too large (%d bytes) for Firestore storage", len(csv_bytes))
            return f"CSV too large for Firestore storage (max {MAX_BYTES} bytes)", 400

        try:
            new_id = create_roadmap_doc(session['uid'], name)
            app.logger.info("Created roadmap doc %s for user %s", new_id, session['uid'])
            # Redirect back to the list so the user can view and add roadtrips
            return redirect(url_for('roadtrips'))
        except Exception as e:
            app.logger.exception("Failed to create roadmap doc: %s", e)
            return "Failed to create roadmap", 500




    @app.route('/append_to_roadtrip', methods=['POST'])
    @login_required
    def append_to_roadtrip():
        name = (request.form.get('name') or "").strip()
        desc = (request.form.get('desc') or "").strip()
        overnight = (request.form.get('overnight') or "").strip()
        place_type = (request.form.get('type') or "").strip()
        nickname = (request.form.get('nickname') or "").strip()
        place_id = None

        if nickname == '': nickname = None

        map_id = request.form.get('map_id') or session.get('current_map_id')

        gmaps_id, lat, long = get_place_id(name)

        place_object = Place(place_id, name, desc, overnight, place_type, nickname, gmaps_id, lat, long)

        append_roadmap_doc(session['uid'], place_object, map_id)

        return redirect(url_for('open_map', map_id=map_id))



    @app.route("/stops")
    def stops_table():
        map_id = session.get('current_map_id')
        user_id = session['uid']

        firebase_config = {
            "apiKey": os.environ.get("FIREBASE_API_KEY"),
            "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
            "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
        }


        return render_template("stops_table.html",
                       map_id=map_id,
                       owner_id=session.get('current_map_owner'),
                       user_id=session.get('uid'))







    # Auth endpoints
    @app.route('/session_login', methods=['POST'])
    def session_login():
        data = request.get_json(silent=True) or {}
        id_token = data.get('idToken')
        if not id_token:
            return jsonify({"error": "missing idToken"}), 400
        try:
            decoded = fb_auth.verify_id_token(id_token)
            uid = decoded.get('uid')
            session['uid'] = uid
            app.logger.info("Created server session for uid=%s", uid)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            app.logger.error("Failed to verify id token: %s", e)
            return jsonify({"error": "invalid token"}), 401

    @app.route('/sign_out')
    def sign_out():
        session.pop('uid', None)
        return redirect(url_for('sign_up'))

    @app.route('/_health')
    def health():
        info = {}
        try:
            info['firebase'] = bool(app.db)
        except Exception:
            info['firebase'] = False
        return jsonify(info), 200


    return app



if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=True)
