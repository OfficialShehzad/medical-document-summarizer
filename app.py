from flask import Flask, request, jsonify, send_from_directory, render_template, json, redirect, url_for, session, stream_with_context, Response, flash
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import requests
import os
import io
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from models import db, Login, User, Document, MedicalProfessional, ChatBot, ProfessionalChat, ProfessionalMessage
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical_document_summarizer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'medical_document_summarizer_secret_key';

db.init_app(app)

# Uncomment the following lines to create the database and tables
with app.app_context():
    db.create_all()

    # Check if admin already exists
    existing_admin = Login.query.filter_by(user_type='admin').first()
    if not existing_admin:
        admin_login = Login(
            email='admin@example.com',
            password=generate_password_hash('admin123'),  # hashed password
            user_type='admin'
        )
        db.session.add(admin_login)
        db.session.commit()
        print("✅ Default admin user created.")
    else:
        print("⚠️ Admin already exists.")

# Set the path to the Tesseract executable
TESSERACT_PATH = TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# Ensure the upload and converted folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Global variables 
global extracted_text
global summary

# Initialize global variables
extracted_text = ""
summary = ""

@app.route("/")
def home_page():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        name = request.form.get('name', '').strip()
        age = request.form.get('age', '')
        gender = request.form.get('gender', '')
        profession = request.form.get('profession', '').strip()
        height = request.form.get('height') or None
        weight = request.form.get('weight') or None

        # Basic validation
        if not email or not password or not confirm or not name or not age or not gender or not profession:
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        existing_user = Login.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html')

        try:
            hashed_pw = generate_password_hash(password)
            user_type = 'user'

            login_entry = Login(email=email, password=hashed_pw, user_type=user_type)
            db.session.add(login_entry)
            db.session.flush()  # Get login_entry.id before committing

            user_entry = User(
                login_id=login_entry.id,
                name=name,
                age=int(age),
                gender=gender,
                profession=profession,
                height=float(height) if height else None,
                weight=float(weight) if weight else None
            )
            db.session.add(user_entry)
            db.session.commit()

            flash('Registration successful. Please login.', 'success')
            next_page = request.form.get('next') or url_for('login')
            return redirect(next_page)

        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Registration error: {e}")  # You can log this in production

    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('auth/login.html')
        
        login_entry = Login.query.filter_by(email=email).first()

        if not login_entry:
            flash('No account found with that email.', 'error')
            return render_template('auth/login.html')
        elif not check_password_hash(login_entry.password, password):
            flash('Incorrect password. Please try again.', 'error')
            return render_template('auth/login.html')
        # Admin login
        elif email == 'admin@example.com' and login_entry.user_type == 'admin':
            session['user_name'] = 'Admin'
            session['email'] = email
            session['user_id'] = login_entry.id
            session['user_type'] = 'admin'

            flash('Welcome, Admin!', 'success')
            return redirect(url_for('dashboard_page'))
        # Regular user or medical professional login
        elif login_entry.user_type == 'user':
            user_entry = User.query.filter_by(login_id=login_entry.id).first()
            if user_entry:
                session['user_name'] = user_entry.name
                session['email'] = email
                session['user_id'] = login_entry.id
                session['user_type'] = login_entry.user_type

                flash(f'Welcome back, {session["user_name"]}!', 'success')
            else:
                flash('User details not found.', 'error')
                return render_template('auth/login.html')
        elif login_entry.user_type == 'medical':
            medical_professional_entry = MedicalProfessional.query.filter_by(login_id=login_entry.id).first()
            if medical_professional_entry:
                session['user_name'] = medical_professional_entry.name
                session['email'] = email
                session['user_id'] = login_entry.id
                session['user_type'] = login_entry.user_type
            
            flash(f'Welcome back, {session["user_name"]}!', 'success')
        else:
            flash('No user found!', 'error')
            return render_template('auth/login.html')

        return redirect(url_for('home_page'))

    return render_template('auth/login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home_page'))

@app.route("/summarizer")
def summarizer_page():
    global extracted_text, summary 
    if ('user_id' not in session) or ('user_type' not in session):
        return redirect(url_for('login', next=request.path))
    if session['user_type'] != 'user':
        return redirect(url_for('home_page'))
    return render_template('summarizer.html', extracted_text=extracted_text, summary=summary)

