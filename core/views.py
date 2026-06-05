from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import *
from .serializers import *

# ── helpers ──────────────────────────────────────────────────────────────────

def notify(user, ntype, title, msg, url=''):
    Notification.objects.create(user=user, notification_type=ntype, title=title, message=msg, related_url=url)

def is_admin(u): return u.is_authenticated and (u.role == 'admin' or u.is_superuser)
def is_org(u): return u.is_authenticated and u.role == 'organization'
def is_vol(u): return u.is_authenticated and u.role == 'volunteer'

# ── root ─────────────────────────────────────────────────────────────────────

def home_redirect(request):
    if not request.user.is_authenticated: return redirect('login')
    if is_admin(request.user): return redirect('admin_dashboard')
    if is_org(request.user): return redirect('org_dashboard')
    return redirect('vol_dashboard')

# ── auth ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated: return redirect('home')
    if request.method == 'POST':
        ident = request.POST.get('email','')
        pw = request.POST.get('password','')
        user = None
        try:
            u = User.objects.get(email=ident)
            user = authenticate(request, username=u.username, password=pw)
        except User.DoesNotExist:
            user = authenticate(request, username=ident, password=pw)
        if user:
            if user.status == 'suspended':
                messages.error(request, 'Your account has been suspended.')
            else:
                login(request, user)
                return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def register_volunteer(request):
    if request.method == 'POST':
        email = request.POST.get('email','').strip()
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'core/register_volunteer.html')
        names = request.POST.get('full_name','').strip().split(' ', 1)
        user = User.objects.create_user(
            username=email, email=email, password=request.POST.get('password',''),
            first_name=names[0], last_name=names[1] if len(names)>1 else '',
            phone_number=request.POST.get('phone',''), role='volunteer')
        VolunteerProfile.objects.create(user=user)
        login(request, user)
        return redirect('vol_onboarding')
    return render(request, 'core/register_volunteer.html')

def register_organization(request):
    if request.method == 'POST':
        email = request.POST.get('email','').strip()
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'core/register_organization.html')
        names = request.POST.get('full_name','').strip().split(' ', 1)
        user = User.objects.create_user(
            username=email, email=email, password=request.POST.get('password',''),
            first_name=names[0], last_name=names[1] if len(names)>1 else '',
            phone_number=request.POST.get('phone',''), role='organization', status='pending')
        org = Organization.objects.create(
            user=user, name=request.POST.get('org_name',''),
            org_type=request.POST.get('org_type',''), contact_person=request.POST.get('full_name',''))
        if 'accreditation_doc' in request.FILES:
            org.accreditation_doc = request.FILES['accreditation_doc']; org.save()
        OrganizationVerification.objects.create(organization=org)
        login(request, user)
        messages.success(request, 'Account created! Under review (3–5 business days). You can explore the platform while waiting.')
        return redirect('org_dashboard')
    return render(request, 'core/register_organization.html')

def forgot_password(request):
    if request.method == 'POST':
        messages.info(request, 'If that email exists, a reset link has been sent.')
    return render(request, 'core/forgot_password.html')

# ── volunteer onboarding ──────────────────────────────────────────────────────

@login_required
def vol_onboarding(request):
    if request.method == 'POST':
        p, _ = VolunteerProfile.objects.get_or_create(user=request.user)
        p.date_of_birth = request.POST.get('dob') or None
        p.time_available = request.POST.get('time_available','')
        p.skills = request.POST.get('skills','')
        p.interests = ','.join(request.POST.getlist('interests'))
        request.user.location = request.POST.get('location','')
        request.user.save(); p.save()
        return redirect('vol_dashboard')
    return render(request, 'core/vol_onboarding.html', {'categories': Opportunity.CATEGORY_CHOICES})

# ── volunteer ─────────────────────────────────────────────────────────────────

@login_required
def vol_dashboard(request):
    if not is_vol(request.user): return redirect('home')
    p, _ = VolunteerProfile.objects.get_or_create(user=request.user)
    interests = p.interests_list()
    opps = Opportunity.objects.filter(status='active').select_related('organization')
    if interests:
        opps = opps.filter(category__in=[i.lower() for i in interests])
    all_opps = Opportunity.objects.filter(status='active').select_related('organization')[:6]
    user_app_ids = list(Application.objects.filter(volunteer=request.user).values_list('opportunity_id', flat=True))
    unread = request.user.notifications.filter(is_read=False).count()
    return render(request, 'core/vol_dashboard.html', {
        'profile': p, 'opportunities': all_opps, 'user_app_ids': user_app_ids, 'unread': unread})

