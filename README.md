# Parking Reservation System

A comprehensive parking reservation system built with Flask, Bootstrap, and modern web technologies.

## Features
- User and admin interfaces
- Parking slot management
- Reservation system with multiple status types
- Support for different vehicle types (Gasoline, Diesel, Electric)
- Comprehensive reporting and export functionality

## Installation

1. Clone the repository
2. Create a virtual environment:
```
python -m venv venv
```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
```
pip install -r requirements.txt
```

## Export Functionality Requirements

For the export functionality to work properly, you need:

### Excel Exports
Excel exports require the `xlsxwriter` package which is included in `requirements.txt`.

### PDF Exports
PDF exports require:

1. `pdfkit` package (included in `requirements.txt`)
2. `wkhtmltopdf` installed on your system:
   - Windows: Download and install from [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html)
   - macOS: `brew install wkhtmltopdf`
   - Ubuntu/Debian: `sudo apt-get install wkhtmltopdf`

After installing wkhtmltopdf, make sure it's added to your system PATH.

## Running the Application

Run the app with:
```
python app.py
```

Then open your browser and navigate to http://127.0.0.1:5000/

## Admin Access
- Email: admin@example.com
- Password: adminpass