@app.route("/admin/dashboard")
def dashboard_page():
    if ('user_type' not in session):
        return redirect(url_for('login', next=request.path))
    
    if session['user_type'] != 'admin':
        return redirect(url_for('home_page'))

    users = User.query.all()
    documents = Document.query.all()
    return render_template('admin/dashboard.html', users=users, documents=documents)

@app.route('/chats')
def chats_page():
    medicalProfessionals = MedicalProfessional.query.all()

    # Convert to list of dicts
    medical_professionals_serialized = [
        {
            'id': mp.id,
            'name': mp.name,
            'age': mp.age,
            'gender': mp.gender,
            'specialization': mp.specialization,
            'certification': mp.certification
        } for mp in medicalProfessionals
    ]

    documents = Document.query.filter(
        Document.user_id == session['user_id'],
        Document.summary.isnot(None)
    ).all()
    if not documents:
        flash("No documents found for this user. Please upload to see in chats.", "info")
        return redirect(url_for('summarizer_page'))
    return render_template('users/chats/user_chat/page.html', documents=documents, medicalProfessionals=medical_professionals_serialized)

@app.route('/chats/professionals')
def user_professional_chats_page():
    user_id = session.get('user_id')
    chat_id = request.args.get('chat_id')
    all_chats = ProfessionalChat.query.filter_by(user_id=user_id).all()

    chat = None
    messages = []

    if chat_id:
        chat = ProfessionalChat.query.get(chat_id)
        if not chat or chat.user_id != user_id:
            flash("Unauthorized or invalid chat", "danger")
            return redirect(url_for('user_professional_chats_page'))

        messages = ProfessionalMessage.query.filter_by(chat_id=chat_id).order_by(ProfessionalMessage.timestamp).all()

    return render_template("users/chats/professional_chat/page.html", chat=chat, messages=messages, all_chats=all_chats)

@app.route('/start_pro_chat', methods=['POST'])
def start_pro_chat():
    data = request.get_json()
    doc_id = data.get('document_id')
    prof_id = data.get('professional_id')
    user_id = session['user_id']

    # Check if a chat already exists
    existing_chat = ProfessionalChat.query.filter_by(
        document_id=doc_id, user_id=user_id, professional_id=prof_id
    ).first()

    if existing_chat:
        chat_id = existing_chat.id
    else:
        chat = ProfessionalChat(
            document_id=doc_id,
            user_id=user_id,
            professional_id=prof_id
        )
        db.session.add(chat)
        db.session.commit()
        chat_id = chat.id

    return jsonify({'success': True, 'chat_id': chat_id})

@app.route("/api/send_professional_message", methods=['POST'])
def send_professional_message():
    data = request.json
    user_id = session.get("user_id")
    chat_id = data.get("chat_id")
    message = data.get("message")

    chat = ProfessionalChat.query.get_or_404(chat_id)
    if chat.user_id != user_id:
        return jsonify({"success": False}), 403

    new_message = ProfessionalMessage(
        chat_id=chat_id,
        sender='user',
        message=message
    )
    db.session.add(new_message)
    db.session.commit()

    return jsonify({"success": True})

@app.route('/medical_professionals/chat')
def professional_user_chats_page():
    user_id = session.get('user_id')
    professional = MedicalProfessional.query.filter_by(login_id=user_id).first()
    chat_id = request.args.get('chat_id')
    all_chats = ProfessionalChat.query.filter_by(professional_id=professional.id).all()

    chat = None
    messages = []

    if chat_id:
        chat = ProfessionalChat.query.get(chat_id)
        if not chat or chat.professional_id != professional.id:
            flash("Unauthorized or invalid chat", "danger")
            return redirect(url_for('professional_user_chats_page'))

        messages = ProfessionalMessage.query.filter_by(chat_id=chat_id).order_by(ProfessionalMessage.timestamp).all()

    return render_template('/medical_professional/chats/page.html', chat=chat, messages=messages, all_chats=all_chats)

