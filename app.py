import os
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import firebase_admin
from firebase_admin import credentials, firestore
from functools import wraps

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')  # override in prod

    # Initialize Firebase Admin SDK using path from env var FIREBASE_CREDENTIALS
    cred_path = os.environ.get('FIREBASE_CREDENTIALS')
    if cred_path:
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            app.logger.info('Initialized Firebase Admin SDK from %s', cred_path)
            app.db = firestore.client()
        except Exception as e:
            app.logger.error('Failed to initialize Firebase Admin SDK: %s', e)
            app.db = None
    else:
        app.logger.warning('FIREBASE_CREDENTIALS not set. Firebase disabled.')
        app.db = None

    # Simple routes
    @app.before_request
    def load_user():
        g.uid = session.get('uid')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        # Example: fetch roadmap docs for current user if firebase is configured
        roadmaps = []
        if getattr(app, 'db', None) and g.uid:
            try:
                docs = app.db.collection('roadmaps').where('owner', '==', g.uid).stream()
                roadmaps = [d.to_dict() for d in docs]
            except Exception as e:
                app.logger.error('Error fetching roadmaps: %s', e)
        return render_template('dashboard.html', roadmaps=roadmaps)

    @app.route('/add_place', methods=['GET', 'POST'])
    def add_place():
        if request.method == 'POST':
            # Minimal example: accept place name and save to Firestore if available
            name = request.form.get('place_name')
            if not name:
                flash('Please provide a place name.', 'error')
                return redirect(url_for('add_place'))
            if getattr(app, 'db', None) and g.uid:
                try:
                    data = {'name': name, 'owner': g.uid}
                    app.db.collection('places').add(data)
                    flash('Place added.', 'success')
                except Exception as e:
                    app.logger.error('Error saving place: %s', e)
                    flash('Failed to save place.', 'error')
            else:
                flash('Firebase not configured — not saved.', 'warning')
            return redirect(url_for('dashboard'))
        return render_template('add_place.html')

    @app.route('/sign_up', methods=['GET', 'POST'])
    def sign_up():
        # This example does not implement real auth — just a placeholder to demonstrate structure.
        if request.method == 'POST':
            uid = request.form.get('uid') or 'user_demo'
            session['uid'] = uid
            flash('Signed in as ' + uid, 'success')
            return redirect(url_for('dashboard'))
        return render_template('sign_up.html')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
