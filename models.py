# models.py
import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Login(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(50), nullable=False)  # admin, user, or medical professional

    user = db.relationship('User', back_populates='login', uselist=False)
    medical_professional = db.relationship('MedicalProfessional', back_populates='login', uselist=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('login.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    profession = db.Column(db.String(100), nullable=False)
    height = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    
    login = db.relationship('Login', back_populates='user')
    documents = db.relationship('Document', back_populates='user', cascade='all, delete-orphan')
    messages = db.relationship('ChatBot', back_populates='user', cascade='all, delete-orphan')


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=True)

    user = db.relationship('User', back_populates='documents')
    messages = db.relationship('ChatBot', back_populates='document', cascade='all, delete-orphan')


class MedicalProfessional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('login.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    certification = db.Column(db.String(200), nullable=False)

    login = db.relationship('Login', back_populates='medical_professional')

class ChatBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # "user" or "bot"
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', back_populates='messages')
    document = db.relationship('Document', back_populates='messages')

class ProfessionalChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('medical_professional.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    document = db.relationship('Document', backref='professional_chats')
    user = db.relationship('User', backref='professional_chats')
    professional = db.relationship('MedicalProfessional', backref='professional_chats')

class ProfessionalMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('professional_chat.id'), nullable=False)
    sender = db.Column(db.String(50))  # 'user' or 'professional'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