@app.route("/api/send_medical_message", methods=['POST'])
def send_medical_message():
    data = request.json
    user_id = session.get("user_id")  # logged-in professional's login_id
    chat_id = data.get("chat_id")
    message = data.get("message")

    professional = MedicalProfessional.query.filter_by(login_id=user_id).first()
    if not professional:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    chat = ProfessionalChat.query.get_or_404(chat_id)
    if chat.professional_id != professional.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    new_message = ProfessionalMessage(
        chat_id=chat_id,
        sender='professional',
        message=message
    )
    db.session.add(new_message)
    db.session.commit()

    return jsonify({"success": True})


@app.route('/admin/users')
def admin_users_page():
    users = User.query.all()
    return render_template('admin/users/page.html', users=users)

@app.route('/admin/medical_professionals')
def admin_medical_professionals_page():
    medical_professionals = MedicalProfessional.query.all()
    return render_template('admin/medical_professionals/page.html', medical_professionals=medical_professionals)

@app.route('/admin/medical_professionals/add', methods=['GET', 'POST'])
def admin_medical_professionals_add_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm']

        # Basic validation
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(request.url)

        # Check if email already exists
        existing_login = Login.query.filter_by(email=email).first()
        if existing_login:
            flash("Email already registered.", "error")
            return redirect(request.url)

        # Create login entry
        hashed_password = generate_password_hash(password)
        login_entry = Login(email=email, password=hashed_password, user_type='medical')
        db.session.add(login_entry)
        db.session.commit()

        # Create medical professional entry
        medical_entry = MedicalProfessional(
            login_id=login_entry.id,
            name=request.form['name'],
            age=int(request.form['age']),
            gender=request.form['gender'],
            specialization=request.form['specialization'],
            certification=request.form['certification']
        )
        db.session.add(medical_entry)
        db.session.commit()

        flash("Medical professional added successfully.", "success")
        return redirect(url_for('admin_medical_professionals_add_page'))

    return render_template('admin/medical_professionals/add.html')

@app.route('/admin/documents')
def admin_documents_page():
    documents = Document.query.all()
    return render_template('admin/documents/page.html', documents=documents)

@app.route('/converted/<filename>')
def serve_converted(filename):
    return send_from_directory(app.config['CONVERTED_FOLDER'], filename)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save the file to the uploads folder
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Check if the file is a PDF
    if file.filename.lower().endswith('.pdf'):
        try:
            # Open the PDF using PyMuPDF
            pdf_document = fitz.open(file_path)
            if pdf_document.page_count > 0:
                # Extract the first page
                page = pdf_document.load_page(0)
                pix = page.get_pixmap()

                # Convert the pixmap to a PIL image
                image = Image.open(io.BytesIO(pix.tobytes()))

                # Save the image as JPEG
                image_filename = file.filename.replace('.pdf', '.jpg')
                image_path = os.path.join(app.config['CONVERTED_FOLDER'], image_filename)
                image.save(image_path, 'JPEG')

                # Return the URL to the converted image
                return jsonify({'file_url': f"/converted/{image_filename}"})
            else:
                return jsonify({'error': 'PDF has no pages'}), 400
        except Exception as e:
            return jsonify({'error': f'Failed to convert PDF to image: {str(e)}'}), 500
    else:
        # For non-PDF files, return the URL to the uploaded file
        return jsonify({'file_url': f"/uploads/{file.filename}"})
    