@login_required
def opportunities_list(request):
    opps = Opportunity.objects.filter(status='active').select_related('organization')
    q = request.GET.get('q',''); cat = request.GET.get('cat','')
    if q: opps = opps.filter(Q(title__icontains=q)|Q(location__icontains=q)|Q(description__icontains=q))
    if cat: opps = opps.filter(category=cat)
    paginator = Paginator(opps, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    user_app_ids = list(Application.objects.filter(volunteer=request.user).values_list('opportunity_id', flat=True)) if is_vol(request.user) else []
    return render(request, 'core/opportunities_list.html', {
        'page_obj': page_obj, 'q': q, 'cat': cat,
        'categories': Opportunity.CATEGORY_CHOICES, 'user_app_ids': user_app_ids})

@login_required
def opp_detail(request, pk):
    opp = get_object_or_404(Opportunity, pk=pk)
    user_app = Application.objects.filter(volunteer=request.user, opportunity=opp).first() if is_vol(request.user) else None
    return render(request, 'core/opp_detail.html', {'opp': opp, 'user_app': user_app})

@login_required
def apply_opp(request, pk):
    if not is_vol(request.user): return redirect('opportunities_list')
    opp = get_object_or_404(Opportunity, pk=pk, status='active')
    if Application.objects.filter(volunteer=request.user, opportunity=opp).exists():
        messages.warning(request, 'You already applied for this opportunity.')
        return redirect('opp_detail', pk=pk)
    if request.method == 'POST':
        Application.objects.create(
            volunteer=request.user, opportunity=opp,
            full_name=request.POST.get('full_name', request.user.get_full_name()),
            email=request.POST.get('email', request.user.email),
            phone=request.POST.get('phone', request.user.phone_number),
            motivation=request.POST.get('motivation',''),
            has_previous_experience='has_experience' in request.POST)
        notify(request.user, 'application_status', 'Application Submitted',
               f'Your application for "{opp.title}" has been received and is under review.')
        messages.success(request, 'Application submitted successfully! Please wait for approval.')
        return redirect('my_applications')
    return render(request, 'core/apply_opp.html', {'opp': opp})

@login_required
def my_applications(request):
    apps = Application.objects.filter(volunteer=request.user).select_related('opportunity__organization')
    return render(request, 'core/my_applications.html', {'applications': apps})

@login_required
def application_status(request, pk):
    app = get_object_or_404(Application, pk=pk, volunteer=request.user)
    return render(request, 'core/application_status.html', {'app': app})

@login_required
def vol_profile(request):
    if not is_vol(request.user): return redirect('home')
    p, _ = VolunteerProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.phone_number = request.POST.get('phone', request.user.phone_number)
        request.user.location = request.POST.get('location', request.user.location)
        if 'profile_picture' in request.FILES:
            request.user.profile_picture = request.FILES['profile_picture']
        request.user.save()
        p.bio = request.POST.get('bio', p.bio)
        p.time_available = request.POST.get('time_available', p.time_available)
        p.skills = request.POST.get('skills', p.skills)
        p.interests = request.POST.get('interests', p.interests)
        p.save()
        messages.success(request, 'Profile updated!')
        return redirect('vol_profile')
    achievements = UserAchievement.objects.filter(user=request.user).select_related('achievement')
    completed = Application.objects.filter(volunteer=request.user, status='completed').select_related('opportunity__organization')
    certs = Certificate.objects.filter(user=request.user).select_related('organization')
    return render(request, 'core/vol_profile.html', {'profile': p, 'achievements': achievements, 'completed': completed, 'certs': certs})

@login_required
def identity_verification(request):
    if not is_vol(request.user): return redirect('home')
    existing = IdentityVerification.objects.filter(user=request.user).first()
    if request.method == 'POST':
        v, _ = IdentityVerification.objects.get_or_create(user=request.user)
        v.id_type = request.POST.get('id_type','')
        if 'id_document' in request.FILES: v.id_document = request.FILES['id_document']
        v.status = 'pending'; v.submitted_at = timezone.now(); v.save()
        messages.success(request, 'Verification submitted successfully!')
        return redirect('vol_profile')
    return render(request, 'core/identity_verification.html', {'existing': existing})

@login_required
def rate_org(request, opp_pk):
    opp = get_object_or_404(Opportunity, pk=opp_pk)
    get_object_or_404(Application, volunteer=request.user, opportunity=opp, status='completed')
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 3))
        OrganizationRating.objects.update_or_create(
            volunteer=request.user, opportunity=opp,
            defaults={'organization': opp.organization, 'rating': rating, 'comment': request.POST.get('comment','')})
        org = opp.organization
        agg = OrganizationRating.objects.filter(organization=org).aggregate(Avg('rating'))
        org.rating = round(agg['rating__avg'] or 0, 2)
        org.rating_count = OrganizationRating.objects.filter(organization=org).count()
        org.save()
        messages.success(request, 'Rating submitted!')
        return redirect('my_applications')
    return render(request, 'core/rate_org.html', {'opp': opp})

