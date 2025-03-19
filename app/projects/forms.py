# app/projects/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

class ProjectForm(FlaskForm):
    name = StringField('Project Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    frequency_type = SelectField('Check-in Frequency', 
                                choices=[('daily', 'Daily (Once per day)'), 
                                         ('unlimited', 'Unlimited')],
                                default='daily')
    visibility = SelectField('Visibility',
                           choices=[('private', 'Private - Only you can see'), 
                                    ('invitation', 'Invitation only - Friends must be invited')],
                           default='private')
    icon = StringField('Icon (optional)', validators=[Length(max=50)])
    color = StringField('Color (optional)', validators=[Length(max=20)])
    submit = SubmitField('Save Project')

class ProjectInvitationForm(FlaskForm):
    friend_id = SelectField('Select Friend', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Send Invitation')
    
    def __init__(self, *args, **kwargs):
        user_id = kwargs.pop('user_id', None)
        super(ProjectInvitationForm, self).__init__(*args, **kwargs)
        
        if user_id:
            # Get the current user's friends list as options
            from app.models.models import User, FriendRelationship
            from flask_login import current_user
            from app import db
            
            # Friends where current user is the requester
            friends_as_requester = db.session.query(
                User
            ).join(
                FriendRelationship, User.id == FriendRelationship.addressee_id
            ).filter(
                FriendRelationship.requester_id == user_id,
                FriendRelationship.status == 'accepted'
            ).all()
            
            # Friends where current user is the addressee
            friends_as_addressee = db.session.query(
                User
            ).join(
                FriendRelationship, User.id == FriendRelationship.requester_id
            ).filter(
                FriendRelationship.addressee_id == user_id,
                FriendRelationship.status == 'accepted'
            ).all()
            
            # Combine both query results
            friends = friends_as_requester + friends_as_addressee
            
            # Set dropdown options
            self.friend_id.choices = [(friend.id, friend.username) for friend in friends]