from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from firebase_admin import credentials, db
import firebase_admin
import os
import pandas as pd
import json
from datetime import datetime, timedelta
from functools import wraps

# ---------------------------------------
# Flask App Setup
# ---------------------------------------
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Enable CORS for multiple frontend origins
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://127.0.0.1:5500",  # VSCode Live Server
            "http://localhost:5000",  # Flask
            "http://localhost:3000",  # React
            "http://localhost:5173"   # Vite
        ]
    }
})

# ---------------------------------------
# Firebase Initialization
# ---------------------------------------
try:
    cred_path = os.path.join(os.getcwd(), 'serviceAccountKey.json')
    cred = credentials.Certificate(cred_path)

    # ✅ Use your actual Firebase Realtime Database URL
    firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://digital-notice-board-7b9ff-default-rtdb.firebaseio.com'
    })

     
    print("✅ Firebase initialized successfully!")
    print("Database URL: https://digital-notice-board-7b9ff-default-rtdb.firebasedatabase.app")

except Exception as e:
    print("❌ Firebase initialization failed:", e)

# ---------------------------------------
# Login Decorator
# ---------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------
# Frontend Routes
# ---------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

# ---------------------------------------
# Authentication Routes
# ---------------------------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == 'admin123':  # Simple password check
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})

# ---------------------------------------
# Notice Management Routes
# ---------------------------------------
@app.route('/api/notices', methods=['GET'])
def get_notices():
    try:
        ref = db.reference('notices')
        notices = ref.get()
        if notices:
            notice_list = [{'id': k, **v} for k, v in notices.items()]
            notice_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return jsonify(notice_list)
        return jsonify([])
    except Exception as e:
        print("Error fetching notices:", e)
        # Mock data fallback
        return jsonify([
            {
                'id': '1',
                'title': 'Welcome to Digital Notice Board',
                'content': 'This is a sample notice. Configure Firebase to add real-time functionality.',
                'category': 'general',
                'priority': 'high',
                'timestamp': datetime.now().isoformat(),
                'author': 'Admin'
            }
        ])

@app.route('/api/notices', methods=['POST'])
@login_required
def create_notice():
    try:
        data = request.json
        data['timestamp'] = datetime.now().isoformat()
        data['views'] = 0
        ref = db.reference('notices')
        new_notice = ref.push(data)
        return jsonify({'success': True, 'id': new_notice.key})
    except Exception as e:
        print("Error creating notice:", e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notices/<notice_id>', methods=['PUT'])
@login_required
def update_notice(notice_id):
    try:
        data = request.json
        ref = db.reference(f'notices/{notice_id}')
        ref.update(data)
        return jsonify({'success': True})
    except Exception as e:
        print("Error updating notice:", e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notices/<notice_id>', methods=['DELETE'])
@login_required
def delete_notice(notice_id):
    try:
        ref = db.reference(f'notices/{notice_id}')
        ref.delete()
        return jsonify({'success': True})
    except Exception as e:
        print("Error deleting notice:", e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------------------------------
# Analytics Routes
# ---------------------------------------
@app.route('/api/analytics/category-distribution')
def category_distribution():
    try:
        ref = db.reference('notices')
        notices = ref.get()
        if not notices:
            return jsonify({'labels': [], 'values': []})

        categories = {}
        for notice in notices.values():
            cat = notice.get('category', 'general')
            categories[cat] = categories.get(cat, 0) + 1

        return jsonify({'labels': list(categories.keys()), 'values': list(categories.values())})
    except:
        return jsonify({'labels': ['General', 'Events', 'Announcements', 'Updates'],
                        'values': [5, 3, 7, 4]})

@app.route('/api/analytics/timeline')
def notices_timeline():
    try:
        ref = db.reference('notices')
        notices = ref.get()
        if not notices:
            return jsonify({'dates': [], 'counts': []})

        date_counts = {}
        for notice in notices.values():
            timestamp = notice.get('timestamp', '')
            if timestamp:
                date = timestamp.split('T')[0]
                date_counts[date] = date_counts.get(date, 0) + 1

        sorted_dates = sorted(date_counts.keys())
        return jsonify({'dates': sorted_dates, 'counts': [date_counts[d] for d in sorted_dates]})
    except:
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7, -1, -1)]
        return jsonify({'dates': dates, 'counts': [2, 1, 3, 2, 4, 3, 5, 6]})

@app.route('/api/analytics/priority-stats')
def priority_stats():
    try:
        ref = db.reference('notices')
        notices = ref.get()
        if not notices:
            return jsonify({'high': 0, 'medium': 0, 'low': 0})

        priorities = {'high': 0, 'medium': 0, 'low': 0}
        for notice in notices.values():
            priority = notice.get('priority', 'low')
            priorities[priority] = priorities.get(priority, 0) + 1

        return jsonify(priorities)
    except:
        return jsonify({'high': 8, 'medium': 12, 'low': 5})

# ---------------------------------------
# CSV Analytics
# ---------------------------------------
@app.route('/api/analytics/csv-data')
def csv_data():
    try:
        csv_path = 'data/sample_data.csv'
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            return jsonify({'columns': df.columns.tolist(), 'data': df.to_dict('records')})
        return jsonify({'columns': [], 'data': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------------------
# Error Handler & Cache Control
# ---------------------------------------
@app.errorhandler(404)
def not_found(e):
    from flask import request
    print(f"404 for path={request.path} method={request.method}")
    return jsonify({"success": False, "error": "Not Found", "path": request.path}), 404

@app.after_request
def add_headers(resp):
    resp.headers['Cache-Control'] = 'no-store'
    return resp

# ---------------------------------------
# Run the App
# ---------------------------------------
if __name__ == '__main__':
    print("\n=== ROUTES ===")
    print(app.url_map)
    print("==============\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
