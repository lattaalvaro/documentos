import os
import requests
import tempfile
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
import dropbox
from dropbox.exceptions import AuthError
import json

app = Flask(__name__)
app.secret_key = 'super_secret_key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Firebase
FIREBASE_URL = 'https://military-docs-b008c-default-rtdb.firebaseio.com/usuarios.json'

# Dropbox credentials
DROPBOX_ACCESS_TOKEN = 'sl.u.AFskRTWnEhk_ykUiBllabSgnfE-vZrpV9zZuO1VimL15Bal5g6h9-_jCivFH25lw5REiNwA4CcyFjyj7UroriGso0FxQDtB1XRu8uJNYVsqjTkUh65gcGAf-U_4EX7LAzyP3ajRZU7kRRh2XbGL2bMVS4UhVzq6TdA1pNrbsq9CJgWPO64NoR86a1yYx-hNC2pgB0-Zq8pVPRNvm4RbeNTbZOgVbqLubMsxJHalUJGBSbPydicLplagd-YePDUXY-kOw5-wCrlHAjgTGZB1ZE8gQA3Y4hKO-BgdsjE9EcT_R9IbwvFnLWyDn-rjfkgPuk_rhU0FsL1du5D4nSkQQuVYnjqHWjJPn-5anSMhcxhp90rhMaMwyICxHdVNmZFaqL2jvlbEgZZNuZT2fxZFYJfBKrsznyZzqu1Vf2ymf9KkmxZIVDlWX9-p7xm-gCH3PwzO_S4_eA3SHz9ArKVDpudwISYSpN1d6G1zSiZqdJAl0rrTdgfffGoxeH6lio80Ms4ENEoe-zDrodQMoHWGadoAmhTh16hCZygnrgd5Tss2ShN_N_8nUK76jNjsbol2-hcnB32KNb8zwehbe66tAFxhDqDPZPZs8jIPBmLdDcpfd3J0D4pLrKBJWaYX3dD5kiwJopGFRt-VbvLh8qKP8BThF47zKuI8Fazz5qmj1HRUK27M5T_wp7icTGrsMRnug3jwwAGgcrtNp-wNVAzfUIk7ku-pbwbqzbWdGBNCVa1Rd7zp1Psb0eBynUGjXpmwLCwhFjYER0lmSlS2qn9IgbzT7rt1oiEBe1DqAMKfa6DirYMuecsrL_4FZ3ateqMKiMfBtgfJ-ac1YUEbwkkfAoPN3EcNiTq1-AqOJ52AVnzOu0m67MW5xkt0Cl1vNJRS3RBoUEE-o7doaGR91AUao0r7jpSH9T-e06PLE3aL-PsptUqw9xF3QgMH49sHbqmhzBB698DOB04qTxQnQe3sholsu08YitfT72g2R9JtaOZcvQ1puJDHqDk98HDTk0nHROU_eGpoT9il6RYXMPLkYhJBtbJ-dSs0UAVuRjvQVPby3Q5QLlvCMIhgj1ce88sJDR28UdouiC-O4ehjPC6tNsVin8u7GM-LZgDZ4ghD4M6_-VSggzCx4WP8Pq9gy2Vc5gePRmEi2Ox6s-M2wTHPdU34OasqDOBjrABQg3Es4rm5o_6QRfWAh7mm3Bwu6Ene3gWCBuefS6lro4EUqsw13_KU4Tf3dpxfn00O5D0rNqUnRCE9A3UzbOjTBgcadptoAwcVO_qD9-DqykK-N-lj6Nq1EgZE3eJP2jYcdDA00ajxc1KtQ35_bLisTDfXHsgKsKgYeSOvqTh4pHfRDR-7IqGLId0wV0ydz3Ore8vt-JzhZFnf0OseG7tMqTiuV_8Zp7TYuZdr7AWxcc-5AK6WmuMoi'

os.environ['DROPBOX_API_DISABLE_GRPC'] = 'True'

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

def get_dropbox_client():
    try:
        dbx = dropbox.Dropbox(
            oauth2_access_token=DROPBOX_ACCESS_TOKEN,
            session=dropbox.create_session(max_connections=8),
            user_agent="MilitaryDocsApp/1.0"
        )
        dbx.users_get_current_account()
        return dbx
    except AuthError as e:
        flash(f"Error de autenticación con Dropbox: {e}", 'error')
        return None
    except Exception as e:
        flash(f"Error al conectar con Dropbox: {e}", 'error')
        return None

def get_or_create_dropbox_folder(folder_name):
    dbx = get_dropbox_client()
    if not dbx:
        return None
    try:
        try:
            folder_metadata = dbx.files_get_metadata('/' + folder_name)
            return folder_metadata
        except dropbox.exceptions.ApiError:
            folder = dbx.files_create_folder_v2('/' + folder_name)
            return folder.metadata
    except Exception as e:
        print(f"Error creando/obteniendo carpeta en Dropbox: {e}")
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
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    dropbox_files = []
    dbx = get_dropbox_client()
    
    if dbx:
        try:
            folder_metadata = get_or_create_dropbox_folder("ArchivosSubidos")
            if folder_metadata:
                result = dbx.files_list_folder('/ArchivosSubidos')
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        try:
                            temp_link = dbx.files_get_temporary_link(entry.path_lower)
                            dropbox_files.append({
                                'title': entry.name,
                                'file_id': entry.path_lower,
                                'url': temp_link.link
                            })
                        except Exception as e:
                            print(f"Error obteniendo enlace para {entry.name}: {e}")
        except Exception as e:
            flash(f"Error accediendo a Dropbox: {e}", 'error')

    return render_template('index.html', dropbox_files=dropbox_files)

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
        
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        file.save(filepath)
        
        dbx = get_dropbox_client()
        if dbx:
            try:
                folder_metadata = get_or_create_dropbox_folder("ArchivosSubidos")
                if folder_metadata:
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    file_path = '/ArchivosSubidos/' + filename
                    upload_result = dbx.files_upload(
                        content, 
                        file_path, 
                        mode=dropbox.files.WriteMode.overwrite
                    )
                    
                    flash('Archivo subido correctamente a Dropbox', 'success')
                else:
                    flash('No se pudo crear la carpeta en Dropbox', 'error')
            except Exception as e:
                flash(f'Error al subir el archivo a Dropbox: {e}', 'error')
        else:
            flash('No se pudo conectar a Dropbox', 'error')
        
        return redirect(url_for('index'))
    else:
        flash('Tipo de archivo no permitido', 'error')
        return redirect(url_for('index'))

@app.route('/preview/<file_id>')
def preview(file_id):
    # Aquí puedes obtener el documento según el file_id
    doc = next((doc for doc in dropbox_files if doc['file_id'] == file_id), None)
    if doc is None:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('index'))
    return render_template('index.html', doc=doc)

if __name__ == "__main__":
    app.run(debug=True)
