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
DROPBOX_ACCESS_TOKEN = 'sl.u.AFu0tr8X9h32v-i4nrNFW9E0eESK76cmqgS1jHEnRsQYcc9UxTWtvcCPVpvPafWWnxhfKch8Z3DRwCf5spsDlfRVrJn23w1XfcQ-wTNl3lMjoTWLsJ_drWRLFTnKAg9Cv-SuMQJh0Fj9KC8abwDBGWH027cdaUxsl_NfBL6f166k1khR6RaFXOlICjrS0HXcZ7XK3VIPTFdmgyM6PcfYH-aODiQQeZJyITtCZua8R4G6mznxVywY2bqcQJQciK7AFDgICwhISCflVPpAL-rcgIXpPdlDJ3txWu9ln_wUdytEo3lZBuyk2jPTqGVz3A4vj8I6ZqSyr1GNSuKJrST9I4lKhokQ1WppJj92qpGcMHl8Za-h9gyioBZPR5F260l6EdAwEwrcmf70qKOQSTvBkc3iuwAC6qGOoIyD8fpSJokfXbvuGvJOLHDPXeMRm_6gXy_pizDc8LYeo0vPMzl_EFpXK1Or1nLrCtvnsbBMtb_kFCV8H6E8w6Z8rM0YeFMthkZadk1lSOLtikdnpMyKV1XttmaZABgYn70BARLoS-A9VKSIxojCx2NJQgdOsneHNOFEeEMDrT6wLvT7DkO3F-JhEmq_oAliqtZ1AStVZBHb5ieapeqXFCsd1HcR0HAMHSmC_6dXhJAYPV3yjDd22yMoW9rSbrsPL9hHgueOo-Kt8YqHXVX_ke3uN56qUPn_cafbTCofoyzxSKN0TRxFQIR1vud1teCnoPM4PmWMIwQte4t0mras6AL_I6SlcBgqK_-f9nwuh15NIPdeYLsBNOb3GRz185oH75kkr1FdG9qdMJyc9FDrFH1thaONrLEYkaF-zGTLBZa_9SfwpAhvYYRRbC0tk71Nun1IRK23_qmGYb-OkH-9mOxYL1uIdNOcZoHcvdF_qG5QFcRqUzGQQcY8JGtJpXN09xv8nTt4_3Sr_tqTya23REuMSrd3fgNCK_U-LxGlV5gPCrnPBNnGnjMGApn3LEak9BXcE1D1mT92g7qfRLJ_U5DPDhmVazkeBK--Qz_KvDd4GLG83oTZlxkIEp0LoHKz-rKQ5Q6st1TetTXYENFbOdh65R8MIWHqz16hds2AvUSzx2b1aJn8iER84gxy43hUaeUZCohyldpnwrHevHXjroiLzitDPDuz_2CurXwQz-eRXUGIf1in0167kJIZ9Tm-ZHdT7BD4_2GsRSzIYdaGYh4BEXBTbw9-Jt0F2aItE3xG7w1UBHl0PDOoKyhU_WXfoJ86z1CeFNQ5LkO2gGU8KEJ9v3ZUAfjbHvmDdLvkO6SYFf2Ro0RzPYvk1FWUAT7LCaarJI1Z0stCTK2OjkiqlOQV-I2ogCKC-NtxVShxzda6mI3RcwcTAi_1Qx85HlBS2JUXkwBE0qWj34iI4ZReNpS9ahEL8hXari44fEfteUA0f2PNbVYXvvxJ'

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


