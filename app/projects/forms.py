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
    is_public = BooleanField('Public Project')
    icon = StringField('Icon (optional)', validators=[Length(max=50)])
    color = StringField('Color (optional)', validators=[Length(max=20)])
    submit = SubmitField('Create Project')

class ProjectInviteForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    role = SelectField('Role', choices=[('member', 'Member'), ('admin', 'Admin')], default='member')
    submit = SubmitField('Invite User')