from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import random

# Create a Blueprint for API routes
api_bp = Blueprint('api', __name__)

@api_bp.route('/slots/available', methods=['GET'])
def available_slots():
    """Mock endpoint for available slots"""
    try:
        # Get query parameters or use defaults
        start = request.args.get('start')
        end = request.args.get('end')
        
        # Generate 10 fake available slots
        slots = []
        for i in range(1, 11):
            slot_type = random.choice(['Regular', 'Regular', 'Regular', 'Electric', 'Handicap'])
            location = random.choice(['Main Area', 'East Wing', 'West Wing', 'North Entrance'])
            
            slots.append({
                'id': i,
                'slot_number': f'{"A" if i <= 5 else "B"}{i if i <= 5 else i-5}',
                'slot_type': slot_type,
                'location': location,
                'hourly_rate': '5.00' if slot_type == 'Electric' else '4.50' if slot_type == 'Handicap' else '4.00'
            })
        
        return jsonify(slots)
    except Exception as e:
        # Log the error but return empty data for graceful degradation
        print(f"Error in available_slots: {e}")
        return jsonify([])

@api_bp.route('/user/notifications', methods=['GET'])
def user_notifications():
    """Mock endpoint for user notifications"""
    page = int(request.args.get('page', 1))
    check_new = request.args.get('check_new') == 'true'
    
    # Mock notifications data with pagination
    notifications = [
        {
            'id': 1,
            'title': 'Reservation Confirmed',
            'message': 'Your parking reservation has been confirmed.',
            'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
            'type': 'success',
            'read': False,
            'action_url': '/view-reservation/1',
            'action_text': 'View Details'
        },
        {
            'id': 2,
            'title': 'Upcoming Reservation',
            'message': 'You have a reservation starting in 1 hour.',
            'timestamp': (datetime.now() - timedelta(days=1)).isoformat(),
            'type': 'info',
            'read': True,
            'action_url': '/view-reservation/2'
        },
        {
            'id': 3,
            'title': 'New System Feature',
            'message': 'We\'ve updated our system with new features.',
            'timestamp': (datetime.now() - timedelta(days=3)).isoformat(),
            'type': 'info',
            'read': False,
            'action_url': '/news/3'
        }
    ]
    
    # Paginate results - 2 per page
    start = (page - 1) * 2
    end = start + 2
    page_data = notifications[start:end]
    
    # Format response with pagination details
    response = {
        'notifications': page_data,
        'has_more': end < len(notifications),
        'unread_count': sum(1 for n in notifications if not n['read']),
        'new_count': 1 if check_new else 0
    }
    
    return jsonify(response)

@api_bp.route('/user/notifications/<int:id>/read', methods=['POST'])
def mark_notification_read(id):
    """Mark a notification as read"""
    return jsonify({'success': True})

@api_bp.route('/user/notifications/read-all', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read"""
    return jsonify({'success': True})

@api_bp.route('/user/activity', methods=['GET'])
def user_activity():
    """Mock endpoint for user activity"""
    # Create some mock activity data
    activities = [
        {
            'type': 'reservation',
            'action': 'New Reservation',
            'description': 'You made a reservation for Slot A2',
            'time': '2 hours ago'
        },
        {
            'type': 'completed',
            'action': 'Reservation Completed',
            'description': 'Your reservation for Slot B3 has ended',
            'time': '1 day ago'
        },
        {
            'type': 'cancellation',
            'action': 'Reservation Cancelled',
            'description': 'You cancelled your reservation for Slot C1',
            'time': '3 days ago'
        }
    ]
    
    return jsonify(activities)

@api_bp.route('/user/reservation-stats', methods=['GET'])
def reservation_stats():
    """Mock endpoint for reservation statistics"""
    stats = {
        'pending': 1,
        'active': 2,
        'completed': 15,
        'cancelled': 3
    }
    
    return jsonify(stats)

@api_bp.route('/slot/<int:id>', methods=['GET'])
def slot_details(id):
    """Mock endpoint for getting details about a specific slot"""
    slot_types = ['Regular', 'Electric', 'Handicap']
    locations = ['Main Area', 'East Wing', 'North Entrance', 'West Wing']
    
    # Generate fake slot data based on ID
    slot_data = {
        'id': id,
        'slot_number': f'{"A" if id < 10 else "B"}{id if id < 10 else id-9}',
        'slot_type': slot_types[id % len(slot_types)],
        'location': locations[id % len(locations)],
        'hourly_rate': '5.00' if slot_types[id % len(slot_types)] == 'Electric' else '4.00',
        'features': []
    }
    
    # Add some features based on slot type
    if slot_data['slot_type'] == 'Electric':
        slot_data['features'] = ['EV Charging Station', 'Covered Parking']
    elif slot_data['slot_type'] == 'Handicap':
        slot_data['features'] = ['Extra Wide Space', 'Ramp Access']
    else:
        slot_data['features'] = ['Standard Space', 'CCTV Coverage']
    
    return jsonify(slot_data)

@api_bp.route('/admin/recent-activity', methods=['GET'])
def admin_recent_activity():
    """Mock endpoint for admin dashboard recent activity"""
    activities = [
        {
            'user_name': 'John Doe',
            'action_type': 'reservation_created',
            'details': 'Created a reservation for Slot A1',
            'timestamp': (datetime.now() - timedelta(minutes=30)).isoformat(),
            'is_admin': False
        },
        {
            'user_name': 'Admin User',
            'action_type': 'admin_action',
            'details': 'Updated system settings',
            'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
            'is_admin': True
        },
        {
            'user_name': 'Jane Smith',
            'action_type': 'reservation_cancelled',
            'details': 'Cancelled reservation for Slot B3',
            'timestamp': (datetime.now() - timedelta(hours=4)).isoformat(),
            'is_admin': False
        },
        {
            'user_name': 'Robert Johnson',
            'action_type': 'user_login',
            'details': 'Logged in from new device',
            'timestamp': (datetime.now() - timedelta(hours=5)).isoformat(),
            'is_admin': False
        },
        {
            'user_name': 'New User',
            'action_type': 'user_registered',
            'details': 'Created new account',
            'timestamp': (datetime.now() - timedelta(hours=6)).isoformat(),
            'is_admin': False
        }
    ]
    
    return jsonify(activities)

@api_bp.route('/reservations/create', methods=['POST'])
def create_reservation():
    """Endpoint to create a new reservation"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        # Extract reservation data
        slot_id = data.get('slot_id')
        date = data.get('date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # Validate required fields
        if not all([slot_id, date, start_time, end_time]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
        # Check for conflicts (simplified mock implementation)
        # In a real app, you would check your database for conflicts
        if random.random() < 0.2:  # 20% chance of conflict for demo
            return jsonify({
                'success': False, 
                'error': 'Reservation conflict', 
                'conflict_details': 'You already have a reservation on this date from 2:00 PM to 4:00 PM',
                'conflict_id': '12345'
            }), 409
            
        # Create reservation (mock implementation)
        # In a real app, you would save to your database
        new_reservation = {
            'id': random.randint(1000, 9999),
            'slot_id': slot_id,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'created_at': datetime.now().isoformat()
        }
        
        # Return success response
        return jsonify({
            'success': True,
            'message': 'Reservation created successfully',
            'reservation': new_reservation
        })
        
    except Exception as e:
        # Log the exception
        print(f"Error in create_reservation: {str(e)}")
        # Return a proper JSON error response
        return jsonify({'success': False, 'error': str(e)}), 500