@login_required
def report_opp(request, pk):
    opp = get_object_or_404(Opportunity, pk=pk)
    if request.method == 'POST':
        Report.objects.create(reporter=request.user, reported_org=opp.organization, opportunity=opp,
                              reason=request.POST.get('reason',''), description=request.POST.get('description',''))
        messages.success(request, 'Report submitted. Thank you.')
        return redirect('opp_detail', pk=pk)
    reasons = [('misrepresented','Misrepresented Event'),('unsafe','Unsafe environment'),('no_supervision','Lack of supervision/support'),('fraud','Fraudulent activity'),('other','Other')]
    return render(request, 'core/report_opp.html', {'opp': opp, 'reasons': reasons})

# ── community ─────────────────────────────────────────────────────────────────

@login_required
def forum(request):
    cat = request.GET.get('cat',''); q = request.GET.get('q','')
    posts = Post.objects.select_related('author').annotate(lc=Count('likes'), cc=Count('comments'))
    if cat: posts = posts.filter(category=cat)
    if q: posts = posts.filter(Q(title__icontains=q)|Q(content__icontains=q))
    page_obj = Paginator(posts, 10).get_page(request.GET.get('page'))
    return render(request, 'core/forum.html', {'page_obj': page_obj, 'cat': cat, 'q': q, 'categories': Post.CATEGORY_CHOICES})

@login_required
def create_post(request):
    if request.method == 'POST':
        t = request.POST.get('title','').strip(); c = request.POST.get('content','').strip()
        if t and c:
            Post.objects.create(author=request.user, title=t, content=c, category=request.POST.get('category','general'))
            messages.success(request, 'Post created!'); return redirect('forum')
    return render(request, 'core/create_post.html', {'categories': Post.CATEGORY_CHOICES})

@login_required
def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        c = request.POST.get('content','').strip()
        if c:
            Comment.objects.create(post=post, author=request.user, content=c)
            if post.author != request.user:
                notify(post.author, 'new_reply', 'New Reply', f'{request.user.get_full_name()} replied to "{post.title}".')
            return redirect('post_detail', pk=pk)
    liked = request.user in post.likes.all()
    return render(request, 'core/post_detail.html', {'post': post, 'comments': post.comments.select_related('author'), 'liked': liked})

@login_required
@require_POST
def like_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user in post.likes.all(): post.likes.remove(request.user); liked = False
    else: post.likes.add(request.user); liked = True
    return JsonResponse({'liked': liked, 'count': post.likes.count()})

# ── messaging ─────────────────────────────────────────────────────────────────

@login_required
def chats(request):
    sent = Message.objects.filter(sender=request.user).values_list('receiver_id', flat=True)
    recv = Message.objects.filter(receiver=request.user).values_list('sender_id', flat=True)
    partner_ids = set(list(sent)+list(recv))
    partners = User.objects.filter(id__in=partner_ids)
    convos = []
    for p in partners:
        last = Message.objects.filter(Q(sender=request.user,receiver=p)|Q(sender=p,receiver=request.user)).order_by('-created_at').first()
        unread = Message.objects.filter(sender=p, receiver=request.user, is_read=False).count()
        convos.append({'partner': p, 'last': last, 'unread': unread})
    convos.sort(key=lambda x: x['last'].created_at if x['last'] else timezone.now(), reverse=True)
    return render(request, 'core/chats.html', {'conversations': convos})

