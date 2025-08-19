from django.db import models
from django.utils import timezone
import datetime

class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    usage_purpose = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Trial and Subscription Fields
    trial_start_date = models.DateTimeField(default=timezone.now)
    trial_sessions_count = models.IntegerField(default=0)
    is_subscribed = models.BooleanField(default=False)

    def is_trial_active(self):
        # Trial expires after 14 days or 3 sessions
        if self.is_subscribed:
            return True # Subscribed users always have active access
        
        is_within_14_days = timezone.now() < self.trial_start_date + datetime.timedelta(days=14)
        has_sessions_left = self.trial_sessions_count < 3
        
        return is_within_14_days and has_sessions_left

    def __str__(self):
        return self.email
