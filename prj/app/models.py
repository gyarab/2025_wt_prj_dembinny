from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for Class Fund Manager.

    Extends Django's built-in AbstractUser so we keep all the
    standard auth functionality (username, password, email, etc.)
    and simply add the `is_treasurer` flag to distinguish the class
    treasurer (admin) from regular student accounts.
    """

    is_treasurer = models.BooleanField(
        default=False,
        verbose_name="Treasurer",
        help_text="Designates whether this user is the class treasurer "
                  "with administrative privileges over the fund.",
    )

    def __str__(self):
        role = "Treasurer" if self.is_treasurer else "Student"
        return f"{self.get_full_name() or self.username} ({role})"
