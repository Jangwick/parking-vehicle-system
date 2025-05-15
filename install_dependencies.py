import subprocess
import sys
import os

def check_dependency(package_name):
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

def install_requirements():
    print("Checking and installing required packages...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\nAll core dependencies successfully installed!")
    except subprocess.CalledProcessError:
        print("\nError installing one or more packages. Please check the error messages above.")
    
    # Check optional dependencies
    print("\nChecking optional dependencies...")
    
    # Check for xlsxwriter
    if check_dependency('xlsxwriter'):
        print("✓ xlsxwriter is installed (Excel export)")
    else:
        print("✗ xlsxwriter is not installed")
        install = input("Would you like to install xlsxwriter for Excel exports? (y/n): ")
        if install.lower() == 'y':
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
                print("✓ xlsxwriter installed successfully!")
            except subprocess.CalledProcessError:
                print("✗ Failed to install xlsxwriter")
    
    # Check for pdfkit
    if check_dependency('pdfkit'):
        print("✓ pdfkit is installed (PDF export)")
        # Check for wkhtmltopdf
        print("  Checking for wkhtmltopdf...")
        try:
            result = subprocess.run(['wkhtmltopdf', '-V'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ wkhtmltopdf is installed: {result.stdout.strip()}")
            else:
                print("  ✗ wkhtmltopdf command returned an error")
        except FileNotFoundError:
            print("  ✗ wkhtmltopdf is not found in PATH")
            print("    Please install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html")
    else:
        print("✗ pdfkit is not installed")
        install = input("Would you like to install pdfkit for PDF exports? (y/n): ")
        if install.lower() == 'y':
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfkit"])
                print("✓ pdfkit installed successfully!")
                print("  Note: You also need to install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html")
            except subprocess.CalledProcessError:
                print("✗ Failed to install pdfkit")

if __name__ == "__main__":
    install_requirements()
    print("\nSetup complete. Run 'python app.py' to start the application.")
