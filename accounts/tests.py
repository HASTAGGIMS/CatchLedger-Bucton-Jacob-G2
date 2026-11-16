import io
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

User = get_user_model()
PASSWORD = "Sup3r-Secret-pw!"


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, role=role,
        first_name=username.title(), last_name="Tester", **extra,
    )


def valid_registration(**overrides):
    data = {
        "username": "juan", "first_name": "Juan", "last_name": "Dela Cruz", "email": "juan@example.com",
        "contact_number": "0917 123 4567", "role": "Recorder", "password1": PASSWORD, "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class DatabaseTests(TestCase):
    def test_uses_postgresql_not_sqlite(self):
        self.assertEqual(connection.vendor, "postgresql")


class RegistrationTests(TestCase):
    url = reverse("accounts:register")

    def test_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_successful_registration_hashes_password_and_shows_message(self):
        response = self.client.post(self.url, valid_registration(), follow=True)
        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(username="juan")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.role, "Recorder")
        self.assertIn("Account created", " ".join(str(m) for m in get_messages(response.wsgi_request)))

    def test_cashier_can_self_register(self):
        self.client.post(self.url, valid_registration(role="Cashier"))
        self.assertEqual(User.objects.get(username="juan").role, "Cashier")

    def test_manager_role_cannot_be_self_assigned(self):
        response = self.client.post(self.url, valid_registration(role="Manager"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="juan").exists())
        self.assertIn("role", response.context["form"].errors)

    def test_required_fields(self):
        response = self.client.post(self.url, {})
        form = response.context["form"]
        for field in ("username", "first_name", "last_name", "email", "role", "password1", "password2"):
            self.assertIn(field, form.errors, field)
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "Registration failed")

    def test_invalid_email_format(self):
        response = self.client.post(self.url, valid_registration(email="not-an-email"))
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_duplicate_username(self):
        make_user("juan", "Recorder")
        response = self.client.post(self.url, valid_registration(email="other@example.com"))
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_is_case_insensitive(self):
        make_user("maria", "Cashier")  # maria@example.com
        response = self.client.post(self.url, valid_registration(email="MARIA@Example.com"))
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="juan").exists())

    def test_password_confirmation_must_match(self):
        response = self.client.post(self.url, valid_registration(password2="Different-pw-123"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_weak_passwords_rejected(self):
        for weak in ("short1", "12345678", "password"):
            response = self.client.post(self.url, valid_registration(password1=weak, password2=weak))
            self.assertIn("password2", response.context["form"].errors, weak)
        self.assertFalse(User.objects.exists())

    def test_invalid_contact_number(self):
        response = self.client.post(self.url, valid_registration(contact_number="abc"))
        self.assertIn("contact_number", response.context["form"].errors)

    def test_logged_in_user_is_redirected_away(self):
        make_user("sam", "Cashier")
        self.client.login(username="sam", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("accounts:dashboard_cashier"))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.login_url = reverse("accounts:login")
        self.recorder = make_user("rec", "Recorder")
        self.cashier = make_user("cash", "Cashier")
        self.manager = make_user("boss", "Manager")

    def test_login_page_loads(self):
        self.assertEqual(self.client.get(self.login_url).status_code, 200)

    def test_each_role_lands_on_its_own_dashboard(self):
        expected = {
            "rec": "accounts:dashboard_recorder",
            "cash": "accounts:dashboard_cashier",
            "boss": "accounts:dashboard_manager",
        }
        for username, name in expected.items():
            self.client.logout()
            response = self.client.post(self.login_url, {"username": username, "password": PASSWORD})
            self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
            response = self.client.get(reverse("accounts:dashboard"))
            self.assertRedirects(response, reverse(name))

    def test_invalid_password_shows_error(self):
        response = self.client.post(self.login_url, {"username": "rec", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_user_shows_error(self):
        response = self.client.post(self.login_url, {"username": "nobody", "password": PASSWORD})
        self.assertContains(response, "Invalid username or password")

    def test_deactivated_account_cannot_log_in(self):
        self.recorder.is_active = False
        self.recorder.save()
        response = self.client.post(self.login_url, {"username": "rec", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_logout_ends_session(self):
        self.client.login(username="rec", password=PASSWORD)
        self.assertIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertRedirects(response, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "You have been logged out")

    def test_logout_requires_post(self):
        self.client.login(username="rec", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_after_logout_protected_pages_redirect_to_login(self):
        self.client.login(username="rec", password=PASSWORD)
        self.client.post(reverse("accounts:logout"))
        url = reverse("accounts:dashboard_recorder")
        self.assertRedirects(self.client.get(url), f"{self.login_url}?next={url}")

    def test_home_redirects(self):
        self.assertRedirects(self.client.get("/"), self.login_url)
        self.client.login(username="cash", password=PASSWORD)
        self.assertRedirects(self.client.get("/"), reverse("accounts:dashboard"), fetch_redirect_response=False)


class LoginRequiredTests(TestCase):
    def test_anonymous_users_are_sent_to_login(self):
        protected = [
            "accounts:dashboard", "accounts:dashboard_recorder", "accounts:dashboard_cashier",
            "accounts:dashboard_manager", "accounts:profile", "accounts:profile_edit",
            "accounts:password_change", "accounts:user_list",
        ]
        for name in protected:
            url = reverse(name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}", msg_prefix=name)
        edit_url = reverse("accounts:user_edit", args=[1])
        self.assertRedirects(self.client.get(edit_url), f"{reverse('accounts:login')}?next={edit_url}")


class RoleAccessTests(TestCase):
    DASHBOARDS = {
        "Recorder": "accounts:dashboard_recorder",
        "Cashier": "accounts:dashboard_cashier",
        "Manager": "accounts:dashboard_manager",
    }

    def setUp(self):
        for role in self.DASHBOARDS:
            make_user(role.lower(), role)

    def test_user_can_open_only_own_dashboard(self):
        for role, own_url in self.DASHBOARDS.items():
            self.client.logout()
            self.client.login(username=role.lower(), password=PASSWORD)
            for other_role, url_name in self.DASHBOARDS.items():
                response = self.client.get(reverse(url_name))
                if other_role == role:
                    self.assertEqual(response.status_code, 200, f"{role} -> {other_role}")
                else:
                    self.assertEqual(response.status_code, 403, f"{role} -> {other_role}")
                    self.assertContains(response, "Access denied", status_code=403)

    def test_dashboards_show_role_specific_content(self):
        self.client.login(username="recorder", password=PASSWORD)
        self.assertContains(self.client.get(reverse("accounts:dashboard_recorder")), "Record a delivery")
        self.client.login(username="cashier", password=PASSWORD)
        self.assertContains(self.client.get(reverse("accounts:dashboard_cashier")), "Fisher payouts")
        self.client.login(username="manager", password=PASSWORD)
        response = self.client.get(reverse("accounts:dashboard_manager"))
        self.assertContains(response, "Staff accounts")
        self.assertContains(response, "Manage users")
        self.assertEqual(response.context["counts"]["total"], 3)

    def test_navigation_matches_role(self):
        self.client.login(username="recorder", password=PASSWORD)
        html = self.client.get(reverse("accounts:dashboard_recorder")).content.decode()
        self.assertIn("Deliveries", html)
        self.assertNotIn(reverse("accounts:user_list"), html)
        self.client.login(username="manager", password=PASSWORD)
        html = self.client.get(reverse("accounts:dashboard_manager")).content.decode()
        self.assertIn(reverse("accounts:user_list"), html)

    def test_only_manager_can_manage_users(self):
        target = User.objects.get(username="recorder")
        for username in ("recorder", "cashier"):
            self.client.login(username=username, password=PASSWORD)
            self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 403)
            self.assertEqual(self.client.get(reverse("accounts:user_edit", args=[target.pk])).status_code, 403)
            response = self.client.post(reverse("accounts:user_edit", args=[target.pk]), {"role": "Manager", "is_active": "on"})
            self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.role, "Recorder")

    def test_manager_can_change_role_and_deactivate(self):
        self.client.login(username="manager", password=PASSWORD)
        target = User.objects.get(username="recorder")
        response = self.client.post(reverse("accounts:user_edit", args=[target.pk]), {"role": "Cashier", "is_active": "on"})
        self.assertRedirects(response, reverse("accounts:user_list"))
        target.refresh_from_db()
        self.assertEqual(target.role, "Cashier")
        self.client.post(reverse("accounts:user_edit", args=[target.pk]), {"role": "Cashier"})
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_manager_cannot_demote_or_deactivate_self(self):
        self.client.login(username="manager", password=PASSWORD)
        me = User.objects.get(username="manager")
        response = self.client.post(reverse("accounts:user_edit", args=[me.pk]), {"role": "Cashier", "is_active": "on"})
        self.assertEqual(response.status_code, 200)
        me.refresh_from_db()
        self.assertEqual(me.role, "Manager")
        self.client.post(reverse("accounts:user_edit", args=[me.pk]), {"role": "Manager"})
        me.refresh_from_db()
        self.assertTrue(me.is_active)

    def test_user_list_search_and_filter(self):
        self.client.login(username="manager", password=PASSWORD)
        response = self.client.get(reverse("accounts:user_list"), {"role": "Cashier"})
        self.assertEqual([u.username for u in response.context["users"]], ["cashier"])
        response = self.client.get(reverse("accounts:user_list"), {"q": "recorder"})
        self.assertEqual([u.username for u in response.context["users"]], ["recorder"])

    def test_createsuperuser_gets_manager_role(self):
        admin = User.objects.create_superuser("root", "root@example.com", PASSWORD)
        self.assertEqual(admin.role, "Manager")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = make_user("ana", "Cashier", contact_number="09171234567")
        self.other = make_user("ben", "Recorder")
        self.client.login(username="ana", password=PASSWORD)

    @staticmethod
    def image_file(name="me.png", size=(20, 20)):
        buf = io.BytesIO()
        Image.new("RGB", size, "teal").save(buf, "PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_view_own_profile(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "ana@example.com")
        self.assertContains(response, "09171234567")
        self.assertEqual(response.context["profile_user"], self.user)

    def test_profile_urls_take_no_user_id(self):
        # There is no URL that can address someone else's profile.
        self.assertEqual(reverse("accounts:profile"), "/accounts/profile/")
        self.assertEqual(reverse("accounts:profile_edit"), "/accounts/profile/edit/")
        self.assertEqual(self.client.get("/accounts/profile/%d/" % self.other.pk).status_code, 404)
        self.assertEqual(self.client.get("/accounts/profile/%d/edit/" % self.other.pk).status_code, 404)

    def test_update_profile_details(self):
        response = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "ana.reyes@example.com", "contact_number": "0999 888 7777",
        }, follow=True)
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertContains(response, "Your profile has been updated")
        self.user.refresh_from_db()
        self.assertEqual((self.user.last_name, self.user.email, self.user.contact_number),
                         ("Reyes", "ana.reyes@example.com", "0999 888 7777"))

    def test_posting_cannot_change_role_or_username(self):
        self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "ana@example.com",
            "role": "Manager", "username": "hacker", "is_superuser": "on", "is_staff": "on",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "Cashier")
        self.assertEqual(self.user.username, "ana")
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)

    def test_cannot_take_another_users_email(self):
        response = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "BEN@example.com"})
        self.assertIn("email", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@example.com")

    def test_edit_only_affects_logged_in_user(self):
        self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Changed", "last_name": "Name", "email": "ana@example.com"})
        self.other.refresh_from_db()
        self.assertEqual(self.other.first_name, "Ben")

    def test_upload_profile_photo(self):
        response = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "ana@example.com", "profile_photo": self.image_file(),
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_photo.name.startswith("profile_photos/"))
        self.assertContains(self.client.get(reverse("accounts:profile")), "profile_photos/")

    def test_non_image_upload_rejected(self):
        bad = SimpleUploadedFile("evil.png", b"not really an image", content_type="image/png")
        response = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "ana@example.com", "profile_photo": bad})
        self.assertIn("profile_photo", response.context["form"].errors)

    def test_oversized_photo_rejected(self):
        big = SimpleUploadedFile("big.png", self.image_file().read() + b"0" * (2 * 1024 * 1024 + 10), content_type="image/png")
        response = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Ana", "last_name": "Reyes", "email": "ana@example.com", "profile_photo": big})
        self.assertIn("profile_photo", response.context["form"].errors)

    def test_change_password(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": PASSWORD, "new_password1": "An0ther-Str0ng-pw", "new_password2": "An0ther-Str0ng-pw"}, follow=True)
        self.assertContains(response, "Your password has been changed")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("An0ther-Str0ng-pw"))

    def test_change_password_wrong_old_password(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "nope", "new_password1": "An0ther-Str0ng-pw", "new_password2": "An0ther-Str0ng-pw"})
        self.assertIn("old_password", response.context["form"].errors)