@login_required
def chat_detail(request, user_id):
    partner = get_object_or_404(User, pk=user_id)
    Message.objects.filter(sender=partner, receiver=request.user, is_read=False).update(is_read=True)
    msgs = Message.objects.filter(Q(sender=request.user,receiver=partner)|Q(sender=partner,receiver=request.user)).order_by('created_at')
    if request.method == 'POST':
        c = request.POST.get('content','').strip()
        if c: Message.objects.create(sender=request.user, receiver=partner, content=c)
        return redirect('chat_detail', user_id=user_id)
    return render(request, 'core/chat_detail.html', {'partner': partner, 'messages': msgs})

# ── notifications ─────────────────────────────────────────────────────────────

@login_required
def notifications(request):
    notifs = request.user.notifications.all()
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'core/notifications.html', {'notifications': notifs})

# ── organization ──────────────────────────────────────────────────────────────

@login_required
def org_dashboard(request):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    opps = org.opportunities.annotate(app_count=Count('applications')).order_by('-created_at')
    unread = request.user.notifications.filter(is_read=False).count()
    return render(request, 'core/org_dashboard.html', {'org': org, 'opportunities': opps, 'unread': unread})

@login_required
def create_opp(request):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    if request.method == 'POST':
        opp = Opportunity(organization=org,
            title=request.POST.get('title'), description=request.POST.get('description'),
            category=request.POST.get('category'), location=request.POST.get('location'),
            date=request.POST.get('date'), start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'), max_volunteers=int(request.POST.get('max_volunteers',50)),
            requirements=request.POST.get('requirements',''), what_to_bring=request.POST.get('what_to_bring',''))
        if 'image' in request.FILES: opp.image = request.FILES['image']
        opp.save()
        org.total_events += 1; org.save()
        messages.success(request, 'Opportunity published!')
        return redirect('org_dashboard')
    return render(request, 'core/create_opp.html', {'categories': Opportunity.CATEGORY_CHOICES})

@login_required
def edit_opp(request, pk):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    opp = get_object_or_404(Opportunity, pk=pk, organization=org)
    if request.method == 'POST':
        for f in ['title','description','category','location','date','start_time','end_time','requirements','what_to_bring']:
            if request.POST.get(f): setattr(opp, f, request.POST[f])
        opp.max_volunteers = int(request.POST.get('max_volunteers', opp.max_volunteers))
        if 'image' in request.FILES: opp.image = request.FILES['image']
        opp.save()
        messages.success(request, 'Opportunity updated!')
        return redirect('org_dashboard')
    return render(request, 'core/create_opp.html', {'opp': opp, 'categories': Opportunity.CATEGORY_CHOICES})

@login_required
def org_applicants(request, opp_pk):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    opp = get_object_or_404(Opportunity, pk=opp_pk, organization=org)
    apps = opp.applications.select_related('volunteer__volunteer_profile')
    return render(request, 'core/org_applicants.html', {'opp': opp, 'applications': apps})

@login_required
def applicant_detail(request, app_pk):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    app = get_object_or_404(Application, pk=app_pk, opportunity__organization=org)
    if request.method == 'POST':
        act = request.POST.get('action')
        if act == 'approve':
            app.status = 'approved'; app.reviewed_at = timezone.now(); app.save()
            notify(app.volunteer, 'application_accepted', 'Application Accepted!',
                   f'Your application for "{app.opportunity.title}" has been accepted by {org.name}.',
                   f'/opportunities/{app.opportunity.pk}/')
            messages.success(request, 'Application approved!')
        elif act == 'reject':
            app.status = 'rejected'; app.reviewed_at = timezone.now(); app.save()
            notify(app.volunteer, 'application_status', 'Application Update',
                   f'Your application for "{app.opportunity.title}" was not approved.')
            messages.info(request, 'Application rejected.')
        elif act == 'complete':
            app.status = 'completed'; app.save()
            p, _ = VolunteerProfile.objects.get_or_create(user=app.volunteer)
            p.total_projects += 1; p.save()
            notify(app.volunteer, 'rate_experience', 'Rate Your Experience',
                   f'How was your volunteer experience at {org.name}?', f'/rate-org/{app.opportunity.pk}/')
        return redirect('applicant_detail', app_pk=app_pk)
    return render(request, 'core/applicant_detail.html', {'app': app})

