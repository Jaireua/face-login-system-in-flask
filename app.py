# Import libreries
from flask import Flask, render_template, redirect, session, request, flash
from werkzeug.security import check_password_hash, generate_password_hash
from base64 import b64decode
import face_recognition
import mysql.connector
import secrets
import zlib
import os

# New instance flask
app = Flask(__name__)

# Setting database
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "whoami"
app.config["MYSQL_DB"] = "database"
app.config["SECRET_KEY"] = secrets.token_bytes(16)

# Connection database
cnx = mysql.connector.connect (
    host = app.config["MYSQL_HOST"],
    user = app.config["MYSQL_USER"],
    password = app.config["MYSQL_PASSWORD"],
    database = app.config["MYSQL_DB"],
    charset = "utf8mb4",
    collation = "utf8mb4_unicode_ci"
)

# Create table
cursor = cnx.cursor()
query = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    hash VARCHAR(255) NOT NULL
    )
"""
cursor.execute(query)
cnx.commit()

# Define routes
@app.route("/")
def index():
    return redirect("login")

@app.route("/login", methods=["GET", "POST"])
def login():
    # Clear session existing
    session.clear()
    # Check if from existing
    if request.method == "POST":
        input_username = request.form.get("username")
        input_password = request.form.get("password")
        # Validate field input
        if not input_username:
            return render_template("login.html", messager=1)
        elif not input_password:
            return render_template("login.html", messager=2)
        # Create cursor to return dictionary
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s",(input_username,))
        user = cursor.fetchone()
        # Validate credencials user
        if user is None or not check_password_hash(user["hash"], input_password):
            return render_template("login.html", messager=3)
        session["user_id"] = user["id"]
        return redirect("/admin")
    return render_template("login.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Get data user
        input_username = request.form.get("username")
        input_password = request.form.get("password")
        input_confirmation = request.form.get("confirmation")
        # Validate data user
        if not input_username:
            return render_template("register.html", messager=1)
        elif not input_password:
            return render_template("register.html", messager=2)
        elif not input_confirmation:
            return render_template("register.html", messager=4)
        elif input_password != input_confirmation:
            return render_template("register.html", messager=3)
       # Create cursor database
        cursor = cnx.cursor()
        cursor.execute("SELECT username FROM users WHERE username = %s", (input_username,))
        if cursor.fetchone():
            return render_template("register.html", messager=5)
        # Generate hashed password
        hash_password = generate_password_hash(input_password, method='pbkdf2:sha256', salt_length=8)
        cursor.execute('INSERT INTO users (username, hash) VALUES (%s, %s)', (input_username, hash_password))
        cnx.commit()
        new_user_id = cursor.lastrowid
        # Saving id user
        session["user_id"] = new_user_id
        flash(f"Usuario registrado como {input_username}")
        return redirect("/admin")
    return render_template("register.html")

import cv2
import mediapipe as mp

# Mostramos el video en RT
def gen_frame():
    # Realizamos la Videocaptura
    cap = cv2.VideoCapture(0)
    
    # Empezamos
    while True:
        # Leemos la VideoCaptura
        ret, frame = cap.read()

        # Si tenemos un error
        if not ret:
            break
        else:
            # Correccion de color
            frameRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Observamos los resultados
            resultados = MallaFacial.process(frameRGB)

            # Si tenemos rostros
            if resultados.multi_face_landmarks:
                for rostros in resultados.multi_face_landmarks:
                    # Obtener las coordenadas del rostro
                    h, w, _ = frame.shape
                    x_min = int(min([landmark.x for landmark in rostros.landmark]) * w)
                    x_max = int(max([landmark.x for landmark in rostros.landmark]) * w)
                    y_min = int(min([landmark.y for landmark in rostros.landmark]) * h)
                    y_max = int(max([landmark.y for landmark in rostros.landmark]) * h)

                    # Dibujar un cuadrado alrededor del rostro
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)

            # Codificamos nuestro video en Bytes
            suc, encode = cv2.imencode('.jpg', frame)
            frame = encode.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    # Liberamos la cámara
    cap.release()

@app.route("/facereg", methods=["GET", "POST"])
def facesetup():
    if request.method == "POST":
        # Get and encode the image
        encoded_image = (request.form.get("pic") + "==").encode('utf-8')
        # Create cursor database
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE id = %s", (session["user_id"],))
        user = cursor.fetchone()
        # If the user is not found, displat an error message
        if not user:
            flash("⚠️ Usuario no encontrado. Por favor, inicia sesión nuevamente.", category="danger")
            return render_template("face.html")
        id_ = user["id"]
        compressed_data = zlib.compress(encoded_image, 9)
        uncompressed_data = zlib.decompress(compressed_data)
        decoded_data = b64decode(uncompressed_data)
        file_path = f'./static/face/{id_}.jpg'
        # Upload image for facial recognition
        try:
            with open(file_path, 'wb') as new_image_handle:
                new_image_handle.write(decoded_data)
        except IOError:
            flash("❌ Error al guardar la imagen. Por favor, intenta nuevamente.", category="danger")
            return render_template("face.html")
        try:
            image = face_recognition.load_image_file(file_path)
            face_encodings = face_recognition.face_encodings(image)
            if not face_encodings:
                os.remove(file_path)
                flash("🔍 Imagen no clara. Asegúrate de que tu rostro esté bien iluminado y visible.", category="warning")
                return render_template("face.html")
        except Exception as e:
            flash("⚠️ Error al procesar la imagen. Por favor, intenta nuevamente.")
            return render_template("face.html")
        flash("✅ Imagen capturada correctamente. ¡Listo para continuar!", category="success")
        return redirect("/admin")
    return render_template("face.html")

@app.route("/facesetup", methods=["GET", "POST"])
def facereg():
    # Clear login
    session.clear()
    if request.method == "POST":
        encoded_image = (request.form.get("pic") + "==").encode('utf-8')
        username = request.form.get("name")
        # Create cursor database
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        # If the user is not found. Show error message
        if not user:
            flash("⚠️ Usuario no encontrado. Por favor, comuníquese con el admistrador.", category="warning")
            return render_template("camera.html")
        # Get the id of the found user
        id_ = user['id']
        compressed_data = zlib.compress(encoded_image, 9)
        uncompressed_data = zlib.decompress(compressed_data)
        decoded_data = b64decode(uncompressed_data)
        dir_path = './static/face/unknown/'
        file_path = os.path.join(dir_path, f'{id_}.jpg')
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        # Upload unknown images for facial recognition
        try:
            with open(file_path, 'wb') as new_image_handle:
                new_image_handle.write(decoded_data)
        except IOError:
            flash("❌ Error al guardar la imagen. Por favor, intenta nuevamente.", category="danger")
            return render_template("camera.html")
        try:
            registered_image = face_recognition.load_image_file(f'./static/face/{id_}.jpg')
            registered_face_encodings = face_recognition.face_encodings(registered_image)
            if not registered_face_encodings:
                flash("🔍 Imagen no clara. Asegúrate de que tu rostro esté bien iluminado y visible.", category="warning")
                return render_template("camera.html")
            registered_face_encoding = registered_face_encodings[0]
        except FileNotFoundError:
            flash("❌ Usuario incorrecto. Por favor, vuelve a seleccionar tu nombre de usuario.", category="danger")
            return render_template("camera.html")
        try:
            unknown_image = face_recognition.load_image_file(file_path)
            unknown_face_encodings = face_recognition.face_encodings(unknown_image)
            if not unknown_face_encodings:
                flash("🔍 Imagen no clara. Asegúrate de que tu rostro esté bien iluminado y visible.", category="warning")
                return render_template("camera.html")
            unknown_face_encoding = unknown_face_encodings[0]
        except FileNotFoundError:
            flash("❌ Error al cargar la imagen. Asegúrate de que la imagen se haya guardado correctamente.", category="danger")
            return render_template("camera.html")
        # Compare face with a precese threshold
        face_distances = face_recognition.face_distance([registered_face_encoding], unknown_face_encoding)
        if len(face_distances) > 0 and face_distances[0] < 0.4:  
            session["user_id"] = user["id"]
            return redirect("/admin")
        else:
            flash("🚫 Rostro incorrecto. Acceso denegado.", category="danger")
            return render_template("camera.html")
    return render_template("camera.html")

# Inicialize web
if __name__ == "__main__":
    app.run(debug=True)