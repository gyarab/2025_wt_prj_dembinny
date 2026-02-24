from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
    verbose_name = 'Accounts & Classes'

    def ready(self):
        """
        Auto-create the four Django Groups that mirror the CustomUser roles.
        Called once when Django starts (after all models are loaded).
        Using post_migrate signal so the auth_group table is guaranteed to exist.
        """
        from django.db.models.signals import post_migrate
        post_migrate.connect(_create_default_groups, sender=self)


def _create_default_groups(sender, **kwargs):
    """
    Ensure the four role groups exist.  This is idempotent – safe to run many
    times.  Permissions can be assigned to these groups in the Django admin or
    in a data migration.
    """
    from django.contrib.auth.models import Group

    GROUPS = [
        'System Admin',
        'Class Treasurer / Teacher',
        'Student',
        'Parent',
    ]
    for name in GROUPS:
        Group.objects.get_or_create(name=name)
