import os
import uuid
import time
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
from sqlalchemy import or_

# --- CONFIGURATION ---
app = Flask(__name__)



# Define the custom nl2br filter function
def nl2br(value):
    """
    Converts newline characters (\n) into HTML break tags (<br>).
    """
    if value is None:
        return ""
    # Use replace to convert newlines to <br> tags
    return value.replace('\n', '<br>')

# Assuming your Flask application object is named 'app':
# Register the custom filter with the Jinja environment
app.jinja_env.filters['nl2br'] = nl2br

# --- Your existing routes and other application code follow below ---


# Essential Flask Config
# Generating a fresh, random key for better session security and reliability
app.secret_key = os.urandom(24) 
app.config['UPLOAD_FOLDER'] = 'static/covers'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Set SERVER_NAME for generating absolute URLs (needed for mock data cover links)
# IMPORTANT: Change 'localhost:5000' if you deploy this on a different host/port
app.config['SERVER_NAME'] = 'localhost:5000' 

# SQLAlchemy Config
# Using SQLite database file in the application instance folder
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth'
login_manager.login_message_category = 'info'


# --- MODELS ---

class User(UserMixin, db.Model):
    """Database model for user authentication."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # Relationship to books uploaded by this user
    books = db.relationship('Book', backref='uploader', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Book(db.Model):
    """Database model for novel entries."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    genre = db.Column(db.String(50))
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False) # The actual text of the novel
    # Stores the full URL path for the cover image
    cover_url = db.Column(db.String(300)) 
    timestamp = db.Column(db.Float, default=time.time)
    
    # Foreign key link to the User table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        """Returns a dictionary representation for easy rendering."""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'genre': self.genre,
            'description': self.description,
            'content': self.content,
            'cover_url': self.cover_url,
            'timestamp': self.timestamp,
            'uploaded_by': self.user_id,
            'uploader_name': self.uploader.username if self.uploader else 'System'
        }


# --- HELPER FUNCTIONS ---

def allowed_file(filename):
    """Checks if a file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    """Loads a user from the database given a user ID."""
    try:
        # Using db.session.get() is the preferred way in modern SQLAlchemy
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None

# --- BEFORE REQUEST HOOK ---
@app.before_request
def before_request():
    """Sets global context variables (timestamp) and syncs session with Flask-Login status."""
    g.now = time.localtime()
    
    # Ensure session variables reflect the current_user status for Jinja rendering
    if current_user.is_authenticated:
        session['is_authenticated'] = True
        session['username'] = current_user.username
    else:
        session['is_authenticated'] = False
        session.pop('username', None)
        
# --- APP SETUP (Ensures folders and database exist) ---

with app.app_context():
    # 1. Create instance path and static upload folders
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # Placeholder folder for static mock images
        os.makedirs('static/placeholder', exist_ok=True) 
        # Create dummy placeholder files if they don't exist
        for filename in ['obsidian_key.png', 'silicon_dreams.png', 'no_cover.png']:
            placeholder_path = os.path.join('static/placeholder', filename)
            if not os.path.exists(placeholder_path):
                # Create a minimal dummy file (empty or placeholder content)
                with open(placeholder_path, 'w') as f:
                    f.write("Placeholder image content")
                
    except OSError as e:
        print(f"Could not create directories: {e}")

    # 2. Initialize the database and tables
    db.create_all()

    # 3. Add mock data users and books if the database is empty
    if not Book.query.first():
        system_user = User.query.filter_by(username='System').first()
        if not system_user:
            # Create a dedicated System user for mock data ownership
            system_user = User(username='System', email='system@novel.com')
            system_user.set_password(str(uuid.uuid4())) # Set a dummy password
            db.session.add(system_user)
            db.session.commit()
            
        # NEW: Create a dedicated 'Guest Uploader' user to assign anonymous uploads to
        guest_uploader = User.query.filter_by(username='Guest Uploader').first()
        if not guest_uploader:
            guest_uploader = User(username='Guest Uploader', email='guest@novel.com')
            guest_uploader.set_password(str(uuid.uuid4())) # Set a dummy password
            db.session.add(guest_uploader)
            db.session.commit()
            
        # NEW: Add a test user for auth testing
        test_user = User.query.filter_by(email='test@story.com').first()
        if not test_user:
            test_user = User(username='Tester', email='test@story.com')
            test_user.set_password('testpassword')
            db.session.add(test_user)
            db.session.commit()
        
        # Use a request context to allow url_for('_external=True') execution
        with app.test_request_context():
            initial_books = [
                Book(title='The Obsidian Key', author='Anya S. Thorne', genre='Fantasy', 
                     description='A young apprentice discovers a forbidden artifact that opens doors between worlds.', 
                     content='''
Chapter 1: The Air Tasted of Ozone
... (Content truncated)
''',
                     cover_url=url_for('static', filename='placeholder/obsidian_key.png', _external=True),
                     user_id=system_user.id),
                Book(title='Silicon Dreams', author='Kaelen Rourke', genre='Sci-Fi', 
                     description='A detective hunts a digital phantom that threatens to crash the entire collective consciousness.', 
                     content='''
Chapter 1: Echoes in the Grid
... (Content truncated)
''',
                     cover_url=url_for('static', filename='placeholder/silicon_dreams.png', _external=True),
                     timestamp=time.time() - 3600,
                     user_id=system_user.id)
                ]
            db.session.bulk_save_objects(initial_books)
            db.session.commit()
            print("--- Database initialized with mock books, System user, Guest Uploader, and Test user ---")


# --- ROUTES ---

@app.route('/toggle-dark-mode', methods=['POST'])
def toggle_dark_mode():
    """Toggles the dark mode setting and saves it in the Flask session."""
    try:
        data = request.get_json()
        is_dark = data.get('dark_mode', False)
        session['dark_mode'] = is_dark
        return jsonify({'status': 'success', 'dark_mode': is_dark}), 200
    except Exception as e:
        print(f"Error toggling dark mode (JSON parse error likely): {e}")
        return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400


@app.route('/')
def home():
    """Display the home page with the 4 most recently uploaded books."""
    newly_released = Book.query.order_by(Book.timestamp.desc()).limit(4).all()
    books_data = [book.to_dict() for book in newly_released]
    return render_template('home.html', books=books_data)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    """Handles user login and signup."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not (email and password):
            flash('Email and password are required.', 'error')
            return redirect(url_for('auth'))

        if action == 'signup':
            username = request.form.get('username')
            if not username:
                flash('Username is required for signup.', 'error')
                return redirect(url_for('auth'))

            if User.query.filter((User.email == email) | (User.username == username)).first():
                flash('Email or username already registered.', 'error')
                return redirect(url_for('auth'))

            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            session.clear() # Clear all old session data
            login_user(new_user)
            
            # Update session variables
            session['is_authenticated'] = True
            session['username'] = new_user.username

            flash(f'Welcome, {username}! Account created.', 'success')
            return redirect(url_for('home'))

        elif action == 'login':
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                
                session.clear() # Clear all old session data
                login_user(user)
                
                # Update session variables
                session['is_authenticated'] = True
                session['username'] = user.username

                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('home'))
            
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth'))

    return render_template('auth.html')

@app.route('/logout')
# Removed @login_required, as logout should be clean even if the user manually hits the URL
def logout():
    """Logs the current user out if authenticated."""
    if current_user.is_authenticated:
        logout_user()
        flash('You have been logged out.', 'success')
        
    # Clear session variables regardless of authentication status, just in case.
    session.pop('is_authenticated', None)
    session.pop('username', None)
    
    return redirect(url_for('home'))

# --- SIMPLIFIED FORGOT PASSWORD FLOW ---

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Step 1: User provides email/username. If found, redirects immediately to reset form.
    """
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        identifier = request.form.get('identifier') # Can be email or username
        
        if not identifier:
            flash('Please enter your email or username.', 'error')
            return redirect(url_for('forgot_password'))

        # Check by email or username
        user = User.query.filter(
            or_(User.email.ilike(identifier), User.username.ilike(identifier))
        ).first()

        if user:
            # Found user: redirect them immediately to the reset page for this user ID.
            # This is a less secure method than using a unique token but fits the simplified request.
            # We rely on the user ID being obscure and only exposed after successful identification.
            return redirect(url_for('reset_password_immediate', user_id=user.id))
        else:
            flash('Account not found.', 'error')
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password-immediate/<int:user_id>', methods=['GET', 'POST'])
def reset_password_immediate(user_id):
    """
    Step 2: User sets the new password directly for the identified user ID.
    """
    user = db.session.get(User, user_id)
    
    if not user:
        flash('Invalid request. Please start the password reset process again.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return render_template('reset_password_immediate.html', user_id=user_id, username=user.username)
            
        if new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return render_template('reset_password_immediate.html', user_id=user_id, username=user.username)

        # Update the user's password
        user.set_password(new_password)
        db.session.commit()
        
        flash('Your password has been successfully reset! You can now log in.', 'success')
        return redirect(url_for('auth'))

    # GET Request: Render the form to enter the new password
    return render_template('reset_password_immediate.html', user_id=user_id, username=user.username)

# --- END SIMPLIFIED FORGOT PASSWORD FLOW ---


@app.route('/all')
def all_books(): 
# ... (rest of the routes are unchanged) ...
    """Displays a list of all available books."""
    all_books_orm = Book.query.order_by(Book.title).all()
    books_data = [book.to_dict() for book in all_books_orm]
    return render_template('all.html', books=books_data, query=None)

@app.route('/search')
def search():
    """Handles searching for books by title, author, or genre."""
    query = request.args.get('query', '').strip()
    if not query:
        return redirect(url_for('all_books')) 

    # Search logic using SQLAlchemy's filter and case-insensitive matching (ilike)
    search_term = f'%{query}%'
    results_orm = Book.query.filter(
        or_(
            Book.title.ilike(search_term), 
            Book.author.ilike(search_term),
            Book.genre.ilike(search_term)
        )
    ).all()

    books_data = [book.to_dict() for book in results_orm]
    return render_template('all.html', books=books_data, query=query)

@app.route('/upload', methods=['GET', 'POST'])
# Removed @login_required to allow anonymous uploads
def upload_book():
    """Handles displaying and processing the book upload form."""
    
    # 1. Determine the user ID for the upload based on authentication status
    if current_user.is_authenticated:
        uploader_id = current_user.id
    else:
        # Find the ID of the special 'Guest Uploader' user
        guest_user = User.query.filter_by(username='Guest Uploader').first()
        if not guest_user:
            flash('System Error: Guest Uploader account not configured. Please contact support.', 'error')
            return redirect(url_for('home'))
        uploader_id = guest_user.id
    
    print(f"DEBUG: Accessing upload. User authenticated: {current_user.is_authenticated}, Upload ID: {uploader_id}")
    
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        genre = request.form.get('genre')
        description = request.form.get('description')
        content = request.form.get('content') 
        
        # Default cover URL
        cover_url = url_for('static', filename='placeholder/no_cover.png') 

        # --- FILE UPLOAD LOGIC ---
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file.filename != '' and allowed_file(file.filename):
                # Generate unique filename using the determined UPLOADER ID and timestamp
                filename = secure_filename(f"{uploader_id}-{int(time.time())}-{file.filename}")
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(save_path)
                    # Store the public URL path
                    cover_url = url_for('static', filename=f'covers/{filename}', _external=True)
                except Exception as e:
                    flash(f'Error saving file: {e}', 'error')
                    return redirect(url_for('upload_book'))
            elif file.filename != '':
                flash('Invalid file type for cover image. Only PNG, JPG, and JPEG are allowed.', 'error')
                return redirect(url_for('upload_book'))
        
        # --- VALIDATION ---
        if not all([title, author, genre, description, content]):
            flash('All fields (including the novel text) must be filled out.', 'error')
            return redirect(url_for('upload_book'))

        # --- SAVE TO DB ---
        new_book = Book(
            title=title,
            author=author,
            genre=genre,
            description=description,
            content=content,
            cover_url=cover_url,
            user_id=uploader_id # Use the determined uploader_id
        )
        try:
            db.session.add(new_book)
            db.session.commit()
            flash(f'Novel "{title}" published successfully!', 'success')
            return redirect(url_for('all_books')) # Redirect to 'all_books' after upload for non-logged-in users
        except Exception as e:
            db.session.rollback()
            flash(f'Database error during publish: {e}', 'error')
            return redirect(url_for('upload_book'))

    return render_template('upload.html')

@app.route('/reader/<int:book_id>')
def reader(book_id):
    """
    Displays the full content of a novel using the reader.html template.
    This route will redirect to 'all_books' ONLY IF the book_id is invalid.
    """
    # Retrieve the Book object or return 404 if not found
    book = db.session.get(Book, book_id)
    if not book:
        # This is the line that causes the redirect if the book ID is bad.
        flash('Novel not found.', 'error')
        return redirect(url_for('all_books'))
        
    # Pass the book dictionary (which includes 'content') to the template
    return render_template('reader.html', book=book.to_dict())

@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    """Deletes a book, ensuring only the original uploader can do so."""
    book = db.session.get(Book, book_id)
    
    if not book:
        flash('Novel not found.', 'error')
        return redirect(url_for('library'))

    if book.user_id != current_user.id:
        flash('You do not have permission to delete this novel.', 'error')
        return redirect(url_for('library'))
    
    try:
        # Delete the cover image file if it exists and is not a placeholder
        if book.cover_url and 'static/covers/' in book.cover_url:
            # Safely extract filename from the URL path
            path = urlparse(book.cover_url).path
            filename = os.path.basename(path)
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                
        db.session.delete(book)
        db.session.commit()
        flash(f'Novel "{book.title}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during deletion: {e}', 'error')

    return redirect(url_for('library'))

# NEW: Route for viewing books by genre
@app.route('/genre/<string:genre_name>')
def genre_view(genre_name):
    """Displays books filtered by a specific genre."""
    # Note: Using ilike for case-insensitive genre matching
    books_in_genre = Book.query.filter(Book.genre.ilike(f'%{genre_name}%')).order_by(Book.title).all()
    books_data = [book.to_dict() for book in books_in_genre]
    return render_template('all.html', books=books_data, query=f"Genre: {genre_name}")

@app.route('/library')
@login_required
def library():
    """Displays the user's uploaded books and mock reading history."""
    # 1. Fetch books uploaded by the current user
    user_uploaded_books = Book.query.filter_by(user_id=current_user.id).all()
    uploaded_books_data = [book.to_dict() for book in user_uploaded_books]
    
    # 2. Mock reading history (using system-uploaded books for diversity)
    history_books_data = [] 
    system_user = User.query.filter_by(username='System').first()
    if system_user:
        # Show system books as "history"
        history_books_data = [
            book.to_dict() for book in Book.query.filter(Book.user_id == system_user.id).limit(2).all()
        ]
        
    return render_template('library.html', 
                             uploaded_books=uploaded_books_data, 
                             history=history_books_data)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Displays the current user's profile information and handles updates."""
    if request.method == 'POST':
        new_username = request.form.get('username')
        
        # 1. Check if the username is taken by another user
        if new_username != current_user.username:
            user_exists = User.query.filter(
                User.username == new_username, 
                User.id != current_user.id
            ).first()
            
            if user_exists:
                flash(f'Username "{new_username}" is already taken.', 'error')
                return redirect(url_for('profile'))
        
        # 2. Update the username and commit to DB
        try:
            current_user.username = new_username
            db.session.commit()
            
            # 3. Update the session for immediate header/UI change
            session['username'] = new_username
            
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating profile: {e}', 'error')
            
        return redirect(url_for('profile'))

    # GET request: Display the profile
    return render_template('profile.html', user=current_user)


if __name__ == '__main__':
    # Running the app creates the instance folder and data.sqlite file
    app.run(debug=True)
