from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .forms import LoginForm, ManagerUserForm, ProfileForm, RegistrationForm, StyledPasswordChangeForm
from .models import User


# ------------------------------------------------------------------ entry
def home(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    return redirect("accounts:login")


# ------------------------------------------------------------------ registration
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created for {user.username}. You can now log in.")
            return redirect("accounts:login")
        messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


# ------------------------------------------------------------------ login / logout
class CatchLedgerLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome back, {form.get_user().display_name}!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Login failed. Invalid username or password.")
        return super().form_invalid(form)


class CatchLedgerLogoutView(auth_views.LogoutView):
    """POST-only logout (Django 5). Ends the session and shows a message."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have been logged out.")
        return response


# ------------------------------------------------------------------ dashboards
@login_required
def dashboard(request):
    """Send each user to the dashboard that belongs to their role."""
    return redirect(request.user.get_dashboard_url())


@role_required(User.Role.RECORDER)
def dashboard_recorder(request):
    return render(request, "accounts/dashboard_recorder.html")


@role_required(User.Role.CASHIER)
def dashboard_cashier(request):
    return render(request, "accounts/dashboard_cashier.html")


@role_required(User.Role.MANAGER)
def dashboard_manager(request):
    counts = User.objects.aggregate(
        total=Count("id"),
        recorders=Count("id", filter=Q(role=User.Role.RECORDER)),
        cashiers=Count("id", filter=Q(role=User.Role.CASHIER)),
        managers=Count("id", filter=Q(role=User.Role.MANAGER)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    recent = User.objects.order_by("-date_joined")[:5]
    return render(request, "accounts/dashboard_manager.html", {"counts": counts, "recent_users": recent})


# ------------------------------------------------------------------ profile (own profile only)
@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"profile_user": request.user})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Your profile was not saved. Please correct the errors below.")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


class PasswordChangeView(SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your password has been changed."


# ------------------------------------------------------------------ user management (Manager only)
@role_required(User.Role.MANAGER)
def user_list(request):
    users = User.objects.order_by("username")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if role in User.Role.values:
        users = users.filter(role=role)
    return render(request, "accounts/user_list.html", {"users": users, "q": q, "role": role, "roles": User.Role.choices})


@role_required(User.Role.MANAGER)
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = ManagerUserForm(request.POST, instance=target, acting_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {target.username}.")
            return redirect("accounts:user_list")
        messages.error(request, "The changes were not saved. Please correct the errors below.")
    else:
        form = ManagerUserForm(instance=target, acting_user=request.user)
    return render(request, "accounts/user_edit.html", {"form": form, "target": target})


# ------------------------------------------------------------------ error pages
def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
