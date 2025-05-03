import os
import requests
import tempfile
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
import dropbox
from dropbox.exceptions import AuthError

app = Flask(__name__)
app.secret_key = 'super_secret_key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Firebase
FIREBASE_URL = 'https://military-docs-b008c-default-rtdb.firebaseio.com/usuarios.json'

# Dropbox credentials
DROPBOX_ACCESS_TOKEN = 'sl.u.AFskRTWnEhk_ykUiBllabSgnfE-vZrpV9zZuO1VimL15Bal5g6h9-_jCivFH25lw5REiNwA4CcyFjyj7UroriGso0FxQDtB1XRu8uJNYVsqjTkUh65gcGAf-U_4EX7LAzyP3ajRZU7kRRh2XbGL2bMVS4UhVzq6TdA1pNrbsq9CJgWPO64NoR86a1yYx-hNC2pgB0-Zq8pVPRNvm4RbeNTbZOgVbqLubMsxJHalUJGBSbPydicLplagd-YePDUXY-kOw5-wCrlHAjgTGZB1ZE8gQA3Y4hKO-BgdsjE9EcT_R9IbwvFnLWyDn-rjfkgPuk_rhU0FsL1du5D4nSkQQuVYnjqHWjJPn-5anSMhcxhp90rhMaMwyICxHdVNmZFaqL2jvlbEgZZNuZT2fxZFYJfBKrsznyZzqu1Vf2ymf9KkmxZIVDlWX9-p7xm-gCH3PwzO_S4_eA3SHz9ArKVDpudwISYSpN1d6G1zSiZqdJAl0rrTdgfffGoxeH6lio80Ms4ENEoe-zDrodQMoHWGadoAmhTh16hCZygnrgd5Tss2ShN_N_8nUK76jNjsbol2-hcnB32KNb8zwehbe66tAFxhDqDPZPZs8jIPBmLdDcpfd3J0D4pLrKBJWaYX3dD5kiwJopGFRt-VbvLh8qKP8BThF47zKuI8Fazz5qmj1HRUK27M5T_wp7icTGrsMRnug3jwwAGgcrtNp-wNVAzfUIk7ku-pbwbqzbWdGBNCVa1Rd7zp1Psb0eBynUGjXpmwLCwhFjYER0lmSlS2qn9IgbzT7rt1oiEBe1DqAMKfa6DirYMuecsrL_4FZ3ateqMKiMfBtgfJ-ac1YUEbwkkfAoPN3EcNiTq1-AqOJ52AVnzOu0m67MW5xkt0Cl1vNJRS3RBoUEE-o7doaGR91AUao0r7jpSH9T-e06PLE3aL-PsptUqw9xF3QgMH49sHbqmhzBB698DOB04qTxQnQe3sholsu08YitfT72g2R9JtaOZcvQ1puJDHqDk98HDTk0nHROU_eGpoT9il6RYXMPLkYhJBtbJ-dSs0UAVuRjvQVPby3Q5QLlvCMIhgj1ce88sJDR28UdouiC-O4ehjPC6tNsVin8u7GM-LZgDZ4ghD4M6_-VSggzCx4WP8Pq9gy2Vc5gePRmEi2Ox6s-M2wTHPdU34OasqDOBjrABQg3Es4rm5o_6QRfWAh7mm3Bwu6Ene3gWCBuefS6lro4EUqsw13_KU4Tf3dpxfn00O5D0rNqUnRCE9A3UzbOjTBgcadptoAwcVO_qD9-DqykK-N-lj6Nq1EgZE3eJP2jYcdDA00ajxc1KtQ35_bLisTDfXHsgKsKgYeSOvqTh4pHfRDR-7IqGLId0wV0ydz3Ore8vt-JzhZFnf0OseG7tMqTiuV_8Zp7TYuZdr7AWxcc-5AK6WmuMoi'

# Initialize Dropbox client
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

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

def get_or_create_dropbox_folder(folder_name):
    try:
        # Check if the folder exists in Dropbox
        folder_metadata = dbx.files_get_metadata('/' + folder_name)
        print(f"Carpeta '{folder_name}' ya existe en Dropbox")
        return folder_metadata
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_conflict():
            print(f"Error creando la carpeta: {e}")
            return None
        else:
            # Create folder if it doesn't exist
            dbx.files_create_folder_v2('/' + folder_name)
            print(f"Carpeta '{folder_name}' creada en Dropbox")
            return dbx.files_get_metadata('/' + folder_name)

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
    try:
        folder_metadata = get_or_create_dropbox_folder("ArchivosSubidos")
        if folder_metadata:
            # Get all files in the folder
            result = dbx.files_list_folder('/ArchivosSubidos')
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    dropbox_files.append({
                        'title': entry.name,
                        'file_id': entry.id,
                        'url': dbx.files_get_temporary_link(entry.id).link
                    })
    except AuthError as e:
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
        file.save(filepath)
        flash('Archivo subido localmente', 'success')

        try:
            # Upload to Dropbox
            with open(filepath, 'rb') as f:
                file_path = '/ArchivosSubidos/' + filename
                dbx.files_upload(f.read(), file_path, mute=True)
                print(f"Archivo subido a Dropbox: {filename}")
            os.remove(filepath)
            flash('Archivo también subido a Dropbox', 'success')
        except Exception as e:
            flash(f'Error subiendo a Dropbox: {e}', 'error')

    return redirect(url_for('index'))

@app.route('/preview/<file_id>')
def preview(file_id):
    try:
        # Get the temporary link for the file to preview it
        link = dbx.files_get_temporary_link(file_id).link
        return redirect(link)
    except Exception as e:
        return f"Error al obtener el archivo: {e}", 400

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)


