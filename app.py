import os
import requests
import tempfile
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import dropbox
from dropbox.exceptions import AuthError
import json

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Asegúrate de que la carpeta de subidas exista
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Firebase
FIREBASE_URL = 'https://military-docs-b008c-default-rtdb.firebaseio.com/usuarios.json'

# Dropbox credentials - Deberías usar un token de acceso permanente
DROPBOX_ACCESS_TOKEN = 'sl.u.AFs_RytDK-ZykfudBJrJbr0uHh3qnan4aFKKt9yychhGz61DccSMMN9vuADBM8yyWENHIJM2F2FmWIII5FKwdzSHoxo-vI2JRQ4z54tJvry30ifLJ3rUQrsgw5KTssAO1oJOmRtlXvvmmuSuuI8zTDIVFAWLcrRAMaBKCgSy3bPbL3YDc8rmzrFN4SMbGM4vi_0sNQKUEVOm-hmO3WuoKUiS1hL_KEXih4BoIIZlXC2LzUEVf_3WmvKS23-wX2vX9OnnOt9Roc_IRO_3P55GmNg2WzgKW_a7OZctFtaT5q4yAT89c2uwc-f5WsOuq5h6U1E3VCvAfgIDUM_l92FdPKk1cfNEXIUtDD40U5ni8MaoFjt9maH68pzeT_5vOqHXMBGlo-s4ANLtrEe_Vth71OASaZ_CG9-5241ZWOeTKwf4SgRvqigi32_wFszuQ_nY8oMjQjvKfy5YA3lxNqGNJ444bKH2ZZ8fHeGethZW79K6D4aQKk3SLokhqKagozSuKN0GCOB1AhnjTmR-1eHzxBLdXZfLdAp6e0E9JJXlbybItRAja8-L6RwVFCOKV_qhVCruZojAE2n1CmTdfr29rqun1FWNeAyVmBOCmBaIrplQUU0Qzk7qG65w9QLJNZg-Rs7o1upiwQ7EIr7qWp0izvpWIKik0qcDByKqKR1aTxUv0dXelt_5r6Uvww7B55lgW5ED1-F1pG696Sil3gkE7f1FwN2hVwD7ZSbdo1Y91BhhRMrIdrO4s31sEk8vfy4FteijhOTn2d7UWnvejH7soyGL4WLV1aVmU25L2z4dfm48RP9dyohOcEn_tsb_4L99hSp71j47w4oN58XTvrE9UEE5F_IBi-OJfs4Nh5sXUK4MpbykRRGN6xQrB9nbM4x6z1lRv1oY-Nw9zOy5615iLKR8BZANwARSy-kdZmTGzbiC0VaaO47gIp81elBzqn3TnTQM6LXy4Nd_lHABAGP5cn5ps-RajwtK-AaeOy5svMmWTd1DByxgrigrVGwS8az7dWEUDaYyET6l8eSOfjMNdJ6vhg5ab3EXpTO-RWEhF_Y3YTJlXLrPZaszQ5k5jzlU-mFRUGDLHPtyFOST2uvKzd-kUBJvSQnvRCioU1JJJ-tXN-_ZvUl3WyVmG4UPqGwvV8ZR0tGiiSNgrkKgarv4g8xAp64uoL3lLXa-287WEQL1OsUeWf_9tXdSUoGQfFbwAIp6Tkw0zxLDStt9heEEhe54SdrXepYFo1sDpJKrvKqhYID-7yPtiQyo_YLed9Os_uy43bzaii8l3vKv4TFyPfRrdThZXoOp8xeCjxWv_9qnisDNcxbv8I-N512u2mH_nJ-e436LO_FgfrlE6KHbL0El6MUuAfLpxDWTtggXyn_-WXWFKVqdPuxdBojTHp9okOlk0nB0q1a1joYJxH1dxtkF'

os.environ['DROPBOX_API_DISABLE_GRPC'] = 'True'

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
        print(f"Error obteniendo usuarios de Firebase: {e}")
        return {}

