import os
from flask import Flask, request, render_template,redirect,url_for,session,flash,Response,jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import threading
import detecam_test,center_cam
import time
import db
import random
from db import get_db
import cv2
import common
from queue import Queue

frame_queue_l = Queue(maxsize=1)
frame_queue_r = Queue(maxsize=1)
frame_queue_center = Queue(maxsize=1)

def start_center_camera():
    threading.Thread(
        target=center_cam.center_cam_loop,
        args=(frame_queue_center,),
        daemon=True
    ).start()
def start_detection():
    #threading.Thread(target=detecam_test.run, args=(0,frame_queue_l,frame_queue_r), daemon=True).start()
    return None

def generate_frames(queue):
    last_frame = None
    while True:
        if not queue.empty():
            data = queue.get()
            last_frame = data["frame"]

        if last_frame is None:
            time.sleep(0.01)
            continue


        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + last_frame + b'\r\n')
def create_app():
    app = Flask(__name__)
    app.secret_key = "test1234tfe2026"
    ADMIN_USERNAME= "admin"
    ADMIN_PASSWORD_HASH = 'scrypt:32768:8:1$4MyVq40Iqy22RZOT$b5c64a67cf5e43a243264136e0052c929522bbbb04549e164ef4a686a5b4933a8a0808eae1d73bd251353562ed6fcbd004d4575d20682912a681e4f9312781eb'
    # Configuration de la base de données
    app.config['DATABASE'] = os.path.join(app.instance_path, 'database.sqlite')

    # Crée le dossier instance si nécessaire
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialise le module db
    db.init_app(app)

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            return f(*args, **kwargs)

        return decorated_function

    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") != "admin":
                return redirect(url_for("blog"))
            return f(*args, **kwargs)

        return decorated_function

    @app.route("/api/sensors")
    def api_sensors():
        angles = []
        if not frame_queue_l.empty():
            data_l = frame_queue_l.get()
            angle_l = data_l.get("percent")
            if angle_l is not None:
                angles.append(-int(angle_l))
        if not frame_queue_r.empty():
            data_r = frame_queue_r.get()
            angle_r = data_r.get("percent")
            if angle_r is not None:
                angles.append(int(angle_r))
        data = {
            "movement_angle": angles,
            "object_count": angles,
            "depth": "Moyen",
            "cpu_usage":random.randint(0, 80),
        }
        return jsonify(data)

    @app.route("/sensors")
    def sensors():
        return render_template("sensors.html")
    #caméras
    @app.route("/mono_left")
    def mono_left():
        return Response(generate_frames(frame_queue_l),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/mono_right")
    def mono_right():
        return Response(generate_frames(frame_queue_r),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/hd_center")
    def hd_center():
        return Response(generate_frames(frame_queue_center),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            db_conn = get_db()
            user = db_conn.execute(
                "SELECT * FROM user WHERE username=?",
                (username,)
            ).fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                return redirect(url_for("blog"))

            flash("Identifiants incorrects", "error")

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("blog"))
    @app.route('/blog')
    def blog():
        db_conn = get_db()
        posts = db_conn.execute("""
                                SELECT post.*, user.username
                                FROM post
                                         JOIN user ON post.author_id = user.id
                                ORDER BY created DESC
                                """).fetchall()

        return render_template("blog.html", posts=posts)

    @app.route("/admin", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_panel():
        db_conn = get_db()

        if request.method == "POST":
            action = request.form.get("action")

            # 🔑 Modifier ses propres infos
            if action == "update_self":
                new_username = request.form["username"]
                new_password = request.form["password"]

                hashed = generate_password_hash(new_password)

                db_conn.execute(
                    "UPDATE user SET username=?, password=? WHERE id=?",
                    (new_username, hashed, session["user_id"])
                )
                db_conn.commit()

                session["username"] = new_username
                flash("Informations mises à jour", "success")

            # ➕ Créer un utilisateur
            if action == "create_user":
                username = request.form.get("username")
                password = request.form.get("password")
                role = request.form.get("role")

                hashed = generate_password_hash(password)

                try:
                    db_conn.execute(
                        "INSERT INTO user (username, password,role) VALUES (?, ?,?)",
                        (username, hashed,role)
                    )
                    db_conn.commit()
                    flash("Utilisateur créé", "success")
                except:
                    flash("Nom déjà utilisé", "error")

        users = db_conn.execute("SELECT * FROM user").fetchall()

        return render_template("admin.html", users=users)


    @app.route('/blog/create', methods=['GET', 'POST'])
    @login_required
    def create_post():

        if request.method == 'POST':
            title = request.form['title']
            body = request.form['body']

            db_conn = get_db()

            # Pour l'instant : user_id = 1 (temporaire)
            db_conn.execute(
                "INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)",
                (title, body, session["user_id"])
            )

            db_conn.commit()

            return redirect('/blog')

        return render_template("create_post.html")

    @app.route('/debug-posts')
    def debug_posts():
        db_conn = get_db()
        posts = db_conn.execute("SELECT * FROM post").fetchall()
        return str(posts)


    @app.route('/test-db')
    def test_db():
        db_conn = db.get_db()
        return "DB OK"

    @app.route('/')
    def acceuil():
        return render_template('acceuil.html')

    return app

# Pour lancer directement avec python app.py
if __name__ == "__main__":
    start_detection()
    start_center_camera()
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)