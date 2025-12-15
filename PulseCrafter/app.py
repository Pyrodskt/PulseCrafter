import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

# Basic setup
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Model
class Music(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    album = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Music {self.title}>'

@app.route('/')
def index():
    music_list = db.session.execute(db.select(Music).order_by(Music.artist)).scalars().all()
    return render_template('index.html', music_list=music_list)

# Command to initialize the database
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and populates them with some initial data."""
    with app.app_context():
        db.create_all()
        # Add sample music if the DB is empty
        if not Music.query.first():
            sample_music = [
                Music(title='Bohemian Rhapsody', artist='Queen', album='A Night at the Opera'),
                Music(title='Stairway to Heaven', artist='Led Zeppelin', album='Led Zeppelin IV'),
                Music(title='Hotel California', artist='Eagles', album='Hotel California')
            ]
            db.session.bulk_save_objects(sample_music)
            db.session.commit()
    print("Initialized and populated the database.")

if __name__ == '__main__':
    app.run(debug=True)