def save_user_firebase(email):
    try:
        user_data = {"email": email}
        response = requests.post(FIREBASE_URL[:-5] + '.json', json=user_data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error guardando usuario en Firebase: {e}")
        return False

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
        print(f"Error de autenticación con Dropbox: {e}")
        return None
    except Exception as e:
        print(f"Error al conectar con Dropbox: {e}")
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

def get_dropbox_files():
    """Función para obtener los archivos de Dropbox"""
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
            print(f"Error accediendo a Dropbox: {e}")
    
    return dropbox_files

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

    dropbox_files = get_dropbox_files()
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
        
        # Asegúrate de que la carpeta de subidas exista
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
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
                    
                    # Limpiar el archivo local después de subirlo
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    
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

@app.route('/preview/<path:file_id>')
def preview(file_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    # Normalizar el path del archivo
    if file_id.startswith('/'):
        file_id = file_id[1:]
    if not file_id.startswith('archivossubidos/'):
        file_id = 'archivossubidos/' + file_id
    
    dropbox_path = '/' + file_id
    
    try:
        dbx = get_dropbox_client()
        if dbx:
            # Obtener el enlace temporal
            temp_link = dbx.files_get_temporary_link(dropbox_path.lower())
            
            # Obtener la extensión del archivo
            file_extension = file_id.split('.')[-1].lower() if '.' in file_id else ''
            
            # Determinar el tipo de visualización basado en la extensión
            if file_extension in ['pdf']:
                # Los PDF se pueden mostrar directamente en el navegador
                return render_template('document_viewer.html', 
                                      doc_url=temp_link.link,
                                      doc_title=file_id.split('/')[-1],
                                      doc_type='pdf')
            elif file_extension in ['jpg', 'jpeg', 'png', 'gif']:
                # Las imágenes se pueden mostrar directamente
                return render_template('document_viewer.html', 
                                      doc_url=temp_link.link,
                                      doc_title=file_id.split('/')[-1],
                                      doc_type='image')
            elif file_extension in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                # Para documentos de Office, usamos el visor de Office Online o Google Docs
                office_url = f"https://view.officeapps.live.com/op/view.aspx?src={temp_link.link}"
                return redirect(office_url)
            else:
                # Para otros tipos de archivos, redirigir al enlace directo
                return redirect(temp_link.link)
                
    except Exception as e:
        print(f"Error visualizando documento {file_id}: {e}")
        flash(f'Error al visualizar el documento: {e}', 'error')
        return redirect(url_for('index'))
        
    flash('Documento no encontrado', 'error')
    return redirect(url_for('index'))
    
    # Redireccionar al enlace de vista previa
    return redirect(doc['url'])
    
@app.route('/get_document_url/<path:file_id>')
def get_document_url(file_id):
    if 'user' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
        
    # Normalizar el path del archivo
    if file_id.startswith('/'):
        file_id = file_id[1:]
    if not file_id.startswith('archivossubidos/'):
        file_id = 'archivossubidos/' + file_id
    
    dropbox_path = '/' + file_id
    
    try:
        dbx = get_dropbox_client()
        if dbx:
            # Intentar obtener un enlace con tiempo de expiración más largo
            # (15 minutos en lugar del valor predeterminado de 4 horas)
            temp_link = dbx.files_get_temporary_link(dropbox_path.lower())
            
            # Registra la URL para depuración
            print(f"URL generada para {file_id}: {temp_link.link}")
            
            return jsonify({
                "success": True,
                "url": temp_link.link,
                "filename": file_id.split('/')[-1]
            })
    except Exception as e:
        print(f"Error obteniendo URL del documento {file_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
        
    return jsonify({"success": False, "error": "Documento no encontrado"}), 404
    
# Para asegurar que la aplicación pueda ejecutarse en Render
if __name__ == "__main__":
    # Determina el puerto desde la variable de entorno (Render lo proporciona)
    port = int(os.environ.get('PORT', 5000))
    # En producción, evita usar debug=True
    app.run(host='0.0.0.0', port=port)
