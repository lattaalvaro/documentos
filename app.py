import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from werkzeug.utils import secure_filename
import requests
from boxsdk import OAuth2, Client

app = Flask(__name__)
app.secret_key = 'super_secret_key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Firebase
FIREBASE_URL = 'https://military-docs-b008c-default-rtdb.firebaseio.com/usuarios.json'

# Box credentials
CLIENT_ID = 'p0g0j6agqo7sf8no0y4t90vg2clyghla'
CLIENT_SECRET = 'rb4W92KieIUz3x2eQqIMHncWaPZcGDEw'
REDIRECT_URI = 'https://documentosmilitares.onrender.com/callback'

box_oauth = OAuth2(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_users_firebase():
    response = requests.get(FIREBASE_URL)
    if response.status_code == 200 and response.json() is not None:
        return response.json()
    else:
        return {}

def save_user_firebase(email):
    user_data = {"email": email}
    response = requests.post(FIREBASE_URL[:-5] + '.json', json=user_data)
    return response.status_code == 200

# Crear una carpeta en Box
def create_box_folder(client, folder_name):
    try:
        # Crear una carpeta en la raíz (root folder) de Box
        folder = client.folder('0').create_subfolder(folder_name)
        print(f"Carpeta '{folder_name}' creada en Box")
        return folder
    except Exception as e:
        print(f"Error creando la carpeta: {e}")
        return None

# Verificar si la carpeta ya existe
def get_or_create_box_folder(client, folder_name):
    try:
        # Buscar la carpeta por nombre
        items = client.folder('0').get_items()
        for item in items:
            if item.name == folder_name and item.type == 'folder':
                print(f"Carpeta '{folder_name}' ya existe en Box")
                return item  # Si la carpeta existe, la devolvemos

        # Si la carpeta no existe, crearla
        return create_box_folder(client, folder_name)
    except Exception as e:
        print(f"Error buscando o creando la carpeta: {e}")
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        if email and email.endswith('@ejercito.mil.co'):
            users = get_users_firebase()
            if users:
                for user_id, user_info in users.items():
                    if user_info.get('email') == email:
                        session['user'] = email
                        return redirect(url_for('index'))
            flash('Correo no registrado. Regístrate primero.', 'error')
            return redirect(url_for('login'))
        else:
            flash('Solo se permiten correos @ejercito.mil.co', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        if email and email.endswith('@ejercito.mil.co'):
            users = get_users_firebase()
            if users:
                for user_id, user_info in users.items():
                    if user_info.get('email') == email:
                        flash('Este correo ya está registrado.', 'error')
                        return redirect(url_for('register'))
            save_user_firebase(email)
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Solo se permiten correos @ejercito.mil.co', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('box_access_token', None)
    session.pop('box_refresh_token', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    docs = []
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        ext = file.rsplit('.', 1)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            docs.append({
                'title': file,
                'filename': file,
                'is_pdf': ext == 'pdf',
                'description': 'Documento cargado localmente',
                'downloadable': True
            })

    box_files = []
    if 'box_access_token' in session:
        oauth = OAuth2(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            access_token=session['box_access_token'],
            refresh_token=session['box_refresh_token'],
        )
        client = Client(oauth)
        root_folder = client.folder('0').get_items()
        for item in root_folder:
            box_files.append({
                'title': item.name,
                'id': item.id,
                'description': 'Archivo en Box'
            })

    return render_template('index.html', docs=docs, box_files=box_files)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect(url_for('login'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('index'))

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        flash('Archivo subido localmente', 'success')

        # Subida opcional a Box si hay token
        if 'box_access_token' in session:
            oauth = OAuth2(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                access_token=session['box_access_token'],
                refresh_token=session['box_refresh_token'],
            )
            client = Client(oauth)

            # Obtener la carpeta de Box o crearla si no existe
            folder_name = "ArchivosSubidos"  # El nombre de la carpeta en Box
            folder = get_or_create_box_folder(client, folder_name)

            # Subir archivo a la carpeta obtenida
            if folder:
                with open(filepath, 'rb') as f:
                    uploaded_item = folder.upload_stream(f, filename)
                    print(f"Archivo subido a Box: {uploaded_item.name}")
                os.remove(filepath)  # ✅ Borra el archivo local
                flash('Archivo también subido a Box', 'success')

    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    code = request.args.get('code')
    access_token, refresh_token = box_oauth.authenticate(code)
    session['box_access_token'] = access_token
    session['box_refresh_token'] = refresh_token
    flash('Conectado con Box correctamente.', 'success')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