@login_required
def rate_volunteer(request, app_pk):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    app = get_object_or_404(Application, pk=app_pk, opportunity__organization=org)
    if request.method == 'POST':
        app.completion_rating = int(request.POST.get('rating', 3))
        app.completion_feedback = request.POST.get('feedback','')
        app.save()
        p, _ = VolunteerProfile.objects.get_or_create(user=app.volunteer)
        agg = Application.objects.filter(volunteer=app.volunteer, completion_rating__isnull=False).aggregate(Avg('completion_rating'))
        p.rating = round(agg['completion_rating__avg'] or 0, 2)
        p.rating_count = Application.objects.filter(volunteer=app.volunteer, completion_rating__isnull=False).count()
        p.save()
        messages.success(request, 'Volunteer rated!')
        return redirect('applicant_detail', app_pk=app_pk)
    return render(request, 'core/rate_volunteer.html', {'app': app})

@login_required
def org_manage_volunteers(request):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    apps = Application.objects.filter(opportunity__organization=org).select_related('volunteer__volunteer_profile','opportunity')
    q = request.GET.get('q','')
    if q: apps = apps.filter(Q(full_name__icontains=q)|Q(volunteer__email__icontains=q))
    return render(request, 'core/org_manage_volunteers.html', {'applications': apps, 'q': q})

@login_required
def org_analytics(request):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    total = Application.objects.filter(opportunity__organization=org).count()
    approved = Application.objects.filter(opportunity__organization=org, status='approved').count()
    completed = Application.objects.filter(opportunity__organization=org, status='completed').count()
    success_rate = round((approved/total*100) if total else 0)
    return render(request, 'core/org_analytics.html', {
        'org': org, 'total': total, 'approved': approved, 'completed': completed, 'success_rate': success_rate})

@login_required
def org_profile(request):
    if not is_org(request.user): return redirect('home')
    org = get_object_or_404(Organization, user=request.user)
    if request.method == 'POST':
        org.name = request.POST.get('name', org.name)
        org.description = request.POST.get('description', org.description)
        org.website = request.POST.get('website', org.website)
        org.address = request.POST.get('address', org.address)
        org.save()
        request.user.phone_number = request.POST.get('phone', request.user.phone_number)
        request.user.save()
        messages.success(request, 'Profile updated!')
        return redirect('org_profile')
    return render(request, 'core/org_profile.html', {'org': org})

