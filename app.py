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
# NOTA: Este token parece ser un token de corta duración que puede haber expirado
# Recomendamos obtener un nuevo token de larga duración desde la consola de desarrolladores de Dropbox
DROPBOX_ACCESS_TOKEN = 'tu_token_de_dropbox_aquí'

# Inicializar el cliente de Dropbox en cada solicitud para manejar reconexiones
def get_dropbox_client():
    try:
        dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        # Prueba la conexión
        dbx.users_get_current_account()
        return dbx
    except AuthError:
        flash("Error de autenticación con Dropbox. El token puede haber expirado.", 'error')
        return None
    except Exception as e:
        flash(f"Error al conectar con Dropbox: {e}", 'error')
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_users_firebase():
    try:
        response = requests.get(FIREBASE_URL)
        if response.status_code == 200 and response.json() is not None:
            return response.json()
        else:
            return {}
    except Exception as e:
        flash(f"Error al conectar con Firebase: {e}", 'error')
        return {}

def save_user_firebase(email):
    try:
        user_data = {"email": email}
        response = requests.post(FIREBASE_URL[:-5] + '.json', json=user_data)
        return response.status_code == 200
    except Exception as e:
        flash(f"Error al guardar usuario en Firebase: {e}", 'error')
        return False

def get_or_create_dropbox_folder(dbx, folder_name):
    if not dbx:
        return None
        
    try:
        # Verificar si la carpeta existe en Dropbox
        try:
            folder_metadata = dbx.files_get_metadata('/' + folder_name)
            print(f"Carpeta '{folder_name}' ya existe en Dropbox")
            return folder_metadata
        except dropbox.exceptions.ApiError:
            # Crear carpeta si no existe
            folder = dbx.files_create_folder_v2('/' + folder_name)
            print(f"Carpeta '{folder_name}' creada en Dropbox")
            return folder.metadata
    except Exception as e:
        print(f"Error al crear/obtener carpeta en Dropbox: {e}")
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
            folder_metadata = get_or_create_dropbox_folder(dbx, "ArchivosSubidos")
            if folder_metadata:
                # Obtener todos los archivos en la carpeta
                result = dbx.files_list_folder('/ArchivosSubidos')
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        try:
                            # Obtener enlace temporal para el archivo
                            temp_link = dbx.files_get_temporary_link(entry.path_lower)
                            dropbox_files.append({
                                'title': entry.name,
                                'file_id': entry.path_lower,  # Usar path en lugar de ID
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
        
        # Asegurarse de que la carpeta de subidas exista
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        file.save(filepath)
        
        dbx = get_dropbox_client()
        if dbx:
            try:
                # Subir a Dropbox
                folder = get_or_create_dropbox_folder(dbx, "ArchivosSubidos")
                if folder:
                    with open(filepath, 'rb') as f:
                        file_path = '/ArchivosSubidos/' + filename
                        dbx.files_upload(f.read(), file_path, mode=dropbox.files.WriteMode.overwrite)
                        print(f"Archivo subido a Dropbox: {filename}")
                    flash('Archivo subido correctamente a Dropbox', 'success')
                else:
                    flash('No se pudo crear la carpeta en Dropbox', 'error')
            except Exception as e:
                flash(f'Error subiendo a Dropbox: {e}', 'error')
            finally:
                # Eliminar el archivo local después de subir
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Error conectando con Dropbox. El archivo solo se guardó localmente.', 'warning')

    else:
        flash(f'Tipo de archivo no permitido. Formatos permitidos: {", ".join(ALLOWED_EXTENSIONS)}', 'error')

    return redirect(url_for('index'))

@app.route('/preview/<path:file_id>')
def preview(file_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    dbx = get_dropbox_client()
    if not dbx:
        flash('Error conectando con Dropbox', 'error')
        return redirect(url_for('index'))
        
    try:
        # Obtener el enlace temporal para el archivo para previsualizarlo
        temp_link = dbx.files_get_temporary_link(file_id)
        return redirect(temp_link.link)
    except Exception as e:
        flash(f"Error al obtener el archivo: {e}", 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)


