from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class FriendSearchForm(FlaskForm):
    search = StringField('Search Users', validators=[DataRequired(), Length(min=2, max=64)], 
                         render_kw={"placeholder": "Enter username..."})
    submit = SubmitField('Search')