@login_required
def public_org_profile(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    is_following = Follow.objects.filter(volunteer=request.user, organization=org).exists() if is_vol(request.user) else False
    return render(request, 'core/public_org_profile.html', {'org': org, 'is_following': is_following})

@login_required
@require_POST
def follow_org(request, pk):
    org = get_object_or_404(Organization, pk=pk)
    f, created = Follow.objects.get_or_create(volunteer=request.user, organization=org)
    if not created: f.delete(); return JsonResponse({'following': False})
    return JsonResponse({'following': True})

@login_required
def report_volunteer(request, user_pk):
    target = get_object_or_404(User, pk=user_pk)
    if request.method == 'POST':
        Report.objects.create(reporter=request.user, reported_user=target,
                              reason=request.POST.get('reason',''), description=request.POST.get('description',''))
        messages.success(request, 'Report submitted.')
        return redirect('org_dashboard')
    reasons = [('theft','Theft or misuse of property'),('harassment','Harassment or abusive behavior'),('no_show','Unexcused abandonment/No-show'),('substance','Substance abuse on duty'),('other','Other')]
    return render(request, 'core/report_volunteer.html', {'target': target, 'reasons': reasons})

# ── admin ─────────────────────────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    if not is_admin(request.user): return redirect('home')
    return render(request, 'core/admin_dashboard.html', {
        'total_users': User.objects.filter(role='volunteer').count(),
        'active_orgs': Organization.objects.filter(user__status='active').count(),
        'active_opps': Opportunity.objects.filter(status='active').count(),
        'apps_this_week': Application.objects.filter(applied_at__gte=timezone.now()-timezone.timedelta(days=7)).count(),
        'new_users': User.objects.filter(role='volunteer').order_by('-date_joined')[:5],
        'recent_reports': Report.objects.filter(status='pending').order_by('-created_at')[:5],
        'pending_verif': IdentityVerification.objects.filter(status='pending').count(),
        'pending_org_verif': OrganizationVerification.objects.filter(status='pending').count(),
    })

@login_required
def admin_organizations(request):
    if not is_admin(request.user): return redirect('home')
    orgs = Organization.objects.select_related('user').all()
    q = request.GET.get('q',''); sf = request.GET.get('status','')
    if q: orgs = orgs.filter(Q(name__icontains=q)|Q(user__email__icontains=q))
    if sf: orgs = orgs.filter(user__status=sf)
    page_obj = Paginator(orgs, 10).get_page(request.GET.get('page'))
    return render(request, 'core/admin_organizations.html', {
        'page_obj': page_obj, 'q': q, 'sf': sf,
        'total': Organization.objects.count(),
        'active': Organization.objects.filter(user__status='active').count(),
        'pending': Organization.objects.filter(user__status='pending').count()})

@login_required
def admin_org_detail(request, pk):
    if not is_admin(request.user): return redirect('home')
    org = get_object_or_404(Organization, pk=pk)
    if request.method == 'POST':
        act = request.POST.get('action')
        if act == 'warning':
            Warning.objects.create(admin=request.user, target_org=org, reason=request.POST.get('reason',''),
                                   description=request.POST.get('description',''), action_type='warning')
            notify(org.user, 'warning', 'Organization Warning', f'Warning issued: {request.POST.get("reason","")}')
            messages.success(request, 'Warning issued.')
        elif act == 'suspend':
            d = int(request.POST.get('suspension_days',7))
            Warning.objects.create(admin=request.user, target_org=org, reason=request.POST.get('reason',''),
                                   description=request.POST.get('description',''), suspension_days=d, action_type='suspend')
            org.user.status = 'suspended'; org.user.save()
            messages.success(request, f'Organization suspended for {d} days.')
        elif act == 'activate':
            org.user.status = 'active'; org.user.save(); messages.success(request, 'Organization activated.')
        elif act == 'delete':
            org.user.delete(); messages.success(request, 'Organization deleted.'); return redirect('admin_organizations')
        return redirect('admin_org_detail', pk=pk)
    return render(request, 'core/admin_org_detail.html', {
        'org': org,
        'warnings': Warning.objects.filter(target_org=org).order_by('-created_at'),
        'reports': Report.objects.filter(reported_org=org).order_by('-created_at')})

@login_required
def admin_users(request):
    if not is_admin(request.user): return redirect('home')
    users = User.objects.filter(role='volunteer').select_related('volunteer_profile')
    q = request.GET.get('q','')
    if q: users = users.filter(Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q))
    page_obj = Paginator(users, 10).get_page(request.GET.get('page'))
    return render(request, 'core/admin_users.html', {'page_obj': page_obj, 'q': q})

@login_required
def admin_user_detail(request, pk):
    if not is_admin(request.user): return redirect('home')
    target = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        act = request.POST.get('action')
        if act == 'warning':
            Warning.objects.create(admin=request.user, target_user=target, reason=request.POST.get('reason',''),
                                   description=request.POST.get('description',''), action_type='warning')
            notify(target, 'warning', 'Account Warning', f'You received a warning: {request.POST.get("reason","")}')
            messages.success(request, 'Warning issued.')
        elif act == 'suspend':
            d = int(request.POST.get('suspension_days',7))
            Warning.objects.create(admin=request.user, target_user=target, reason=request.POST.get('reason',''),
                                   description=request.POST.get('description',''), suspension_days=d, action_type='suspend')
            target.status = 'suspended'; target.save(); messages.success(request, f'User suspended for {d} days.')
        elif act == 'activate':
            target.status = 'active'; target.save(); messages.success(request, 'User activated.')
        elif act == 'delete':
            target.delete(); messages.success(request, 'User deleted.'); return redirect('admin_users')
        return redirect('admin_user_detail', pk=pk)
    return render(request, 'core/admin_user_detail.html', {
        'target': target,
        'profile': getattr(target, 'volunteer_profile', None),
        'warnings': Warning.objects.filter(target_user=target).order_by('-created_at'),
        'reports': Report.objects.filter(reported_user=target).order_by('-created_at'),
        'certs': Certificate.objects.filter(user=target)})

