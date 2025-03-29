# app/checkin/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField
from wtforms import TextAreaField, SubmitField, SelectField
from wtforms.validators import Length, Optional

class CheckInForm(FlaskForm):
    note = TextAreaField('Note', validators=[Length(max=1000)])
    images = MultipleFileField('Images (Optional)', validators=[Optional()])
    submit = SubmitField('Check In')

class ProjectSelectForm(FlaskForm):
    project = SelectField('Select Project', coerce=int)
