from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Telefon raqami kiritilishi shart")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractUser):
    """Tizim foydalanuvchisi: admin yoki o'qituvchi. Kirish — telefon raqami orqali."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "O'qituvchi"

    username = None
    phone = models.CharField("telefon", max_length=20, unique=True)
    full_name = models.CharField("F.I.Sh.", max_length=150)
    role = models.CharField("rol", max_length=20, choices=Role.choices, default=Role.TEACHER)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "foydalanuvchi"
        verbose_name_plural = "foydalanuvchilar"

    def __str__(self):
        return self.full_name or self.phone

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER
