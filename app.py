from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy import or_
from collections import defaultdict
import json
import io
import csv
from flask_wtf.csrf import CSRFProtect, generate_csrf
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Setup login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    reservations = db.relationship('Reservation', backref='user', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    @property
    def created_at(self):
        """Return a default creation time when the attribute is accessed."""
        return datetime.now()  # Default to current time when accessed

class ParkingSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_number = db.Column(db.String(10), unique=True, nullable=False)
    slot_type = db.Column(db.String(20), nullable=False)  # Regular, Electric
    status = db.Column(db.String(20), default='Available')  # Available, Occupied, Maintenance
    reservations = db.relationship('Reservation', backref='parking_slot', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('parking_slot.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Active, Completed, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_name = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Decorator to check admin access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.url))
        
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        vehicle_type = request.form.get('vehicle_type')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already exists')
            return redirect(url_for('register'))
        
        new_user = User(
            name=name,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            vehicle_type=vehicle_type
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        
        # ...existing validation code...
        
        # Check if CSRF token is valid
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(request.form.get('csrf_token'))
        except:
            flash("Form expired. Please try again.")
            return redirect(url_for('login'))
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
            
        if not user.is_active:
            flash('Your account has been deactivated. Please contact admin.')
            return redirect(url_for('login'))
            
        login_user(user)
        
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# User routes
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            # Handle profile update
            try:
                current_user.name = request.form.get('name')
                current_user.email = request.form.get('email')
                current_user.vehicle_type = request.form.get('vehicle_type')
                db.session.commit()
                flash('Profile updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating profile: {str(e)}', 'danger')
                
        elif action == 'change_password':
            # Handle password change
            try:
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')
                confirm_password = request.form.get('confirm_password')
                
                # Validate inputs
                if not current_password or not new_password or not confirm_password:
                    flash('All password fields are required', 'danger')
                elif new_password != confirm_password:
                    flash('New passwords do not match', 'danger')
                elif not check_password_hash(current_user.password, current_password):
                    flash('Current password is incorrect', 'danger')
                else:
                    # Update password
                    current_user.password = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Password changed successfully. Please log in with your new password.', 'success')
                    logout_user()
                    return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error changing password: {str(e)}', 'danger')
    
    # Get active reservations for the user
    active_reservations = Reservation.query.filter_by(user_id=current_user.id).filter(
        Reservation.status.in_(['Active', 'Pending'])
    ).all()
    
    # Get user stats for the dashboard
    total_count = Reservation.query.filter_by(user_id=current_user.id).count()
    active_count = Reservation.query.filter_by(user_id=current_user.id, status='Active').count()
    upcoming_count = Reservation.query.filter_by(user_id=current_user.id, status='Pending').count()
    
    # Get total slots for availability percentage calculation
    total_slots = ParkingSlot.query.count()
    
    return render_template(
        'user/dashboard.html',
        reservations=active_reservations,
        total_count=total_count,
        active_count=active_count,
        upcoming_count=upcoming_count,
        total_slots=total_slots
    )

# Enhance the make-reservation route
@app.route('/make-reservation', methods=['GET', 'POST'])
@login_required
def make_reservation():
    if request.method == 'POST':
        # Get form data
        slot_id = request.form.get('slot_id')
        reservation_date = request.form.get('reservation_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        # Validate required fields
        if not slot_id or not reservation_date or not start_time or not end_time:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="All fields are required.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Parse datetime objects
        try:
            start_datetime = datetime.strptime(f"{reservation_date} {start_time}", '%Y-%m-%d %H:%M')
            end_datetime = datetime.strptime(f"{reservation_date} {end_time}", '%Y-%m-%d %H:%M')
            
            # If end time is before start time, assume next day
            if end_datetime < start_datetime:
                end_datetime = end_datetime + timedelta(days=1)
                
        except ValueError:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Invalid date or time format.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Get the parking slot
        parking_slot = ParkingSlot.query.get(slot_id)
        if not parking_slot:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Selected parking slot not found.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Check if slot is available
        if parking_slot.status != 'Available':
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Selected slot is no longer available.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Check for electric vehicle restriction
        if parking_slot.slot_type == 'Electric' and current_user.vehicle_type != 'Electric':
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Electric slots are reserved for electric vehicles only.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Check minimum reservation time (1 hour)
        duration = end_datetime - start_datetime
        hours = duration.total_seconds() / 3600
        if hours < 1:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Minimum reservation duration is 1 hour.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Check maximum reservation time (24 hours by default)
        max_duration = 24  # This could be loaded from settings
        if hours > max_duration:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message=f"Maximum reservation duration is {max_duration} hours.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=max_duration)
        
        # Check if reservation start time is in the past
        if start_datetime < datetime.now():
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="Reservation start time cannot be in the past.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Check for conflicting reservations
        conflicting_reservations = Reservation.query.filter(
            Reservation.slot_id == slot_id,
            Reservation.status.in_(['Pending', 'Active']),
            Reservation.start_time < end_datetime,
            Reservation.end_time > start_datetime
        ).all()
        
        if conflicting_reservations:
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message="This slot is already reserved during the selected time period.",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
        
        # Create the reservation
        new_reservation = Reservation(
            user_id=current_user.id,
            slot_id=slot_id,
            start_time=start_datetime,
            end_time=end_datetime
        )
        
        try:
            db.session.add(new_reservation)
            db.session.commit()
            
            # Record activity
            record_user_activity(current_user.id, 'create_reservation', f"Reserved slot {parking_slot.slot_number} from {start_datetime.strftime('%Y-%m-%d %H:%M')} to {end_datetime.strftime('%Y-%m-%d %H:%M')}")
            
            # Show success message
            flash("Reservation created successfully!")
            return redirect(url_for('view_reservations'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating reservation: {str(e)}")
            return render_template('make_reservation.html', 
                                  available_slots=get_available_slots(),
                                  error_message=f"An error occurred while creating your reservation: {str(e)}",
                                  today=datetime.now().strftime('%Y-%m-%d'),
                                  max_duration=24)
    
    # GET request - show the reservation form
    return render_template('make_reservation.html', 
                          available_slots=get_available_slots(),
                          today=datetime.now().strftime('%Y-%m-%d'),
                          max_duration=24)

def get_available_slots():
    """Get available parking slots, filtered by user's vehicle type"""
    if current_user.vehicle_type == 'Electric':
        # Electric vehicles can use any slot
        return ParkingSlot.query.filter_by(status='Available').all()
    else:
        # Non-electric vehicles can use non-Electric slots
        return ParkingSlot.query.filter_by(status='Available').all()

def record_user_activity(user_id, action_type, details):
    """Record user activity for the activity log"""
    # This function would typically insert into an Activity table
    # For now, we'll just log it
    app.logger.info(f"User {user_id} - {action_type}: {details}")

# Add a new API endpoint to check for reservation conflicts
@app.route('/api/check-conflicts')
@login_required
def check_conflicts():
    slot_id = request.args.get('slot_id')
    date = request.args.get('date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    
    # Validate required parameters
    if not slot_id or not date or not start_time or not end_time:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        # Parse datetime objects
        start_datetime = datetime.strptime(f"{date} {start_time}", '%Y-%m-%d %H:%M')
        end_datetime = datetime.strptime(f"{date} {end_time}", '%Y-%m-%d %H:%M')
        
        # If end time is before start time, assume next day
        if end_datetime < start_datetime:
            end_datetime = end_datetime + timedelta(days=1)
    except ValueError:
        return jsonify({'error': 'Invalid date or time format'}), 400
    
    # Check for conflicting reservations
    conflicting_reservations = Reservation.query.filter(
        Reservation.slot_id == slot_id,
        Reservation.status.in_(['Pending', 'Active']),
        Reservation.start_time < end_datetime,
        Reservation.end_time > start_datetime
    ).all()
    
    conflicts = []
    for reservation in conflicting_reservations:
        conflicts.append({
            'id': reservation.id,
            'start_time': reservation.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': reservation.end_time.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify({
        'conflicts': conflicts,
        'has_conflicts': len(conflicts) > 0
    })

@app.route('/view-reservations')
@login_required
def view_reservations():
    reservations = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.start_time.desc()).all()
    return render_template('user/view_reservations.html', reservations=reservations)

@app.route('/edit-reservation/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_reservation(id):
    reservation = Reservation.query.get_or_404(id)
    if reservation.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('admin_edit_reservation', id=id))
    if reservation.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access')
        return redirect(url_for('view_reservations'))
        
    if reservation.status != 'Pending':
        flash('Only pending reservations can be edited', 'danger')
        return redirect(url_for('view_reservations'))
        
    if request.method == 'POST':
        start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        
        if start_time >= end_time:
            flash('End time must be after start time', 'danger')
            return redirect(url_for('edit_reservation', id=id))
            
        if start_time < datetime.now():
            flash('Start time cannot be in the past', 'danger')
            return redirect(url_for('edit_reservation', id=id))
        
        # Check for overlapping reservations (excluding current reservation)
        overlapping = Reservation.query.filter(
            Reservation.id != id,
            Reservation.slot_id == reservation.slot_id,
            Reservation.status.in_(['Pending', 'Active']),
            Reservation.start_time < end_time,
            Reservation.end_time > start_time
        ).first()
        
        if overlapping:
            flash('This slot is already reserved for the selected time period', 'danger')
            return redirect(url_for('edit_reservation', id=id))
        
        reservation.start_time = start_time
        reservation.end_time = end_time
        
        try:
            db.session.commit()
            flash('Reservation updated successfully', 'success')
            return redirect(url_for('view_reservations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating reservation: {str(e)}', 'danger')
            return render_template('user/edit_reservation.html', reservation=reservation)
            
    return render_template('user/edit_reservation.html', reservation=reservation)

@app.route('/cancel-reservation/<int:id>', methods=['POST'])
@login_required
def cancel_reservation(id):
    reservation = Reservation.query.get_or_404(id)
    
    # Check if user owns this reservation or is admin
    if reservation.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to cancel this reservation', 'danger')
        return redirect(url_for('view_reservations'))
    
    # Check if reservation can be cancelled
    if reservation.status not in ['Pending', 'Active']:
        flash('This reservation cannot be cancelled', 'danger')
        return redirect(url_for('view_reservations'))
    
    try:
        reservation.status = 'Cancelled'
        db.session.commit()
        flash('Reservation cancelled successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling reservation: {str(e)}', 'danger')
    
    if current_user.is_admin:
        return redirect(url_for('admin_reservations'))
    return redirect(url_for('view_reservations'))

@app.route('/availability')
@login_required
def availability():
    """Page to check parking space availability"""
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get system settings
    try:
        max_days_setting = SystemSetting.query.filter_by(setting_name='advance_booking_limit').first()
        max_days_ahead = int(max_days_setting.setting_value) if max_days_setting else 30
    except:
        max_days_ahead = 30  # Default value
    
    # Get total slots for statistics
    total_slots = ParkingSlot.query.count()
    
    return render_template(
        'user/availability.html',
        max_days_ahead=max_days_ahead,
        total_slots=total_slots
    )

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    total_users = User.query.filter_by(is_admin=False).count()
    active_reservations = Reservation.query.filter_by(status='Active').count()
    total_slots = ParkingSlot.query.count()
    available_slots = ParkingSlot.query.filter_by(status='Available').count()
    
    # Get recent activities for initial page load
    recent_reservations = Reservation.query.order_by(Reservation.created_at.desc()).limit(10).all()
    recent_activities = []
    
    for reservation in recent_reservations:
        activity = {
            'user_name': reservation.user.name,
            'action': 'Created reservation' if reservation.status == 'Pending' else 'Completed reservation' if reservation.status == 'Completed' else 'Cancelled reservation' if reservation.status == 'Cancelled' else 'Started reservation',
            'details': f"Slot {reservation.parking_slot.slot_number} from {reservation.start_time.strftime('%Y-%m-%d %H:%M')} to {reservation.end_time.strftime('%Y-%m-%d %H:%M')}",
            'timestamp': reservation.created_at.strftime('%Y-%m-%d %H:%M')
        }
        recent_activities.append(activity)
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        active_reservations=active_reservations,
        total_slots=total_slots,
        available_slots=available_slots,
        recent_activities=recent_activities
    )

# Update the admin_users route to properly handle pagination parameters
@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    # Get page number for pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of users per page
    
    # Build the query with filters
    query = User.query.filter_by(is_admin=False)
    
    # Apply search filter if provided
    search = request.args.get('search', '')
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    # Apply vehicle type filter if provided
    vehicle_type = request.args.get('vehicle_type', '')
    if vehicle_type:
        query = query.filter_by(vehicle_type=vehicle_type)
    
    # Apply status filter if provided
    status = request.args.get('status', '')
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    # Apply sorting
    sort = request.args.get('sort', 'name')
    if sort == 'name':
        query = query.order_by(User.name)
    elif sort == 'email':
        query = query.order_by(User.email)
    elif sort == 'newest':
        query = query.order_by(User.id.desc())
    
    # Paginate the results
    paginated_users = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'admin/users.html',
        users=paginated_users.items,
        page=page,
        total_pages=paginated_users.pages or 1
    )

@app.route('/admin/edit-user/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
        
    user = User.query.get_or_404(id)
    
    # Prevent editing admin users
    if user.is_admin and user.id != current_user.id:
        flash("Cannot modify other admin accounts")
        return redirect(url_for('admin_users'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        vehicle_type = request.form.get('vehicle_type')
        is_active = 'is_active' in request.form
        
        # Check if email already exists for another user
        existing = User.query.filter(User.email == email, User.id != id).first()
        if existing:
            flash("Email already in use by another user")
            return redirect(url_for('admin_edit_user', id=id))
            
        # Update user details
        user.name = name
        user.email = email
        user.vehicle_type = vehicle_type
        user.is_active = is_active
        
        # Only update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            
        db.session.commit()
        flash("User updated successfully")
        return redirect(url_for('admin_users'))
        
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/toggle-user/<int:id>')
@login_required
def toggle_user(id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
        
    user = User.query.get_or_404(id)
    
    if user.is_admin:
        flash('Cannot modify admin accounts')
        return redirect(url_for('admin_users'))
        
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} has been {status}')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete-user/<int:id>')
@login_required
def delete_user(id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
        
    user = User.query.get_or_404(id)
    
    if user.is_admin:
        flash('Cannot delete admin accounts')
        return redirect(url_for('admin_users'))
        
    # Cancel all pending reservations
    pending_reservations = Reservation.query.filter_by(user_id=user.id).filter(
        Reservation.status.in_(['Pending', 'Active'])
    ).all()
    
    for reservation in pending_reservations:
        reservation.status = 'Cancelled'
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.name} has been deleted')
    return redirect(url_for('admin_users'))

@app.route('/admin/reservations', methods=['GET'])
@login_required
@admin_required
def admin_reservations():
    # Get query parameters for filtering and pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    slot_type_filter = request.args.get('slot_type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Handle reservation actions
    action = request.args.get('action')
    reservation_id = request.args.get('reservation_id')
    
    if action and reservation_id:
        reservation = Reservation.query.get(reservation_id)
        if reservation:
            if action == 'approve':
                reservation.status = 'Active'
                db.session.commit()
                flash('Reservation approved successfully!', 'success')
            elif action == 'deny':
                reservation.status = 'Cancelled'
                db.session.commit()
                flash('Reservation denied successfully!', 'error')
            elif action == 'complete':
                reservation.status = 'Completed'
                db.session.commit()
                flash('Reservation marked as completed!', 'success')
            elif action == 'cancel':
                reservation.status = 'Cancelled'
                db.session.commit()
                flash('Reservation cancelled successfully!', 'success')
            elif action == 'reactivate':
                reservation.status = 'Active'
                db.session.commit()
                flash('Reservation reactivated successfully!', 'success')
        return redirect(url_for('admin_reservations'))
    
    # Handle bulk actions
    bulk_action = request.args.get('bulk_action')
    selected_ids = request.args.getlist('selected_ids')
    
    if bulk_action and selected_ids:
        processed = 0
        for id in selected_ids:
            reservation = Reservation.query.get(id)
            if not reservation:
                continue
                
            if bulk_action == 'approve' and reservation.status == 'Pending':
                reservation.status = 'Active'
                processed += 1
            elif bulk_action == 'deny' and reservation.status == 'Pending':
                reservation.status = 'Cancelled'
                processed += 1
            elif bulk_action == 'cancel' and reservation.status == 'Active':
                reservation.status = 'Cancelled'
                processed += 1
            elif bulk_action == 'complete' and reservation.status == 'Active':
                reservation.status = 'Completed'
                processed += 1
                
        if processed > 0:
            db.session.commit()
            flash(f'{processed} reservations processed successfully!', 'success')
        return redirect(url_for('admin_reservations'))

    # Build query with filters
    query = Reservation.query
    
    if search_query:
        query = query.join(User).join(ParkingSlot).filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%'),
                ParkingSlot.slot_number.ilike(f'%{search_query}%')
            )
        )
    
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    
    if slot_type_filter:
        query = query.join(ParkingSlot).filter(ParkingSlot.slot_type == slot_type_filter)
    
    if start_date:
        query = query.filter(Reservation.start_time >= datetime.strptime(start_date, '%Y-%m-%d'))
    
    if end_date:
        query = query.filter(Reservation.end_time <= (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)))
    
    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(Reservation.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(Reservation.created_at.asc())
    elif sort_by == 'start_time':
        query = query.order_by(Reservation.start_time.asc())
    elif sort_by == 'end_time':
        query = query.order_by(Reservation.end_time.asc())
    
    # Get statistics for summary cards
    total_reservations = Reservation.query.count()
    pending_reservations = Reservation.query.filter_by(status='Pending').count()
    active_reservations = Reservation.query.filter_by(status='Active').count()
    cancelled_reservations = Reservation.query.filter_by(status='Cancelled').count()
    completed_reservations = Reservation.query.filter_by(status='Completed').count()
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    reservations = pagination.items
    total_pages = pagination.pages or 1
    
    # Get all users and slots for add/edit modals
    all_users = User.query.filter_by(is_admin=False).all()
    all_slots = ParkingSlot.query.all()
    
    return render_template(
        'admin/reservations.html',
        reservations=reservations,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_reservations=total_reservations,
        pending_reservations=pending_reservations,
        active_reservations=active_reservations,
        cancelled_reservations=cancelled_reservations,
        completed_reservations=completed_reservations,
        all_users=all_users,
        all_slots=all_slots
    )

@app.route('/admin/slots')
@login_required
def admin_slots():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    # Get filter parameters
    search = request.args.get('search', '')
    slot_type = request.args.get('type', '')
    status = request.args.get('status', '')
    sort = request.args.get('sort', 'number')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query
    query = ParkingSlot.query
    
    # Apply filters
    if search:
        query = query.filter(ParkingSlot.slot_number.contains(search))
    
    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type)
    
    if status:
        query = query.filter(ParkingSlot.status == status)
    
    # Apply sorting
    if sort == 'number':
        query = query.order_by(ParkingSlot.slot_number)
    elif sort == 'type':
        query = query.order_by(ParkingSlot.slot_type, ParkingSlot.slot_number)
    elif sort == 'status':
        query = query.order_by(ParkingSlot.status, ParkingSlot.slot_number)
    
    # Paginate results
    slots_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    slots = slots_pagination.items
    total_pages = slots_pagination.pages
    
    # Get summary stats
    total_slots = ParkingSlot.query.count()
    available_slots = ParkingSlot.query.filter_by(status='Available').count()
    occupied_slots = ParkingSlot.query.filter_by(status='Occupied').count()
    maintenance_slots = ParkingSlot.query.filter_by(status='Maintenance').count()
    
    # Get all slots for the parking map
    all_slots = ParkingSlot.query.all()
    
    return render_template('admin/slots.html',
                          slots=slots,
                          all_slots=all_slots,
                          page=page,
                          total_pages=total_pages,
                          total_slots=total_slots,
                          available_slots=available_slots,
                          occupied_slots=occupied_slots,
                          maintenance_slots=maintenance_slots)

@app.route('/admin/add-slot', methods=['GET', 'POST'])
@login_required
def add_slot():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        slot_number = request.form.get('slot_number')
        slot_type = request.form.get('slot_type')
        status = request.form.get('status')
        
        slot_exists = ParkingSlot.query.filter_by(slot_number=slot_number).first()
        if slot_exists:
            flash('Slot number already exists')
            return redirect(url_for('add_slot'))
        
        new_slot = ParkingSlot(
            slot_number=slot_number,
            slot_type=slot_type,
            status=status
        )
        
        db.session.add(new_slot)
        db.session.commit()
        
        flash('Parking slot added successfully')
        return redirect(url_for('admin_slots'))
        
    return render_template('admin/add_slot.html')

@app.route('/admin/edit-slot/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_slot(id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
        
    slot = ParkingSlot.query.get_or_404(id)
    
    if request.method == 'POST':
        slot_number = request.form.get('slot_number')
        
        # Check if another slot has the same number
        existing = ParkingSlot.query.filter(ParkingSlot.slot_number == slot_number, ParkingSlot.id != id).first()
        if existing:
            flash('Slot number already exists')
            return redirect(url_for('edit_slot', id=id))
            
        slot.slot_number = slot_number
        slot.slot_type = request.form.get('slot_type')
        slot.status = request.form.get('status')
        
        db.session.commit()
        flash('Parking slot updated successfully')
        return redirect(url_for('admin_slots'))
        
    return render_template('admin/edit_slot.html', slot=slot)

@app.route('/admin/delete-slot/<int:id>')
@login_required
def delete_slot(id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
        
    slot = ParkingSlot.query.get_or_404(id)
    
    # Check for active reservations
    active_reservations = Reservation.query.filter_by(
        slot_id=slot.id
    ).filter(
        Reservation.status.in_(['Pending', 'Active'])
    ).first()
    
    if active_reservations:
        flash('Cannot delete slot with active reservations')
        return redirect(url_for('admin_slots'))
        
    db.session.delete(slot)
    db.session.commit()
    
    flash('Parking slot deleted successfully')
    return redirect(url_for('admin_slots'))

# Replace the JavaScript-style comments (//) with Python comments
# Find the admin_settings route and modify it to handle all the settings-related actions
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Load settings from database or file
    settings = load_settings()
    
    # Handle different actions
    action = request.args.get('action') or request.form.get('action')
    
    # Handle backup action
    if action == 'backup':
        try:
            # Convert settings to JSON
            settings_json = json.dumps(settings, indent=4)
            
            # Return as downloadable file
            return Response(
                settings_json,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=settings_backup.json'}
            )
        except Exception as e:
            flash(f"Error backing up settings: {str(e)}", "error")
            return redirect(url_for('admin_settings'))
    
    # Handle restore action
    elif action == 'restore' and request.method == 'POST':
        if 'settings_file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(url_for('admin_settings'))
        
        settings_file = request.files['settings_file']
        if settings_file.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('admin_settings'))
            
        if not settings_file.filename.endswith('.json'):
            flash("Please upload a valid JSON settings file", "error")
            return redirect(url_for('admin_settings'))
        
        try:
            # Read and parse uploaded settings
            settings_json = settings_file.read().decode('utf-8')
            new_settings = json.loads(settings_json)
            
            # Validate settings (basic check)
            if not isinstance(new_settings, dict):
                flash("Invalid settings format", "error")
                return redirect(url_for('admin_settings'))
            
            # Save the new settings
            save_settings(new_settings)
            
            flash("Settings restored successfully", "success")
            return redirect(url_for('admin_settings'))
        except Exception as e:
            flash(f"Error restoring settings: {str(e)}", "error")
            return redirect(url_for('admin_settings'))
    
    # Handle reset action
    elif action == 'reset' and request.method == 'POST':
        try:
            # Reset to default settings
            default_settings = {
                'system_name': 'ParkEase Parking System',
                'contact_email': 'contact@example.com',
                'timezone': 'UTC',
                'maintenance_mode': 'false',
                'min_duration': '1',
                'max_duration': '24',
                'max_active_reservations': '3',
                'reservation_buffer': '15',
                'advance_booking_limit': '30',
                'cancellation_policy': '2',
                'require_approval': 'false',
                'ev_slots_limit': '20',
                'handicap_slots_limit': '10',
                'operating_hours': '24/7',
                'slot_numbering': 'numeric',
                'restrict_ev_slots': 'true',
                'email_notifications': 'all',
                'notify_admin_new_reservation': 'true',
                'notify_admin_cancellation': 'true',
                'send_reminder': 'true',
                'reminder_hours': '24',
                'email_sender': 'ParkEase System',
                'session_timeout': '60',
                'password_expiry': '90',
                'failed_login_attempts': '5',
                'lockout_duration': '30',
                'enable_debug_mode': 'false'
            }
            
            # Save the default settings
            save_settings(default_settings)
            
            flash("Settings have been reset to default values", "success")
            return redirect(url_for('admin_settings'))
        except Exception as e:
            flash(f"Error resetting settings: {str(e)}", "error")
            return redirect(url_for('admin_settings'))
    
    # Handle form submission for updating settings
    elif request.method == 'POST':
        # Process form data
        new_settings = {}
        
        # Process all form fields
        for key in request.form.keys():
            if key != 'csrf_token' and key != 'action':
                if request.form[key] == 'on':
                    new_settings[key] = 'true'
                else:
                    new_settings[key] = request.form[key]
                    
        # Process checkbox fields that might not be in the form if unchecked
        checkbox_fields = [
            'maintenance_mode', 'require_approval', 'restrict_ev_slots',
            'notify_admin_new_reservation', 'notify_admin_cancellation',
            'send_reminder', 'enable_debug_mode'
        ]
        
        for field in checkbox_fields:
            if field not in new_settings:
                new_settings[field] = 'false'
        
        # Handle custom operating hours
        if new_settings.get('operating_hours') == 'custom':
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                day_enabled = f"{day}_enabled"
                if day_enabled not in new_settings:
                    new_settings[day_enabled] = 'false'
        
        try:
            # Save the new settings
            save_settings(new_settings)
                
            flash("Settings updated successfully", "success")
            return redirect(url_for('admin_settings'))
        except Exception as e:
            flash(f"Error saving settings: {str(e)}", "error")
    
    # Display the settings page
    return render_template('admin/settings.html', settings=settings, success_message=None, error_message=None)

# Helper functions for settings
def load_settings():
    """Load settings from database or file"""
    try:
        # Check if settings file exists
        settings_path = os.path.join(app.root_path, 'data', 'settings.json')
        
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                return json.load(f)
        else:
            # Return default settings
            return {
                'system_name': 'ParkEase Parking System',
                'contact_email': 'contact@example.com',
                'timezone': 'UTC',
                'max_duration': '24',
                'ev_slots_limit': '20'
            }
    except Exception as e:
        app.logger.error(f"Error loading settings: {str(e)}")
        # Return basic default settings on error
        return {
            'system_name': 'ParkEase Parking System',
            'max_duration': '24',
            'ev_slots_limit': '20'
        }

def save_settings(settings):
    """Save settings to database or file"""
    try:
        # Ensure data directory exists
        data_dir = os.path.join(app.root_path, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Write settings to file
        settings_path = os.path.join(data_dir, 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
            
        return True
    except Exception as e:
        app.logger.error(f"Error saving settings: {str(e)}")
        return False

# API Routes for AJAX calls
@app.route('/api/slots/available')
@login_required
def api_available_slots():
    """API endpoint to get available parking slots for a time range"""
    try:
        # Parse start and end datetime parameters
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        if start_str and end_str:
            # Parse ISO format datetime strings
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        else:
            # Default to current time + 1 hour for start and +3 hours for end
            now = datetime.now()
            start_time = now + timedelta(hours=1)
            end_time = now + timedelta(hours=3)
        
        # Find all slots that are not reserved during the specified time period
        all_slots = ParkingSlot.query.filter_by(status='Available').all()
        available_slots = []
        
        for slot in all_slots:
            # Check if there are any conflicting reservations for this slot
            conflicting_reservations = Reservation.query.filter(
                Reservation.slot_id == slot.id,
                Reservation.status.in_(['Active', 'Pending']),
                Reservation.start_time < end_time,
                Reservation.end_time > start_time
            ).first()
            
            # If no conflicts, slot is available
            if not conflicting_reservations:
                # For non-Electric vehicles, exclude Electric slots
                if slot.slot_type == 'Electric' and current_user.vehicle_type != 'Electric':
                    continue
                
                # Add slot details to available slots
                price_info = get_price_for_slot(slot)
                available_slots.append({
                    'id': slot.id,
                    'slot_number': slot.slot_number,
                    'slot_type': slot.slot_type,
                    'location': slot.location,
                    'hourly_rate': price_info['hourly_rate'],
                    'features': get_slot_features(slot)
                })
        
        return jsonify(available_slots)
        
    except Exception as e:
        app.logger.error(f"Error retrieving available slots: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add helper functions for slot data
def get_price_for_slot(slot):
    """Get pricing information for a parking slot"""
    # Default rates based on slot type
    rates = {
        'Regular': 4.00,
        'Electric': 5.50,
        'Handicap': 4.00,
        'Premium': 6.00
    }
    
    # Get pricing from system settings if available
    try:
        setting = SystemSetting.query.filter_by(setting_name=f"{slot.slot_type.lower()}_rate").first()
        if setting:
            rate = float(setting.setting_value)
        else:
            rate = rates.get(slot.slot_type, 4.00)
    except:
        # Fallback to default rates
        rate = rates.get(slot.slot_type, 4.00)
        
    return {
        'hourly_rate': rate,
        'currency': 'USD'
    }

def get_slot_features(slot):
    """Get features for a parking slot"""
    features = []
    
    if slot.slot_type == 'Electric':
        features.append('EV Charging Station')
    
    if slot.slot_type == 'Premium':
        features.append('Extra Wide')
        features.append('Covered Parking')
    
    if slot.is_covered:
        features.append('Covered Parking')
    
    if slot.has_camera:
        features.append('Security Camera')
    
    # Add custom features from slot metadata if available
    try:
        if slot.metadata and 'features' in slot.metadata:
            features.extend(slot.metadata['features'])
    except:
        pass
        
    return features

# Add an API endpoint to get specific slot details
@app.route('/api/slot/<int:id>')
@login_required
def api_get_slot(id):
    """API endpoint to get details for a specific parking slot"""
    try:
        slot = ParkingSlot.query.get_or_404(id)
        
        # Get current pricing and status
        price_info = get_price_for_slot(slot)
        
        slot_data = {
            'id': slot.id,
            'slot_number': slot.slot_number,
            'slot_type': slot.slot_type,
            'location': slot.location,
            'status': slot.status,
            'hourly_rate': price_info['hourly_rate'],
            'features': get_slot_features(slot)
        }
        
        return jsonify(slot_data)
        
    except Exception as e:
        app.logger.error(f"Error retrieving slot details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/dashboard-stats')
@login_required
def api_dashboard_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    total_users = User.query.filter_by(is_admin=False).count()
    active_reservations = Reservation.query.filter_by(status='Active').count()
    total_slots = ParkingSlot.query.count()
    available_slots = ParkingSlot.query.filter_by(status='Available').count()
    
    return jsonify({
        'total_users': total_users,
        'active_reservations': active_reservations,
        'total_slots': total_slots,
        'available_slots': available_slots
    })

@app.route('/api/admin/reservations-data')
@login_required
def api_reservation_data():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    period = request.args.get('period', 'weekly')
    
    if period == 'weekly':
        # Get data for the last 7 days
        start_date = datetime.now() - timedelta(days=7)
        labels = [(datetime.now() - timedelta(days=i)).strftime('%a') for i in range(6, -1, -1)]
        
        # Get reservations grouped by day
        reservations = Reservation.query.filter(Reservation.created_at >= start_date).all()
        data_dict = defaultdict(int)
        
        for reservation in reservations:
            day_key = reservation.created_at.strftime('%a')
            data_dict[day_key] += 1
            
        # Format data to match labels order
        data = [data_dict[label] for label in labels]
        
    else:  # monthly
        # Get data for the current month
        current_month = datetime.now().month
        current_year = datetime.now().year
        days_in_month = 30  # Approximation
        
        labels = [str(i) for i in range(1, days_in_month + 1)]
        
        # Get reservations for current month
        start_date = datetime(current_year, current_month, 1)
        end_date = start_date + timedelta(days=days_in_month)
        
        reservations = Reservation.query.filter(
            Reservation.created_at >= start_date,
            Reservation.created_at < end_date
        ).all()
        
        data_dict = defaultdict(int)
        
        for reservation in reservations:
            day_key = str(reservation.created_at.day)
            data_dict[day_key] += 1
            
        # Format data to match labels order
        data = [data_dict[label] for label in labels]
    
    return jsonify({
        'labels': labels,
        'data': data
    })

@app.route('/api/admin/vehicle-distribution')
@login_required
def api_vehicle_distribution():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get count of users by vehicle type
    gasoline_count = User.query.filter_by(vehicle_type='Gasoline').count()
    diesel_count = User.query.filter_by(vehicle_type='Diesel').count()
    electric_count = User.query.filter_by(vehicle_type='Electric').count()
    
    labels = ['Gasoline', 'Diesel', 'Electric']
    data = [gasoline_count, diesel_count, electric_count]
    
    return jsonify({
        'labels': labels,
        'data': data
    })

@app.route('/api/admin/recent-activities')
@login_required
def api_recent_activities():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    # Get recent reservations as activities
    recent_reservations = Reservation.query.order_by(Reservation.created_at.desc()).limit(10).all()
    
    activities = []
    
    for reservation in recent_reservations:
        activity = {
            'user_name': reservation.user.name,
            'action': 'Created reservation' if reservation.status == 'Pending' else 'Completed reservation' if reservation.status == 'Completed' else 'Cancelled reservation' if reservation.status == 'Cancelled' else 'Started reservation',
            'details': f"Slot {reservation.parking_slot.slot_number} from {reservation.start_time.strftime('%Y-%m-%d %H:%M')} to {reservation.end_time.strftime('%Y-%m-%d %H:%M')}",
            'timestamp': reservation.created_at.strftime('%Y-%m-%d %H:%M')
        }
        activities.append(activity)
    
    return jsonify(activities)

@app.route('/api/admin/user-details/<int:user_id>')
@login_required
def api_user_details(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    # When returning user data, provide a default value for created_at
    created_at_value = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'vehicle_type': user.vehicle_type,
        'is_active': user.is_active,
        'created_at': created_at_value,  # Use default value
        # ... other fields ...
    })

@app.route('/api/admin/user-reservations/<int:user_id>')
@login_required
def api_user_reservations(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    user = User.query.get_or_404(user_id)
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.start_time.desc()).all()
    
    result = []
    for res in reservations:
        result.append({
            'id': res.id,
            'slot_number': res.parking_slot.slot_number,
            'slot_type': res.parking_slot.slot_type,
            'start_time': res.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': res.end_time.strftime('%Y-%m-%d %H:%M'),
            'status': res.status,
            'created_at': res.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify(result)

@app.route('/api/admin/bulk-user-action', methods=['POST'])
@login_required
def api_bulk_user_action():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    action = data.get('action')
    user_ids = data.get('user_ids')
    
    if not action or not user_ids:
        return jsonify({'error': 'Invalid request parameters'}), 400
    
    try:
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and not user.is_admin:  # Prevent modifying admin users
                if action == 'activate':
                    user.is_active = True
                elif action == 'deactivate':
                    user.is_active = False
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/admin/export-users')
@login_required
def api_export_users():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    format_type = request.args.get('format', 'csv')
    fields = request.args.get('fields', 'name,email,vehicle_type').split(',')
    
    # Build query with filters
    query = User.query.filter_by(is_admin=False)
    
    # Apply filters from URL if present
    search = request.args.get('search')
    if search:
        query = query.filter(
            or_(User.name.ilike(f'%{search}%'), User.email.ilike(f'%{search}%'))
        )
    
    vehicle_type = request.args.get('vehicle_type')
    if vehicle_type:
        query = query.filter_by(vehicle_type=vehicle_type)
    
    status = request.args.get('status')
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active(False))
    
    # Get all users matching the filters
    users = query.all()
    
    # CSV export (default)
    if format_type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = []
        for field in fields:
            if field == 'name': headers.append('Name')
            elif field == 'email': headers.append('Email')
            elif field == 'vehicle_type': headers.append('Vehicle Type')
            elif field == 'status': headers.append('Status')
            elif field == 'reservations': headers.append('Reservations Count')
            elif field == 'created_at': headers.append('Created At')
        writer.writerow(headers)
        
        # Write data rows
        for user in users:
            row = []
            for field in fields:
                if field == 'name': row.append(user.name)
                elif field == 'email': row.append(user.email)
                elif field == 'vehicle_type': row.append(user.vehicle_type)
                elif field == 'status': row.append('Active' if user.is_active else 'Inactive')
                elif field == 'reservations': row.append(len(user.reservations))
                elif field == 'created_at': row.append(datetime.now().strftime('%Y-%m-%d'))  # Placeholder - add actual field if exists
            
            writer.writerow(row)
        
        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    
    # Excel export
    elif format_type == 'excel':
        try:
            from io import BytesIO
            import xlsxwriter
            
            # Create a workbook and add a worksheet
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Users')
            
            # Add headers with formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#3498db',
                'color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Write headers to the worksheet
            for col_idx, header in enumerate(headers):
                worksheet.write(0, col_idx, header, header_format)
            
            # Add data rows with formatting
            row_format = workbook.add_format({
                'align': 'left',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Write data rows
            for row_idx, row_data in enumerate(data_rows):
                for col_idx, cell_value in enumerate(row_data):
                    worksheet.write(row_idx + 1, col_idx, cell_value, row_format)
            
            # Auto-adjust column widths
            for col_idx, _ in enumerate(headers):
                worksheet.set_column(col_idx, col_idx, 18)
            
            workbook.close()
            output.seek(0)
            
            return Response(
                output.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-disposition": f"attachment; filename={filename}.xlsx"}
            )
            
        except ImportError as e:
            app.logger.error(f"Excel export error (ImportError): {str(e)}")
            return jsonify({'error': f'Excel export failed: {str(e)}. Please make sure xlsxwriter is installed.'}), 500
        except Exception as e:
            app.logger.error(f"Excel export error (Exception): {str(e)}")
            return jsonify({'error': f'Excel export failed: {str(e)}.'}), 500

    # PDF export
    elif format_type == 'pdf':
        try:
            # First try with pdfkit if available
            import pdfkit
            from flask import render_template_string
            
            # Create HTML table from data
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Reservations Export</title>
                <style>
                    body { font-family: Arial, sans-serif; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #3498db; color: white; }
                    tr:nth-child(even) { background-color: #f2f2f2; }
                    h1 { color: #3498db; }
                    .footer { margin-top: 30px; font-size: 12px; color: #666; text-align: center; }
                </style>
            </head>
            <body>
                <h1>Reservations Export</h1>
                <p>Generated on: {{ generation_date }}</p>
                <table>
                    <thead>
                        <tr>
                            {% for header in headers %}
                                <th>{{ header }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in data %}
                            <tr>
                                {% for cell in row %}
                                    <td>{{ cell }}</td>
                                {% endfor %}
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <div class="footer">
                    <p>ParkEase Reservation System &copy; {{ current_year }}</p>
                </div>
            </body>
            </html>
            """
            
            html_content = render_template_string(
                html_template,
                headers=headers,
                data=data_rows, 
                generation_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                current_year=datetime.now().year
            )
            
            # Convert HTML to PDF
            pdf_options = {
                'page-size': 'A4',
                'margin-top': '1cm',
                'margin-right': '1cm',
                'margin-bottom': '1cm',
                'margin-left': '1cm',
                'encoding': "UTF-8"
            }
            
            # Using pdfkit to generate PDF
            pdf = pdfkit.from_string(html_content, False, options=pdf_options)
            
            # Return the PDF file
            return Response(
                pdf,
                mimetype="application/pdf",
                headers={"Content-disposition": f"attachment; filename={filename}.pdf"}
            )
            
        except ImportError:
            # If pdfkit is not available, use alternative HTML download approach
            from flask import render_template_string
            
            # Create HTML table from data that can be saved as HTML and printed to PDF
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Reservations Export</title>
                <style>
                    body { font-family: Arial, sans-serif; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #3498db; color: white; }
                    tr:nth-child(even) { background-color: #f2f2f2; }
                    h1 { color: #3498db; }
                    .footer { margin-top: 30px; font-size: 12px; color: #666; text-align: center; }
                    .print-instructions { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                    @media print {
                        .print-instructions { display: none; }
                        button { display: none; }
                    }
                </style>
                <script>
                    function printDocument() {
                        window.print();
                    }
                </script>
            </head>
            <body>
                <div class="print-instructions">
                    <h3>Print Instructions</h3>
                    <p>To save as PDF:</p>
                    <ol>
                        <li>Click the "Print" button below or press Ctrl+P (Cmd+P on Mac)</li>
                        <li>In the print dialog, select "Save as PDF" as the destination/printer</li>
                        <li>Click Save/Print</li>
                    </ol>
                    <button onclick="printDocument()" style="padding: 8px 16px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">Print</button>
                </div>
                
                <h1>Reservations Export</h1>
                <p>Generated on: {{ generation_date }}</p>
                <table>
                    <thead>
                        <tr>
                            {% for header in headers %}
                                <th>{{ header }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in data %}
                            <tr>
                                {% for cell in row %}
                                    <td>{{ cell }}</td>
                                {% endfor %}
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <div class="footer">
                    <p>ParkEase Reservation System &copy; {{ current_year }}</p>
                </div>
            </body>
            </html>
            """
            
            html_content = render_template_string(
                html_template,
                headers=headers,
                data=data_rows, 
                generation_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                current_year=datetime.now().year
            )
            
            # Return HTML that can be printed to PDF
            return Response(
                html_content,
                mimetype="text/html",
                headers={"Content-disposition": f"inline; filename={filename}.html"}
            )
        except Exception as e:
            app.logger.error(f"PDF export error: {str(e)}")
            return jsonify({'error': f'PDF export failed: {str(e)}. Try using CSV or Excel format instead.'}), 500

    # Unsupported format
    return jsonify({'error': 'Unsupported export format'}), 400

@app.route('/api/admin/slot-details/<int:slot_id>')
@login_required
def api_slot_details(slot_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    slot = ParkingSlot.query.get_or_404(slot_id)
    
    # Get current reservation if any
    current_reservation = None
    active_reservation = Reservation.query.filter_by(slot_id=slot_id, status='Active').first()
    
    if active_reservation:
        current_reservation = {
            'id': active_reservation.id,
            'user_name': active_reservation.user.name,
            'start_time': active_reservation.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': active_reservation.end_time.strftime('%Y-%m-%d %H:%M')
        }
    
    # Calculate usage statistics
    reservations = Reservation.query.filter_by(slot_id=slot_id).all()
    usage_count = len(reservations)
    hours_used = 0
    
    for reservation in reservations:
        if reservation.status in ['Active', 'Completed']:
            duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
            hours_used += duration_seconds / 3600
    
    return jsonify({
        'id': slot.id,
        'slot_number': slot.slot_number,
        'slot_type': slot.slot_type,
        'status': slot.status,
        'location': slot.location if hasattr(slot, 'location') else '',
        'usage_count': usage_count,
        'hours_used': round(hours_used, 1),
        'current_reservation': current_reservation
    })

@app.route('/api/admin/slot-history/<int:slot_id>')
@login_required
def api_slot_history(slot_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get reservations for this slot
    reservations = Reservation.query.filter_by(slot_id=slot_id).order_by(Reservation.start_time.desc()).limit(20).all()
    
    history = []
    for reservation in reservations:
        duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
        hours = int(duration_seconds / 3600)
        minutes = int((duration_seconds % 3600) / 60)
        
        history.append({
            'id': reservation.id,
            'user_name': reservation.user.name,
            'start_time': reservation.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': reservation.end_time.strftime('%Y-%m-%d %H:%M'),
            'duration': f"{hours}h {minutes}m",
            'status': reservation.status
        })
    
    return jsonify(history)

@app.route('/api/admin/bulk-slot-action', methods=['POST'])
@login_required
def api_bulk_slot_action():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    action = data.get('action')
    slot_ids = data.get('slot_ids', [])
    
    if not slot_ids:
        return jsonify({'error': 'No slots selected'}), 400
    
    try:
        # Fetch all slots at once
        slots = ParkingSlot.query.filter(ParkingSlot.id.in_(slot_ids)).all()
        
        if action == 'available':
            for slot in slots:
                if slot.status != 'Occupied':
                    slot.status = 'Available'
        elif action == 'maintenance':
            for slot in slots:
                if slot.status != 'Occupied':
                    slot.status = 'Maintenance'
        elif action == 'delete':
            for slot in slots:
                if slot.status != 'Occupied':
                    db.session.delete(slot)
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Successfully processed {len(slots)} slots'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/export-slots')
@login_required
def api_export_slots():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    format_type = request.args.get('format', 'csv')
    fields = request.args.get('fields', 'slot_number,slot_type,status').split(',')
    
    # Build query based on filter parameters
    query = ParkingSlot.query
    
    # Apply filters from URL if present
    search = request.args.get('search')
    if search:
        query = query.filter(ParkingSlot.slot_number.contains(search))
    
    slot_type = request.args.get('type')
    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type)
    
    status = request.args.get('status')
    if status:
        query = query.filter(ParkingSlot.status == status)
    
    # Get all slots matching the criteria
    slots = query.all()
    
    # Prepare headers
    headers = []
    for field in fields:
        if field == 'slot_number': headers.append('Slot Number')
        elif field == 'slot_type': headers.append('Type')
        elif field == 'status': headers.append('Status')
        elif field == 'location': headers.append('Location')
        elif field == 'usage_count': headers.append('Usage Count')
        elif field == 'hours_used': headers.append('Hours Used')
    
    # Prepare data rows
    data_rows = []
    for slot in slots:
        # Calculate usage statistics if needed
        usage_count = 0
        hours_used = 0
        if 'usage_count' in fields or 'hours_used' in fields:
            reservations = Reservation.query.filter_by(slot_id=slot.id).all()
            usage_count = len(reservations)
            for reservation in reservations:
                if reservation.status in ['Active', 'Completed']:
                    duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
                    hours_used += duration_seconds / 3600
        
        row = []
        for field in fields:
            if field == 'slot_number': row.append(slot.slot_number)
            elif field == 'slot_type': row.append(slot.slot_type)
            elif field == 'status': row.append(slot.status)
            elif field == 'location': row.append(getattr(slot, 'location', 'N/A'))
            elif field == 'usage_count': row.append(str(usage_count))
            elif field == 'hours_used': row.append(f"{round(hours_used, 1)}")
        
        data_rows.append(row)
    
    # Generate export with the same logic as other exports
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"parking_slots_{timestamp}"
    
    # Use existing export code implementation (CSV, Excel, PDF)
    # ...

# Add these new routes to manage the admin profile
# Add these near your other admin routes

@app.route('/admin/profile', methods=['GET'])
@login_required
def admin_profile():
    if not current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get user preferences from database or default values
    preferences = get_user_preferences(current_user.id)
    
    # Get recent activity for the current admin
    activity_logs = get_user_activity_logs(current_user.id, limit=10)
    
    # Check for any messages in the session
    success_message = session.pop('success_message', None)
    error_message = session.pop('error_message', None)
    
    # Create a form instance for CSRF protection if using Flask-WTF
    form = None
    try:
        from flask_wtf import FlaskForm
        form = FlaskForm()
    except ImportError:
        pass
    
    return render_template(
        'admin/profile.html',
        preferences=preferences,
        activity_logs=activity_logs,
        success_message=success_message,
        error_message=error_message,
        form=form
    )

@app.route('/admin/profile/update', methods=['POST'])
@login_required
def admin_profile_update():
    if not current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Check the form action
    action = request.form.get('action')
    
    # Handle CSRF validation if using Flask-WTF
    try:
        from flask_wtf import FlaskForm
        form = FlaskForm()
        if not form.validate_on_submit():
            session['error_message'] = "Form validation failed. Please try again."
            return redirect(url_for('admin_profile'))
    except ImportError:
        pass
    
    # Get the active tab to redirect back to it
    active_tab = 'account'  # Default tab
    
    if action == 'update_profile':
        # Update profile information
        name = request.form.get('name')
        email = request.form.get('email')
        vehicle_type = request.form.get('vehicle_type')
        
        # Server-side validation
        if not name or not email:
            session['error_message'] = "Name and email are required."
            return redirect(url_for('admin_profile'))
        
        try:
            # Update user in database
            current_user.name = name
            current_user.email = email
            current_user.vehicle_type = vehicle_type
            db.session.commit()
            
            # Log the activity
            log_user_activity(current_user.id, 'Profile Update', 'Updated profile information', request.remote_addr)
            
            session['success_message'] = "Profile updated successfully."
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating profile: {str(e)}")
            session['error_message'] = "An error occurred while updating your profile."
    
    elif action == 'change_password':
        # Change password
        active_tab = 'password'
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Server-side validation
        if not current_password or not new_password or not confirm_password:
            session['error_message'] = "All password fields are required."
            return redirect(url_for('admin_profile', tab='password'))
        
        if new_password != confirm_password:
            session['error_message'] = "New passwords do not match."
            return redirect(url_for('admin_profile', tab='password'))
        
        if len(new_password) < 8:
            session['error_message'] = "Password must be at least 8 characters long."
            return redirect(url_for('admin_profile', tab='password'))
        
        # Check if current password is correct
        if not check_password_hash(current_user.password, current_password):
            session['error_message'] = "Current password is incorrect."
            return redirect(url_for('admin_profile', tab='password'))
        
        try:
            # Update password in database
            current_user.password = generate_password_hash(new_password)
            db.session.commit()
            
            # Log the activity
            log_user_activity(current_user.id, 'Password Change', 'Changed account password', request.remote_addr)
            
            # Force re-login for security
            logout_user()
            session['success_message'] = "Password changed successfully. Please log in with your new password."
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            session['error_message'] = "An error occurred while changing your password."
    
    elif action == 'update_preferences':
        # Update preferences
        active_tab = 'preferences'
        dashboard_layout = request.form.get('dashboard_layout', 'standard')
        items_per_page = int(request.form.get('items_per_page', 20))
        email_notifications = 'email_notifications' in request.form
        
        try:
            # Update preferences in database
            save_user_preferences(current_user.id, {
                'dashboard_layout': dashboard_layout,
                'items_per_page': items_per_page,
                'email_notifications': email_notifications
            })
            
            # Log the activity
            log_user_activity(current_user.id, 'Preference Update', 'Updated account preferences', request.remote_addr)
                
            session['success_message'] = "Preferences saved successfully."
        except Exception as e:
            app.logger.error(f"Error updating preferences: {str(e)}")
            session['error_message'] = "An error occurred while saving your preferences."
    
    return redirect(url_for('admin_profile', tab=active_tab))

# Helper functions for user preferences and activity logs
def get_user_preferences(user_id):
    try:
        # Try to get preferences from database
        # Replace this with your actual database query
        preferences = {
            'dashboard_layout': 'standard',
            'items_per_page': 20,
            'email_notifications': True
        }
        
        return preferences
    except Exception as e:
        app.logger.error(f"Error getting user preferences: {str(e)}")
        # Return default preferences
        return {
            'dashboard_layout': 'standard',
            'items_per_page': 20,
            'email_notifications': True
        }

def save_user_preferences(user_id, preferences):
    try:
        # Save preferences to database
        # Replace this with your actual database logic
        return True
    except Exception as e:
        app.logger.error(f"Error saving user preferences: {str(e)}")
        return False

def log_user_activity(user_id, action, details, ip_address):
    try:
        # Log activity to database
        # Replace this with your actual database insert
        return True
    except Exception as e:
        app.logger.error(f"Error logging user activity: {str(e)}")
        return False

def get_user_activity_logs(user_id, limit=10):
    try:
        # Get activity logs from database
        # Replace this with your actual database query
        from datetime import datetime, timedelta
        
        # Dummy data for demonstration
        logs = [
            {'action': 'Login', 'details': 'Successful login', 'timestamp': datetime.now() - timedelta(hours=1), 'ip_address': '127.0.0.1'},
            {'action': 'Profile View', 'details': 'Viewed profile page', 'timestamp': datetime.now() - timedelta(hours=2), 'ip_address': '127.0.0.1'},
            {'action': 'Dashboard', 'details': 'Accessed admin dashboard', 'timestamp': datetime.now() - timedelta(days=1), 'ip_address': '127.0.0.1'},
            {'action': 'Settings', 'details': 'Updated system settings', 'timestamp': datetime.now() - timedelta(days=2), 'ip_address': '127.0.0.1'},
        ]
        
        return logs
    except Exception as e:
        app.logger.error(f"Error getting user activity logs: {str(e)}")
        return []

# Add this function after the User model but before app initialization or in the if __name__ == "__main__" block
def add_created_at_column():
    try:
        with app.app_context():
            # Check if created_at column exists in user table
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('user')]
            
            if 'created_at' not in columns:
                # Add the column without default value (SQLite limitation)
                db.session.execute(db.text('ALTER TABLE user ADD COLUMN created_at TIMESTAMP'))
                # Update existing rows with current timestamp
                db.session.execute(db.text('UPDATE user SET created_at = datetime("now")'))
                db.session.commit()
                print("Added created_at column to user table")
    except Exception as e:
        print(f"Error adding created_at column: {str(e)}")
        db.session.rollback()  # Make sure to rollback on error
        
# Initialize the database
with app.app_context():
    add_created_at_column()  # Add this line to modify existing tables if needed
    db.create_all()
    
    # Create admin user if not exists
    admin = User.query.filter_by(email='admin@example.com').first()
    if not admin:
        admin = User(
            name='Admin',
            email='admin@example.com',
            password=generate_password_hash('adminpass', method='pbkdf2:sha256'),
            vehicle_type='Gasoline',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)

# Find the code that creates the admin user and make sure it doesn't include created_at
if __name__ == "__main__":
    # Create directories if they don't exist
    os.makedirs('data', exist_ok=True)
    
    with app.app_context():
        # Create tables without trying to migrate
        db.create_all()
        
        # Check if admin user exists - use a try/except to handle potential errors
        try:
            # Create a custom query that only selects the columns we know exist
            admin = db.session.query(User.id, User.email).filter_by(email='admin@example.com').first()
            
            if not admin:
                # Create admin user with required fields only
                admin = User(
                    name="Admin",
                    email="admin@example.com",
                    password=generate_password_hash('adminpass', method='pbkdf2:sha256'),
                    vehicle_type="Electric",
                    is_admin=True,
                    is_active=True
                )
                db.session.add(admin)
                db.session.commit()
                print("Admin user created with email: admin@example.com and password: adminpass")
        except Exception as e:
            print(f"Error checking for admin user: {str(e)}")
            # Continue anyway to allow application to start

# Add this error handler function somewhere in your app.py file
# For example, after your route definitions but before the app.run() call

@app.errorhandler(400)
def bad_request_error(error):
    """Handle 400 Bad Request errors and provide better debugging information"""
    app.logger.error(f"Bad Request Error: {request.url}")
    app.logger.error(f"Method: {request.method}")
    
    # If it's an API endpoint (expecting JSON), return JSON error
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Bad Request',
            'message': 'The server could not process your request. Please check your input data.'
        }), 400
    
    # For regular form submissions, redirect to a page with error message
    flash('Error processing your request. Please check your input and try again.', 'error')
    
    # Try to redirect back to the referring page if available
    referrer = request.headers.get('Referer')
    if referrer:
        return redirect(referrer)
    else:
        return redirect(url_for('index'))

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

@app.errorhandler(400)
def handle_csrf_error(e):
    return render_template('error.html', error="CSRF token validation failed. Please try refreshing the page and submitting the form again."), 400

# Add this new route for the user profile
@app.route('/user/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if current_user.is_admin:
        return redirect(url_for('admin_profile'))
    
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            # Process profile update
            try:
                current_user.name = request.form.get('name')
                current_user.email = request.form.get('email')
                current_user.vehicle_type = request.form.get('vehicle_type')
                
                db.session.commit()
                success_message = "Profile updated successfully!"
            except Exception as e:
                db.session.rollback()
                error_message = f"Error updating profile: {str(e)}"
                
        elif action == 'change_password':
            # Process password change
            try:
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')
                confirm_password = request.form.get('confirm_password')
                
                # Validate input
                if not current_password or not new_password or not confirm_password:
                    raise ValueError("All password fields are required")
                    
                if new_password != confirm_password:
                    raise ValueError("New passwords don't match")
                    
                if not check_password_hash(current_user.password, current_password):
                    raise ValueError("Current password is incorrect")
                
                # Update password
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                
                # Force re-login
                logout_user()
                flash("Password changed successfully. Please log in with your new password.")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                error_message = f"Error changing password: {str(e)}"
    
    # Get user reservations stats
    try:
        stats = {
            'total': Reservation.query.filter_by(user_id=current_user.id).count(),
            'active': Reservation.query.filter_by(user_id=current_user.id, status='Active').count(),
            'pending': Reservation.query.filter_by(user_id=current_user.id, status='Pending').count(),
            'completed': Reservation.query.filter_by(user_id=current_user.id, status='Completed').count(),
            'cancelled': Reservation.query.filter_by(user_id=current_user.id, status='Cancelled').count()
        }
    except Exception:
        stats = {
            'total': 0, 'active': 0, 'pending': 0, 'completed': 0, 'cancelled': 0
        }
    
    return render_template(
        'user/profile.html',
        stats=stats,
        success_message=success_message,
        error_message=error_message
    )

# Add API endpoints for user reservation functionality

@app.route('/api/reservation/<int:id>')
@login_required
def api_reservation_details(id):
    reservation = Reservation.query.get_or_404(id)
    
    # Check if user has permission to view this reservation
    if reservation.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Calculate duration
    duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
    hours = int(duration_seconds / 3600)
    minutes = int((duration_seconds % 3600) / 60)
    duration_str = f"{hours}h {minutes}m"
    
    return jsonify({
        'id': reservation.id,
        'slot_number': reservation.parking_slot.slot_number,
        'slot_type': reservation.parking_slot.slot_type,
        'start_time': reservation.start_time.strftime('%Y-%m-%d %H:%M'),
        'end_time': reservation.end_time.strftime('%Y-%m-%d %H:%M'),
        'status': reservation.status,
        'duration': duration_str,
        'created_at': reservation.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(reservation, 'created_at') else None
    })

@app.route('/api/available-slots')
@login_required
def api_available_slots():
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    
    if not start_time or not end_time:
        return jsonify({'error': 'Start and end time are required'}), 400
    
    try:
        start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid datetime format'}), 400
    
    # Get all slots
    all_slots = ParkingSlot.query.filter_by(status='Available').all()
    
    # Find slots with conflicting reservations
    busy_slot_ids = db.session.query(Reservation.slot_id).filter(
        Reservation.status.in_(['Pending', 'Active']),
        Reservation.start_time < end_datetime,
        Reservation.end_time > start_datetime
    ).distinct().all()
    
    busy_slot_ids = [id for id, in busy_slot_ids]
    
    # Filter available slots
    available_slots = []
    for slot in all_slots:
        if slot.id not in busy_slot_ids:
            available_slots.append({
                'id': slot.id,
                'slot_number': slot.slot_number,
                'slot_type': slot.slot_type,
                'section': f"Section {slot.slot_number[0]}" if slot.slot_number[0].isalpha() else "Main Section"
            })
    
    return jsonify(available_slots)

@app.route('/api/user/reservation-stats')
@login_required
def api_user_reservation_stats():
    if current_user.is_admin:
        return jsonify({'error': 'Admin users should use admin APIs'}), 403
    
    # Get reservation counts by status
    pending = Reservation.query.filter_by(user_id=current_user.id, status='Pending').count()
    active = Reservation.query.filter_by(user_id=current_user.id, status='Active').count()
    completed = Reservation.query.filter_by(user_id=current_user.id, status='Completed').count()
    cancelled = Reservation.query.filter_by(user_id=current_user.id, status='Cancelled').count()
    
    return jsonify({
        'pending': pending,
        'active': active,
        'completed': completed,
        'cancelled': cancelled
    })

# Add this new API endpoint for fetching reservation details
@app.route('/api/reservation/<int:id>', methods=['GET'])
@login_required
def api_get_reservation(id):
    """API endpoint to get reservation details by ID"""
    try:
        # Get reservation
        reservation = Reservation.query.get_or_404(id)
        
        # Check if user owns this reservation or is admin
        if reservation.user_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'You do not have permission to view this reservation'}), 403
            
        # Format reservation data
        parking_slot = reservation.parking_slot
        
        # Calculate duration
        duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
        hours = int(duration_seconds / 3600)
        minutes = int((duration_seconds % 3600) / 60)
        duration_str = f"{hours}h {minutes}m"
        
        # Format the response data
        reservation_data = {
            'id': reservation.id,
            'slot': {
                'id': parking_slot.id,
                'number': parking_slot.slot_number,
                'type': parking_slot.slot_type,
                'location': parking_slot.location
            },
            'times': {
                'start': reservation.start_time.strftime('%Y-%m-%d %H:%M'),
                'end': reservation.end_time.strftime('%Y-%m-%d %H:%M'),
                'duration': duration_str
            },
            'status': reservation.status,
            'user': {
                'id': reservation.user.id,
                'name': reservation.user.name,
                'email': reservation.user.email,
                'vehicle_type': reservation.user.vehicle_type
            },
            'created_at': reservation.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(reservation, 'created_at') else None
        }
        
        return jsonify(reservation_data)
    except Exception as e:
        app.logger.error(f"Error fetching reservation details: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
