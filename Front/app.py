import sys
import os

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports inter-modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, render_template

# Basic setup
app = Flask(__name__)

@app.route('/')
def index():
    """Renders the main index page, which will fetch data via JavaScript."""
    return render_template('index.html')

@app.route('/groups')
def groups():
    """Renders the groups page, which will fetch data via JavaScript."""
    return render_template('groups.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Use a different port than FastAPI (8000)
