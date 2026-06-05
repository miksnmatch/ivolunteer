from django.contrib import admin as dj_admin
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='api-users')
router.register(r'organizations', views.OrganizationViewSet, basename='api-organizations')
router.register(r'opportunities', views.OpportunityViewSet, basename='api-opportunities')
router.register(r'applications', views.ApplicationViewSet, basename='api-applications')
router.register(r'posts', views.PostViewSet, basename='api-posts')
router.register(r'notifications', views.NotificationViewSet, basename='api-notifications')
router.register(r'reports', views.ReportViewSet, basename='api-reports')

urlpatterns = [
    path('admin/', admin.site.urls),
    # auth
    path('', views.home_redirect, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/volunteer/', views.register_volunteer, name='register_volunteer'),
    path('register/organization/', views.register_organization, name='register_organization'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    # volunteer onboarding
    path('onboarding/', views.vol_onboarding, name='vol_onboarding'),
    # volunteer
    path('dashboard/', views.vol_dashboard, name='vol_dashboard'),
    path('opportunities/', views.opportunities_list, name='opportunities_list'),
    path('opportunities/<int:pk>/', views.opp_detail, name='opp_detail'),
    path('opportunities/<int:pk>/apply/', views.apply_opp, name='apply_opp'),
    path('opportunities/<int:pk>/report/', views.report_opp, name='report_opp'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('applications/<int:pk>/', views.application_status, name='application_status'),
    path('profile/', views.vol_profile, name='vol_profile'),
    path('verify-identity/', views.identity_verification, name='identity_verification'),
    path('rate-org/<int:opp_pk>/', views.rate_org, name='rate_org'),
    path('certificates/<int:pk>/', views.view_certificate, name='view_certificate'),
    # forum
    path('forum/', views.forum, name='forum'),
    path('forum/create/', views.create_post, name='create_post'),
    path('forum/<int:pk>/', views.post_detail, name='post_detail'),
    path('forum/<int:pk>/like/', views.like_post, name='like_post'),
    # messages
    path('chats/', views.chats, name='chats'),
    path('chats/<int:user_id>/', views.chat_detail, name='chat_detail'),
    # notifications
    path('notifications/', views.notifications, name='notifications'),
    # org
    path('org/dashboard/', views.org_dashboard, name='org_dashboard'),
    path('org/opportunity/create/', views.create_opp, name='create_opp'),
    path('org/opportunity/<int:pk>/edit/', views.edit_opp, name='edit_opp'),
    path('org/opportunity/<int:opp_pk>/applicants/', views.org_applicants, name='org_applicants'),
    path('org/applicants/<int:app_pk>/', views.applicant_detail, name='applicant_detail'),
    path('org/applicants/<int:app_pk>/rate/', views.rate_volunteer, name='rate_volunteer'),
    path('org/volunteers/', views.org_manage_volunteers, name='org_manage_volunteers'),
    path('org/analytics/', views.org_analytics, name='org_analytics'),
    path('org/profile/', views.org_profile, name='org_profile'),
    path('org/<int:pk>/', views.public_org_profile, name='public_org_profile'),
    path('org/<int:pk>/follow/', views.follow_org, name='follow_org'),
    path('report-volunteer/<int:user_pk>/', views.report_volunteer, name='report_volunteer'),
    # admin panel
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/organizations/', views.admin_organizations, name='admin_organizations'),
    path('admin-panel/organizations/<int:pk>/', views.admin_org_detail, name='admin_org_detail'),
    path('admin-panel/users/', views.admin_users, name='admin_users'),
    path('admin-panel/users/<int:pk>/', views.admin_user_detail, name='admin_user_detail'),
    path('admin-panel/verification/', views.admin_verification, name='admin_verification'),
    path('admin-panel/verification/user/<int:pk>/', views.admin_verify_user, name='admin_verify_user'),
    path('admin-panel/verification/org/<int:pk>/', views.admin_verify_org, name='admin_verify_org'),
    path('admin-panel/opportunities/', views.admin_opportunities, name='admin_opportunities'),
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),
    path('admin-panel/reports/<int:pk>/', views.admin_report_detail, name='admin_report_detail'),
    path('admin-panel/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin-panel/users/<int:user_pk>/certificate/', views.create_certificate, name='create_certificate'),
    # api
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('accounts/', include('allauth.urls')),
    
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
