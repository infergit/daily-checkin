# app/checkin/forms.py
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, SelectField
from wtforms.validators import Length

class CheckInForm(FlaskForm):
    note = TextAreaField('Note (Optional)', validators=[Length(max=200)])
    submit = SubmitField('Check In')

class ProjectSelectForm(FlaskForm):
    project = SelectField('Select Project', coerce=int)
