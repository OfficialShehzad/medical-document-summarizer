import pytesseract
from PIL import Image
import os

# Set the path to the system-installed Tesseract executable
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Debugging: Print the Tesseract path
print("Tesseract Path:", TESSERACT_PATH)

# Check if the Tesseract executable exists
if not os.path.isfile(TESSERACT_PATH):
    print("Error: Tesseract executable not found at the specified path.")
else:
    print("Tesseract executable found.")

# Path to the image file
image_path = os.path.join(os.getcwd(), 'converted', 'shehzad_resume_march_2023.jpg')

# Debugging: Print the image path
print("Image Path:", image_path)

# Check if the image file exists
if not os.path.isfile(image_path):
    print("Error: Image file not found at the specified path.")
else:
    print("Image file found.")

# Test OCR with the image
def test_tesseract():
    try:
        # Open the image
        image = Image.open(image_path)
        # Extract text using pytesseract
        text = pytesseract.image_to_string(image)
        print("Extracted Text:", text)
    except Exception as e:
        print("Error:", str(e))

# Run the test
test_tesseract()
