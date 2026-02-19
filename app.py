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

# Load .env for local development (optional)
load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')

    # placeholder for Firestore client
    app.db = None

    # -------------------------
    # Firebase Admin init
    # -------------------------
    def init_firebase():
        """
        Initialize Firebase Admin SDK using one of:
          - FIREBASE_CREDENTIALS -> path to service-account JSON
          - FIREBASE_CREDENTIALS_JSON -> raw JSON string
          - FIREBASE_CREDENTIALS_B64 -> base64 JSON
          - FALLBACK: GOOGLE_APPLICATION_CREDENTIALS
        On success sets app.db = firestore.client()
        """
        # If already initialized, attach client and return
        try:
            firebase_admin.get_app()
            app.logger.info("Firebase Admin already initialized.")
            try:
                app.db = fb_firestore.client()
            except Exception:
                app.db = None
            return
        except ValueError:
            # Not initialized yet
            pass

        # 1) path
        cred_path = os.environ.get("FIREBASE_CREDENTIALS") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path:
            if os.path.isfile(cred_path):
                try:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    app.db = fb_firestore.client()
                    app.logger.info("Initialized Firebase Admin from %s", cred_path)
                    return
                except Exception as e:
                    app.logger.error("Failed to initialize Firebase Admin from %s: %s", cred_path, e)
            else:
                app.logger.warning("FIREBASE_CREDENTIALS path set but file not found: %s", cred_path)

        # 2) raw JSON
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                info = json.loads(cred_json)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)
                app.db = fb_firestore.client()
                app.logger.info("Initialized Firebase Admin from FIREBASE_CREDENTIALS_JSON")
                return
            except Exception as e:
                app.logger.error("Failed to initialize Firebase Admin from FIREBASE_CREDENTIALS_JSON: %s", e)

        # 3) base64 JSON
        cred_b64 = os.environ.get("FIREBASE_CREDENTIALS_B64")
        if cred_b64:
            try:
                decoded = base64.b64decode(cred_b64).decode('utf-8')
                info = json.loads(decoded)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)
                app.db = fb_firestore.client()
                app.logger.info("Initialized Firebase Admin from FIREBASE_CREDENTIALS_B64")
                return
            except Exception as e:
                app.logger.error("Failed to initialize Firebase Admin from FIREBASE_CREDENTIALS_B64: %s", e)

        app.logger.warning("Firebase Admin not initialized. No valid credentials found.")
        app.db = None

    init_firebase()

    # -------------------------
    # Helpers
    # -------------------------
    def parse_csv_text(csv_text):
        if csv_text is None:
            return [], []

        # Normalize newlines and ensure it's a str
        if isinstance(csv_text, bytes):
            csv_text = csv_text.decode('utf-8', errors='replace')
        csv_text = csv_text.replace('\r\n', '\n').replace('\r', '\n')

        # Use csv module to parse
        try:
            reader = csv.DictReader(csv_text.splitlines())
            header = reader.fieldnames or []
            rows = [row for row in reader]
            return header, rows
        except Exception as e:
            app.logger.exception("Failed to parse CSV text: %s", e)
            # fallback: return whole content as a single raw row
            return [], [{"raw": csv_text}]
        
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
        
        
        

    # create a roadmap doc (Firestore-only)
    def create_roadmap_doc(uid, name, filename, csv_text):
        """
        Create a document under users/{uid}/maps with CSV stored as text.
        Returns new document id.
        """
        db = app.db
        if db is None:
            raise RuntimeError("Firestore client not configured")
        doc_ref = db.collection("users").document(uid).collection("maps").document()
        data = {
            "name": name,
            "filename": filename,
            "csv_content": csv_text,
            "created_at": fb_firestore.SERVER_TIMESTAMP,
        }
        doc_ref.set(data)
        return doc_ref.id


    def append_roadmap_doc(uid, name, filename, csv_text):
        """
        Create a document under users/{uid}/maps with CSV stored as text.
        Returns new document id.
        """
        db = app.db
        if db is None:
            raise RuntimeError("Firestore client not configured")
        doc_ref = db.collection("users").document(uid).collection("maps").document()
        data = {
            'stop1': loc_id, nickname, name, description, include_drive, link_titles, etc
        doc_ref.set(data)
        return doc_ref.id




    # -------------------------
    # Routes
    # -------------------------
    @app.route('/')
    def index():
        return render_template('index.html')

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
        return redirect(url_for('index'))

    @app.route('/_health')
    def health():
        info = {}
        try:
            info['firebase'] = bool(app.db)
        except Exception:
            info['firebase'] = False
        return jsonify(info), 200
    
    
    

    # -------------------------
    # Firestore-based Roadtrips
    # -------------------------
    @app.route('/roadtrips')
    @login_required
    def roadtrips():
        """
        List roadtrips for current user from users/{uid}/maps and render the roadtrips.html template.
        No download link or automatic redirection — just view + create UI.
        """
        roadmaps = []
        if getattr(app, 'db', None):
            try:
                coll = app.db.collection("users").document(session['uid']).collection("maps")
                try:
                    docs = coll.order_by("created_at", direction=fb_firestore.Query.DESCENDING).stream()
                except Exception:
                    docs = coll.stream()
                for d in docs:
                    data = d.to_dict()
                    name = data.get('name') or "(unnamed)"
                    created = data.get('created_at')
                    created_str = created.isoformat() if hasattr(created, 'isoformat') else str(created)
                    filename = data.get('filename')
                    roadmaps.append({
                        "id": d.id,
                        "name": name,
                        "created_at": created_str,
                        "filename": filename,
                    })
            except Exception as e:
                app.logger.exception("Error listing user roadmaps: %s", e)
        return render_template('roadtrips.html', roadtrips=roadmaps)






    @app.route('/create_roadtrip', methods=['POST'])
    @login_required
    def create_roadtrip():
        """
        Create a new roadtrip stored in Firestore under users/{uid}/maps/{auto-id}
        Stores CSV contents as 'csv_content' (string). Enforces size cap to avoid 1MB doc limit.
        After creation, redirect back to the roadtrips list page.
        """
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
            new_id = create_roadmap_doc(session['uid'], name, csv_filename, csv_text)
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
        map_id = request.form.get('map_id') or session.get('current_map_id')
        
        create_roadmap_doc(session['uid'], name, csv_filename, csv_text)
        
        
        # if not name:
        #     return "Missing name", 400

        # filename_safe = secure_filename(name) or "roadtrip"
        # csv_filename = f"{filename_safe}.csv"

        # fileobj = request.files.get('file')
        # if fileobj and fileobj.filename:
        #     try:
        #         raw = fileobj.read()
        #         try:
        #             csv_text = raw.decode('utf-8')
        #         except UnicodeDecodeError:
        #             csv_text = raw.decode('latin-1')
        #     except Exception as e:
        #         app.logger.exception("Failed to read uploaded file: %s", e)
        #         return "Failed to read file", 400
        # else:
        #     csv_text = "stop_name,lat,lng\n"

        # # Safety: enforce conservative size cap (900 KB)
        # MAX_BYTES = 900 * 1024
        # csv_bytes = csv_text.encode('utf-8')
        # if len(csv_bytes) > MAX_BYTES:
        #     app.logger.warning("Uploaded CSV too large (%d bytes) for Firestore storage", len(csv_bytes))
        #     return f"CSV too large for Firestore storage (max {MAX_BYTES} bytes)", 400

        # try:
        #     new_id = create_roadmap_doc(session['uid'], name, csv_filename, csv_text)
        #     app.logger.info("Created roadmap doc %s for user %s", new_id, session['uid'])
        #     # Redirect back to the list so the user can view and add roadtrips
        #     return redirect(url_for('roadtrips'))
        # except Exception as e:
        #     app.logger.exception("Failed to create roadmap doc: %s", e)
        return "Failed to create roadmap", 500
        





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
            doc_ref = app.db.collection("users").document(uid).collection("maps").document(map_id)
            doc = doc_ref.get()
            if not doc.exists:
                app.logger.info("Map not found: %s for user %s", map_id, uid)
                return "Map not found", 404

            data = doc.to_dict()
            name = data.get('name') or "(untitled)"
            filename = data.get('filename') or f"{name}.csv"
            csv_text = data.get('csv_content')

            header, rows = parse_csv_text(csv_text)

            # Keep session small: remember which map is active
            session['current_map_id'] = map_id
            session['current_map_name'] = name

            # Attach parsed map to request-global vars (optional)
            g.current_map = {
                "id": map_id,
                "name": name,
                "filename": filename,
                "header": header,
                "rows": rows
            }
            g.current_map_rows = rows

            tf = generate_map(g)
            
            try:
                return send_file(tf.name, mimetype='text/html')
            finally:
                # optionally remove file after some time / or use delete=True for immediate cleanup
                pass

        except Exception as e:
            app.logger.exception("Error opening map %s for user %s: %s", map_id, uid, e)
            return "Error", 500

    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=True)