@login_required
def admin_verification(request):
    if not is_admin(request.user): return redirect('home')
    tab = request.GET.get('tab','user')
    return render(request, 'core/admin_verification.html', {
        'tab': tab,
        'user_verifs': IdentityVerification.objects.filter(status='pending').select_related('user'),
        'org_verifs': OrganizationVerification.objects.filter(status='pending').select_related('organization__user')})

@login_required
def admin_verify_user(request, pk):
    if not is_admin(request.user): return redirect('home')
    v = get_object_or_404(IdentityVerification, pk=pk)
    if request.method == 'POST':
        act = request.POST.get('action')
        v.status = 'approved' if act == 'approve' else 'rejected'
        v.reviewed_at = timezone.now(); v.reviewed_by = request.user; v.save()
        if act == 'approve':
            v.user.is_verified = True; v.user.save()
            notify(v.user, 'verification', 'Identity Verified!', 'Your identity has been verified.')
        messages.success(request, f'Verification {v.status}.')
        return redirect('admin_verification')
    return render(request, 'core/admin_verify_user.html', {'v': v})

@login_required
def admin_verify_org(request, pk):
    if not is_admin(request.user): return redirect('home')
    v = get_object_or_404(OrganizationVerification, pk=pk)
    if request.method == 'POST':
        act = request.POST.get('action')
        v.status = 'approved' if act == 'approve' else 'rejected'
        v.reviewed_at = timezone.now(); v.reviewed_by = request.user; v.save()
        if act == 'approve':
            v.organization.is_verified = True; v.organization.save()
            v.organization.user.is_verified = True; v.organization.user.status = 'active'; v.organization.user.save()
            notify(v.organization.user, 'verification', 'Organization Approved!', 'Your organization has been verified.')
        messages.success(request, f'Organization {v.status}.')
        return redirect('admin_verification')
    return render(request, 'core/admin_verify_org.html', {'v': v})

@login_required
def admin_opportunities(request):
    if not is_admin(request.user): return redirect('home')
    opps = Opportunity.objects.select_related('organization').annotate(app_count=Count('applications'))
    q = request.GET.get('q',''); sf = request.GET.get('status','')
    if q: opps = opps.filter(Q(title__icontains=q)|Q(organization__name__icontains=q))
    if sf: opps = opps.filter(status=sf)
    page_obj = Paginator(opps, 10).get_page(request.GET.get('page'))
    return render(request, 'core/admin_opportunities.html', {'page_obj': page_obj, 'q': q, 'sf': sf, 'statuses': Opportunity.STATUS_CHOICES})

@login_required
def admin_reports(request):
    if not is_admin(request.user): return redirect('home')
    tab = request.GET.get('tab','active'); ttype = request.GET.get('type','user')
    if tab == 'active': reports = Report.objects.filter(status='pending')
    elif tab == 'history': reports = Report.objects.filter(status__in=['resolved','dismissed'])
    else: reports = Report.objects.all()
    if ttype == 'user': reports = reports.filter(reported_user__isnull=False)
    else: reports = reports.filter(reported_org__isnull=False)
    page_obj = Paginator(reports.select_related('reported_user','reported_org','reporter'), 10).get_page(request.GET.get('page'))
    return render(request, 'core/admin_reports.html', {'page_obj': page_obj, 'tab': tab, 'ttype': ttype})

@login_required
def admin_report_detail(request, pk):
    if not is_admin(request.user): return redirect('home')
    report = get_object_or_404(Report, pk=pk)
    if request.method == 'POST':
        act = request.POST.get('action')
        if act == 'dismiss': report.status = 'dismissed'
        elif act in ('resolve','done'): report.status = 'resolved'; report.action_taken = request.POST.get('action_taken','Resolved by admin.')
        report.resolved_at = timezone.now(); report.resolved_by = request.user; report.save()
        messages.success(request, 'Report updated.')
        return redirect('admin_reports')
    return render(request, 'core/admin_report_detail.html', {'report': report})

