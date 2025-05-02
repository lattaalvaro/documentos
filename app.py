import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from boxsdk import OAuth2, Client

app = Flask(__name__)
app.secret_key = 'super_secret_key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

FIREBASE_URL = 'https://military-docs-b008c-default-rtdb.firebaseio.com/usuarios.json'
CLIENT_ID = 'xmwe4k8mabm488z87nj07cyqtc4wtplt'
CLIENT_SECRET = 'Az8Zyr85ehEXe5HgkNa7kXgM3I82iZKL'
REDIRECT_URI = 'https://documentosmilitares.onrender.com/callback'

box_oauth = OAuth2(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_users_firebase():
    response = requests.get(FIREBASE_URL)
    return response.json() if response.status_code == 200 and response.json() else {}

def save_user_firebase(email):
    user_data = {"email": email}
    response = requests.post(FIREBASE_URL[:-5] + '.json', json=user_data)
    return response.status_code == 200

def create_box_folder(client, folder_name):
    try:
        return client.folder('0').create_subfolder(folder_name)
    except Exception as e:
        print(f"Error creando la carpeta: {e}")
        return None

def get_or_create_box_folder(client, folder_name):
    try:
        items = client.folder('0').get_items()
        for item in items:
            if item.name == folder_name and item.type == 'folder':
                return item
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
            for user_info in users.values():
                if user_info.get('email') == email:
                    session['user'] = email
                    return redirect(url_for('index'))
            flash('Correo no registrado. Regístrate primero.', 'error')
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
            for user_info in users.values():
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
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    box_files = []
    if 'box_access_token' in session:
        try:
            oauth = OAuth2(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                access_token=session['box_access_token'],
                refresh_token=session['box_refresh_token'],
                store_tokens=lambda a, r: session.update({'box_access_token': a, 'box_refresh_token': r})
            )
            client = Client(oauth)
            folder = get_or_create_box_folder(client, "ArchivosSubidos")
            if folder:
                for item in folder.get_items():
                    if item.type == 'file':
                        shared_link = client.file(item.id).get_shared_link(access='open')
                        box_files.append({
                            'title': item.name,
                            'file_id': item.id,
                            'embed_url': f"https://app.box.com/embed/s/{shared_link.split('/')[-1]}"
                        })
        except Exception as e:
            flash(f"Error accediendo a Box: {e}", 'error')

    return render_template('index.html', box_files=box_files)

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

        if 'box_access_token' in session:
            try:
                oauth = OAuth2(
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                    access_token=session['box_access_token'],
                    refresh_token=session['box_refresh_token'],
                    store_tokens=lambda a, r: session.update({'box_access_token': a, 'box_refresh_token': r})
                )
                client = Client(oauth)
                folder = get_or_create_box_folder(client, "ArchivosSubidos")
                if folder:
                    with open(filepath, 'rb') as f:
                        folder.upload_stream(f, filename)
                    os.remove(filepath)
                    flash('Archivo también subido a Box', 'success')
            except Exception as e:
                flash(f'Error subiendo a Box: {e}', 'error')

    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return 'No se recibió ningún código de Box.', 400
    try:
        access_token, refresh_token = box_oauth.authenticate(code)
        session['box_access_token'] = access_token
        session['box_refresh_token'] = refresh_token
        flash('Conectado con Box correctamente.', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        return f"Error al intercambiar el código por tokens: {e}", 500

@app.route('/embed/<file_id>')
def embed_view(file_id):
    if 'box_access_token' not in session:
        return jsonify({'error': 'No autorizado'}), 403
    try:
        oauth = OAuth2(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            access_token=session['box_access_token'],
            refresh_token=session['box_refresh_token'],
            store_tokens=lambda a, r: session.update({'box_access_token': a, 'box_refresh_token': r})
        )
        client = Client(oauth)
        file = client.file(file_id)
        shared_link = file.get_shared_link(access='open')
        return jsonify({
            'embed_url': f"https://app.box.com/embed/s/{shared_link.split('/')[-1]}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
