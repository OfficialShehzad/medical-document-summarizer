# MEDICAL DOCUMENT SUMMARIZER AND CHATBOT
---------------------------------------------
Application for users to scan their medical document and have a "ChatBot" that helps to clear any doubts or queries of worries of the user regarding said document. There is an added feature of talking to a medical professional; after talking to a chatbot, you can directly consult a professional from the application itself.

### STEPS TO RUN
---------------------------------------------
1. download and install tesseract-OCR
2. download and install ollama and tinyllama
3. py -m venv env
4. pip install -r requirements.txt
5. flask --app app.py --debug run
6. ollama serve on a different terminal
7. admin credentials : 
    email: admin@example.com
    password: admin123