@login_required
def admin_analytics(request):
    if not is_admin(request.user): return redirect('home')
    return render(request, 'core/admin_analytics.html', {
        'total_users': User.objects.filter(role='volunteer').count(),
        'total_orgs': Organization.objects.count(),
        'total_opps': Opportunity.objects.count(),
        'total_apps': Application.objects.count(),
        'approved_apps': Application.objects.filter(status='approved').count(),
        'completed_apps': Application.objects.filter(status='completed').count(),
        'pending_reports': Report.objects.filter(status='pending').count(),
        'resolved_reports': Report.objects.filter(status='resolved').count(),
    })

@login_required
def create_certificate(request, user_pk):
    if not is_admin(request.user): return redirect('home')
    target = get_object_or_404(User, pk=user_pk)
    if request.method == 'POST':
        cert = Certificate(user=target, cert_type=request.POST.get('cert_type','completion'),
            hours=int(request.POST.get('hours',0)), template_title=request.POST.get('template_title',''),
            issued_by=request.POST.get('issued_by','Admin User'), issued_role=request.POST.get('issued_role','Administrator'))
        oid = request.POST.get('organization')
        if oid:
            try: cert.organization = Organization.objects.get(pk=oid)
            except: pass
        cert.save()
        notify(target, 'general', 'Certificate Issued!', 'A certificate has been issued to you.')
        messages.success(request, 'Certificate created!')
        return redirect('admin_user_detail', pk=user_pk)
    return render(request, 'core/create_certificate.html', {
        'target': target, 'orgs': Organization.objects.all(), 'cert_types': Certificate.CERT_TYPES})

@login_required
def view_certificate(request, pk):
    cert = get_object_or_404(Certificate, pk=pk)
    if not (is_admin(request.user) or cert.user == request.user): return redirect('home')
    return render(request, 'core/certificate.html', {'cert': cert})

# ── REST API ──────────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if is_admin(self.request.user): return User.objects.all()
        return User.objects.filter(pk=self.request.user.pk)

class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

class OpportunityViewSet(viewsets.ModelViewSet):
    queryset = Opportunity.objects.filter(status='active')
    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = Opportunity.objects.all()
        cat = self.request.query_params.get('category')
        q = self.request.query_params.get('q')
        if cat: qs = qs.filter(category=cat)
        if q: qs = qs.filter(Q(title__icontains=q)|Q(location__icontains=q))
        return qs
    def perform_create(self, serializer):
        serializer.save(organization=get_object_or_404(Organization, user=self.request.user))

class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        u = self.request.user
        if u.role == 'volunteer': return Application.objects.filter(volunteer=u)
        if u.role == 'organization': return Application.objects.filter(opportunity__organization__user=u)
        return Application.objects.all()
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        app = self.get_object(); app.status = 'approved'; app.reviewed_at = timezone.now(); app.save()
        return Response({'status': 'approved'})
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        app = self.get_object(); app.status = 'rejected'; app.reviewed_at = timezone.now(); app.save()
        return Response({'status': 'rejected'})

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    def perform_create(self, serializer): serializer.save(author=self.request.user)
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        post = self.get_object()
        if request.user in post.likes.all(): post.likes.remove(request.user); return Response({'liked': False, 'count': post.likes.count()})
        post.likes.add(request.user); return Response({'liked': True, 'count': post.likes.count()})
    @action(detail=True, methods=['get','post'])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == 'POST':
            c = Comment.objects.create(post=post, author=request.user, content=request.data.get('content',''))
            return Response(CommentSerializer(c).data, status=status.HTTP_201_CREATED)
        return Response(CommentSerializer(post.comments.all(), many=True).data)

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return Notification.objects.filter(user=self.request.user)
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'ok'})

class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if is_admin(self.request.user): return Report.objects.all()
        return Report.objects.filter(reporter=self.request.user)
    def perform_create(self, serializer): serializer.save(reporter=self.request.user)