@app.route('/submit_for_summarization', methods=['POST'])
def submit_for_summarization():
    global extracted_text, summary

    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('summarizer_page'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('summarizer_page'))

    filename = secure_filename(file.filename)
    saved_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(saved_path)

    extracted_text = ""

    try:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            image = Image.open(saved_path)
            extracted_text = pytesseract.image_to_string(image)

        elif filename.lower().endswith('.pdf'):
            with open(saved_path, "rb") as pdf_file:
                pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
                for page in pdf_document:
                    extracted_text += page.get_text()

        else:
            flash("Unsupported file type", "error")
            return redirect(url_for('summarizer_page'))

    except Exception as e:
        flash(f"Text extraction failed: {str(e)}", "error")
        return redirect(url_for('summarizer_page'))

    # === LLM Summarization ===
    try:
        ollama_url = "http://localhost:11434/api/generate"
        response = requests.post(
            ollama_url,
            json={
                "model": "tinyllama",
                "prompt": f"What does the following text mean :\n\n{extracted_text}, 'donot' return the entire text, just return the summary, and say how is the patient doing.",
                "options": {"num_ctx": 2048}
            },
            headers={"Content-Type": "application/json"},
            stream=True
        )

        summary = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_data = json.loads(line)
                    summary += json_data.get("response", "")
                except json.JSONDecodeError:
                    continue

        if not summary:
            flash("Failed to generate summary", "error")
            return redirect(url_for('summarizer_page'))

    except Exception as e:
        flash(f"LLM request failed: {str(e)}", "error")
        return redirect(url_for('summarizer_page'))

    # === Save to DB ===
    try:
        doc = Document(
            user_id=session['user_id'],
            file_path=saved_path,
            summary=summary
        )
        db.session.add(doc)
        db.session.commit()
        flash("Summary saved successfully!", "success")

    except Exception as e:
        flash(f"Error saving document to database: {str(e)}", "error")

    return redirect(url_for('chats_page', chat_id=doc.id))

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    message = data.get('message')
    doc_id = data.get('document_id')
    user_id = session.get('user_id')

    if not message or not doc_id or not user_id:
        return jsonify({"error": "Invalid data"}), 400

    # Save user message
    user_msg = ChatBot(
        user_id=user_id,
        document_id=doc_id,
        sender="user",
        message=message
    )
    db.session.add(user_msg)

    # Query document summary for context
    doc = Document.query.get(doc_id)
    context = doc.summary if doc else ""

    # Send to LLM
    try:
        ollama_url = "http://localhost:11434/api/generate"
        response = requests.post(
            ollama_url,
            json={
                "model": "tinyllama",
                "prompt": f"according to this text : '{context}', answer this please {message}",
                "options": {"num_ctx": 2048}
            },
            headers={"Content-Type": "application/json"},
            stream=True
        )

        bot_reply = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_data = json.loads(line)
                    bot_reply += json_data.get("response", "")
                except json.JSONDecodeError:
                    continue

        if bot_reply:
            bot_msg = ChatBot(
                user_id=user_id,
                document_id=doc_id,
                sender="bot",
                message=bot_reply.strip()
            )
            db.session.add(bot_msg)

        db.session.commit()
        return jsonify({"bot_reply": bot_reply.strip()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/messages')
def get_messages():
    doc_id = request.args.get('document_id')
    user_id = session.get('user_id')
    if not doc_id or not user_id:
        return jsonify({"error": "Missing document_id or user not logged in"}), 400

    messages = ChatBot.query.filter_by(document_id=doc_id, user_id=user_id).order_by(ChatBot.timestamp).all()
    return jsonify({
        "messages": [{
            "sender": msg.sender,
            "message": msg.message,
            "timestamp": msg.timestamp.isoformat()
        } for msg in messages]
    })

@app.route('/profile', methods=['GET', 'POST'])
def profile_page():
    login = Login.query.get(session['user_id'])
    
    if login.user_type == 'user':
        profile_data = login.user
    elif login.user_type == 'medical professional':
        profile_data = login.medical_professional
    else:
        flash("Invalid user type.", "danger")
        return redirect(url_for('logout'))

    if request.method == 'POST':
        profile_data.name = request.form['name']
        profile_data.age = int(request.form['age']) if request.form['age'] else None
        profile_data.gender = request.form['gender']

        if login.user_type == 'user':
            profile_data.profession = request.form['profession']
            profile_data.height = float(request.form['height']) if request.form['height'] else None
            profile_data.weight = float(request.form['weight']) if request.form['weight'] else None
        else:
            profile_data.specialization = request.form['specialization']
            profile_data.certification = request.form['certification']

        db.session.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for('profile_page'))
    
    return render_template('profile.html', profile=profile_data, user_type=login.user_type)

@app.route('/admin/user/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/users/detail.html', user=user)

@app.route('/admin/documents/<int:doc_id>')
def document_detail(doc_id):
    document = Document.query.get_or_404(doc_id)
    return render_template('admin/documents/detail.html', document=document)

@app.route('/converted/<path:filename>')
def serve_converted_image(filename):
    return send_from_directory('converted', filename)
