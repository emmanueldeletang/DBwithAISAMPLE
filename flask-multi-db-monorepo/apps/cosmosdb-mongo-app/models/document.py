from mongoengine import Document, StringField, DateTimeField, ListField, ReferenceField
from datetime import datetime

class Partner(Document):
    name = StringField(required=True)
    contact_info = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

class Delivery(Document):
    partner = ReferenceField(Partner, required=True)
    delivery_date = DateTimeField(required=True)
    status = StringField(choices=["Pending", "Completed", "Cancelled"], default="Pending")
    items = ListField(StringField())
    created_at = DateTimeField(default=datetime.utcnow)