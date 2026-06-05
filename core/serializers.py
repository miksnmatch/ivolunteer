from rest_framework import serializers
from .models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','email','first_name','last_name','role','phone_number','location','status','is_verified','date_joined']
        read_only_fields = ['id','date_joined']

class OrganizationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    followers_count = serializers.SerializerMethodField()
    class Meta:
        model = Organization
        fields = ['id','name','org_type','description','website','address','contact_person','is_verified','total_events','total_volunteers','total_hours','rating','user_email','followers_count']
    def get_followers_count(self, obj): return obj.followers.count()

class OpportunitySerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    approved_count = serializers.ReadOnlyField()
    spots_available = serializers.ReadOnlyField()
    class Meta:
        model = Opportunity
        fields = ['id','title','description','category','location','date','start_time','end_time','max_volunteers','requirements','what_to_bring','status','created_at','organization_name','approved_count','spots_available']
        read_only_fields = ['id','created_at']

class ApplicationSerializer(serializers.ModelSerializer):
    volunteer_name = serializers.CharField(source='volunteer.get_full_name', read_only=True)
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    class Meta:
        model = Application
        fields = ['id','full_name','email','phone','motivation','has_previous_experience','status','applied_at','reviewed_at','completion_rating','volunteer_name','opportunity_title']

class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    class Meta:
        model = Post
        fields = ['id','title','content','category','created_at','author_name','likes_count','comments_count']
    def get_author_name(self, obj): return obj.author.get_full_name() or obj.author.username
    def get_likes_count(self, obj): return obj.likes.count()
    def get_comments_count(self, obj): return obj.comments.count()

class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    class Meta:
        model = Comment
        fields = ['id','content','created_at','author_name']
    def get_author_name(self, obj): return obj.author.get_full_name() or obj.author.username

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id','notification_type','title','message','is_read','created_at','related_url']

class ReportSerializer(serializers.ModelSerializer):
    reported_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    class Meta:
        model = Report
        fields = ['id','reason','description','status','created_at','reported_name','reporter_name','action_taken']
    def get_reported_name(self, obj): return (obj.reported_user.get_full_name() if obj.reported_user else '') or (obj.reported_org.name if obj.reported_org else '')
    def get_reporter_name(self, obj): return obj.reporter.get_full_name() or obj.reporter.username
