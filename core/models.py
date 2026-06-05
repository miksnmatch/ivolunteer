from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [('volunteer','Volunteer'),('organization','Organization'),('admin','Admin')]
    STATUS_CHOICES = [('active','Active'),('pending','Pending'),('suspended','Suspended'),('inactive','Inactive')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='volunteer')
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_verified = models.BooleanField(default=False)
    def __str__(self): return f"{self.get_full_name() or self.username} ({self.role})"
    def initials(self): n=self.get_full_name(); return (n[0].upper() if n else 'U')

class VolunteerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='volunteer_profile')
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    time_available = models.CharField(max_length=100, blank=True)
    skills = models.TextField(blank=True)
    interests = models.TextField(blank=True)
    total_hours = models.PositiveIntegerField(default=0)
    total_projects = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    rating_count = models.PositiveIntegerField(default=0)
    def skills_list(self): return [s.strip() for s in self.skills.split(',') if s.strip()]
    def interests_list(self): return [i.strip() for i in self.interests.split(',') if i.strip()]

class IdentityVerification(models.Model):
    ID_TYPES = [('drivers_license',"Driver's License"),('passport','Passport'),('national_id','National ID'),('other','Other Gov. ID')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='identity_verification')
    id_type = models.CharField(max_length=30, choices=ID_TYPES)
    id_document = models.FileField(upload_to='id_docs/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')], default='pending')
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_verifications')

class Organization(models.Model):
    ORG_TYPES = [('environmental','Environmental & Conservation'),('health','Health & Medical Support'),('education','Education & Youth Development'),('disaster','Disaster Relief & Humanitarian'),('community','Community & Social Welfare'),('animal','Animal Welfare'),('other','Other')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=30, choices=ORG_TYPES)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    accreditation_doc = models.FileField(upload_to='accreditation/', blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    total_events = models.PositiveIntegerField(default=0)
    total_volunteers = models.PositiveIntegerField(default=0)
    total_hours = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    rating_count = models.PositiveIntegerField(default=0)
    def __str__(self): return self.name

class OrganizationVerification(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='verification')
    status = models.CharField(max_length=20, choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')], default='pending')
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

class Opportunity(models.Model):
    CATEGORY_CHOICES = [('environmental','Environmental'),('healthcare','Healthcare'),('education','Education'),('community','Community'),('animal_care','Animal Care'),('disaster','Disaster Relief'),('other','Other')]
    STATUS_CHOICES = [('active','Active'),('pending','Pending'),('suspended','Suspended'),('completed','Completed'),('cancelled','Cancelled')]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='opportunities')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    location = models.CharField(max_length=200)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_volunteers = models.PositiveIntegerField(default=50)
    requirements = models.TextField(blank=True)
    what_to_bring = models.TextField(blank=True)
    image = models.ImageField(upload_to='opportunities/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['-created_at']
    def __str__(self): return f"{self.title} — {self.organization.name}"
    @property
    def approved_count(self): return self.applications.filter(status='approved').count()
    @property
    def pending_count(self): return self.applications.filter(status='pending').count()
    @property
    def spots_available(self): return max(0, self.max_volunteers - self.approved_count)

class Application(models.Model):
    STATUS_CHOICES = [('pending','Pending'),('approved','Approved'),('rejected','Rejected'),('completed','Completed')]
    volunteer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    motivation = models.TextField(blank=True)
    has_previous_experience = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    completion_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    completion_feedback = models.TextField(blank=True)
    class Meta: unique_together = ['volunteer','opportunity']; ordering = ['-applied_at']

class Follow(models.Model):
    volunteer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: unique_together = ['volunteer','organization']

class Post(models.Model):
    CATEGORY_CHOICES = [('questions','Questions'),('tips','Tips & Advice'),('events','Events'),('general','General')]
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=300)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['-created_at']

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['created_at']

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['created_at']

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=40, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    related_url = models.CharField(max_length=300, blank=True)
    class Meta: ordering = ['-created_at']

class Achievement(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    icon = models.CharField(max_length=50, default='🏆')
    requirement_type = models.CharField(max_length=50)
    requirement_value = models.PositiveIntegerField(default=1)

class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(default=timezone.now)
    class Meta: unique_together = ['user','achievement']

class Report(models.Model):
    STATUS_CHOICES = [('pending','Pending'),('under_review','Under Review'),('resolved','Resolved'),('dismissed','Dismissed')]
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='reports_received')
    reported_org = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='reports_received')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    evidence = models.FileField(upload_to='report_evidence/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_reports')
    action_taken = models.TextField(blank=True)
    class Meta: ordering = ['-created_at']

class Warning(models.Model):
    ACTION_CHOICES = [('warning','Warning'),('suspend','Suspension'),('delete','Deletion')]
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='warnings_issued')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='warnings_received')
    target_org = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='warnings_received')
    reason = models.CharField(max_length=100)
    description = models.TextField()
    suspension_days = models.PositiveIntegerField(default=0)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default='warning')
    created_at = models.DateTimeField(default=timezone.now)

class Certificate(models.Model):
    CERT_TYPES = [('completion','Certificate of Completion'),('participation','Certificate of Participation'),('excellence','Certificate of Excellence')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    cert_type = models.CharField(max_length=30, choices=CERT_TYPES, default='completion')
    hours = models.PositiveIntegerField(default=0)
    template_title = models.CharField(max_length=200)
    issued_by = models.CharField(max_length=100, default='Admin User')
    issued_role = models.CharField(max_length=100, default='Administrator')
    issued_at = models.DateTimeField(default=timezone.now)

class OrganizationRating(models.Model):
    volunteer = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ratings')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, null=True, blank=True)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: unique_together = ['volunteer','opportunity']
